"""
agent/customer_service.py
--------------------------
Core request orchestration for Agent Indemnity.

The live API path is:
  1. Quote the request (route + price)
  2. Require an x402-style payment challenge
  3. Generate the reply only after payment proof verifies
  4. Run hybrid anomaly detection
  5. Auto-slash deterministically when enabled

`handle_request()` remains as a dev/test convenience wrapper that bypasses the
challenge step with a synthetic payment reference. The FastAPI path does not use
that helper.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import time
from datetime import datetime, timezone

from agent import config
from agent.anomaly_detector import detect_anomaly
from agent.model_clients import (
    ModelClientError,
    call_featherless,
    call_gemini_action_controller,
    call_gemini_fallback,
)
from agent.payment_meter import create_payment_record, get_price
from agent.prompts import (
    GENERAL_SYSTEM_PROMPT,
    LEGAL_RISK_SYSTEM_PROMPT,
    TECHNICAL_SYSTEM_PROMPT,
)
from agent.router import route_message

try:
    from backend.blockchain.bond_manager import get_bond_balance, pay_premium, slash_bond
except ImportError:  # pragma: no cover - compatibility fallback
    from blockchain.bond_manager import get_bond_balance, pay_premium, slash_bond

logger = logging.getLogger(__name__)

_LOG_FILE = pathlib.Path(__file__).parent.parent / "logs" / "demo_transactions.json"
_FLAGGED_REFUSAL_REPLY = (
    "I'm sorry, I cannot process that request. This interaction has been flagged and reviewed."
)

_ROUTE_CONFIG: dict[str, tuple[str, str]] = {
    config.GENERAL: (GENERAL_SYSTEM_PROMPT, config.FEATHERLESS_GENERAL_MODEL),
    config.TECHNICAL: (TECHNICAL_SYSTEM_PROMPT, config.FEATHERLESS_TECH_MODEL),
    config.LEGAL_RISK: (LEGAL_RISK_SYSTEM_PROMPT, config.FEATHERLESS_LEGAL_MODEL),
}


def _env_positive_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def quote_request(message: str) -> dict[str, float | str | None]:
    route_decision = route_message(message)
    route = route_decision["route"]
    price = get_price(route)
    return {
        "route_category": route,
        "route_confidence": route_decision.get("confidence"),
        "price_usdc": price,
    }


def _generate_reply(route: str, message: str) -> tuple[str, str]:
    """Return (reply_text, model_id). Raises ModelClientError on failure."""
    if route == config.FALLBACK_COMPLEX:
        logger.info("Generating reply via Gemini fallback model=%s", config.GEMINI_FALLBACK_MODEL)
        return call_gemini_fallback(message), config.GEMINI_FALLBACK_MODEL

    system_prompt, model_id = _ROUTE_CONFIG[route]
    logger.info("Generating reply via Featherless route=%s model=%s", route, model_id)
    try:
        return call_featherless(model_id, system_prompt, message), model_id
    except ModelClientError as exc:
        logger.warning(
            "Featherless failed for route=%s model=%s; falling back to Gemini model=%s error=%s",
            route,
            model_id,
            config.GEMINI_FALLBACK_MODEL,
            exc,
        )
        return call_gemini_fallback(message), config.GEMINI_FALLBACK_MODEL


def _append_to_log(record: dict) -> None:
    _LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing: list = json.loads(_LOG_FILE.read_text()) if _LOG_FILE.exists() else []
    except (json.JSONDecodeError, OSError):
        existing = []
    existing.append(record)
    _LOG_FILE.write_text(json.dumps(existing, indent=2))


def handle_paid_request(
    *,
    message: str,
    user_id: str,
    user_wallet_address: str,
    route: str,
    route_confidence: float | None,
    price: float,
    payment_ref: str,
) -> dict:
    """Process one paid customer message end-to-end."""
    t0 = time.monotonic()
    payment = create_payment_record(user_id, route, price)

    try:
        reply, model_id = _generate_reply(route, message)
        payment_status = "settled"
        payment_error = None
    except ModelClientError as exc:
        logger.error("Provider call failed after payment verification: route=%s error=%s", route, exc)
        reply = "I'm sorry, I'm unable to process your request right now. Please try again."
        model_id = config.MODEL_MAP[route]
        payment_status = "failed"
        payment_error = "Provider unavailable after payment verification"

    anomaly = detect_anomaly(message, reply, route)
    original_reply = reply
    beneficiary_wallet_address = user_wallet_address

    if anomaly["flagged"]:
        reply = _FLAGGED_REFUSAL_REPLY

    auto_slash_enabled = _env_flag("AUTO_SLASH_ON_FLAGGED", True)
    slash_mode = "auto" if anomaly["flagged"] and auto_slash_enabled else "none"
    slash_executed = False
    slash_tx_hash = None
    slash_payout = None
    slash_victim_address = None

    if anomaly["flagged"] and auto_slash_enabled:
        default_payout = _env_positive_float(
            "AUTO_SLASH_PAYOUT_USDC",
            _env_positive_float("SLASH_PAYOUT_USDC", 1.0),
        )
        min_payout = _env_positive_float("AUTO_SLASH_MIN_PAYOUT_USDC", 0.01)
        try:
            available_bond = max(float(get_bond_balance()), 0.0)
        except Exception as exc:
            logger.warning("Unable to read bond balance before auto slash: %s", exc)
            available_bond = 0.0
        payout = min(default_payout, available_bond)
        if payout >= min_payout:
            try:
                slash_tx_hash = slash_bond(beneficiary_wallet_address, payout)
                slash_payout = payout
                slash_victim_address = beneficiary_wallet_address
                slash_executed = True
            except Exception as exc:
                logger.error(
                    "Automatic slash failed: beneficiary=%s amount=%s error=%s",
                    beneficiary_wallet_address,
                    payout,
                    exc,
                )
        else:
            logger.info(
                "Skipping automatic slash: payout below threshold (payout=%s min=%s available=%s)",
                payout,
                min_payout,
                available_bond,
            )

    latency_ms = int((time.monotonic() - t0) * 1000)

    try:
        bond_balance_after = float(get_bond_balance())
    except Exception:
        bond_balance_after = None

    result = {
        "reply": reply,
        "model": model_id,
        "route_category": route,
        "route_confidence": route_confidence,
        "price_usdc": price,
        "payment_status": payment_status,
        "payment_ref": payment_ref,
        "payer_wallet_address": user_wallet_address,
        "beneficiary_wallet_address": beneficiary_wallet_address,
        "flagged": anomaly["flagged"],
        "anomaly_reason": anomaly["reason"],
        "anomaly_signal": anomaly["signal"],
        "payment_error": payment_error,
        "slash_mode": slash_mode,
        "slash_executed": slash_executed,
        "slash_tx_hash": slash_tx_hash,
        "slash_payout": slash_payout,
        "slash_victim_address": slash_victim_address,
        "latency_ms": latency_ms,
        "bond_balance_after": bond_balance_after,
        "payment_record": payment,
    }

    logger.info(
        "Paid request handled: route=%s model=%s price=%s flagged=%s signal=%s latency_ms=%d",
        route,
        model_id,
        price,
        anomaly["flagged"],
        anomaly["signal"],
        latency_ms,
    )

    log_record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
        "user_wallet_address": user_wallet_address,
        "beneficiary_wallet_address": beneficiary_wallet_address,
        "message": message,
        "message_type": "malicious" if anomaly["flagged"] else "normal",
        "model_reply": original_reply,
        "returned_reply": reply,
        "route_category": route,
        "model_used": model_id,
        "price_usdc": price,
        "payment_status": payment_status,
        "payment_ref": payment_ref,
        "anomaly_flagged": anomaly["flagged"],
        "anomaly_reason": anomaly["reason"],
        "anomaly_signal": anomaly["signal"],
        "slash_mode": slash_mode,
        "slash_executed": slash_executed,
        "slash_tx_hash": slash_tx_hash,
        "slash_payout": slash_payout,
        "bond_balance_after": bond_balance_after,
        "route_confidence": route_confidence,
        "payment_error": payment_error,
        "latency_ms": latency_ms,
    }
    _append_to_log(log_record)
    return result


def handle_request(
    message: str,
    user_id: str = "demo-user",
    user_wallet_address: str = "0xDEMOUSER00000000000000000000000000000000",
) -> dict:
    """Compatibility wrapper for scripts/tests outside the x402 challenge flow."""
    quote = quote_request(message)
    payment_ref = f"dev-bypass:{int(time.time() * 1000)}"
    return handle_paid_request(
        message=message,
        user_id=user_id,
        user_wallet_address=user_wallet_address,
        route=str(quote["route_category"]),
        route_confidence=float(quote["route_confidence"] or 0.0),
        price=float(quote["price_usdc"]),
        payment_ref=payment_ref,
    )
