"""
agent/customer_service.py
--------------------------
Orchestrates the full request lifecycle for one customer message.

Flow per request:
  1. Start timer
  2. route_message     → route + confidence
  3. get_price         → price_usdc
  4. create_payment_record
  5. call appropriate provider
  6. detect_anomaly
  7. Calculate latency, compose result
  8. Append to log
  9. Return result
"""

import json
import logging
import os
import pathlib
import time

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

# Map route → (system_prompt, model_id)
_ROUTE_CONFIG: dict[str, tuple[str, str]] = {
    config.GENERAL:   (GENERAL_SYSTEM_PROMPT,    config.FEATHERLESS_GENERAL_MODEL),
    config.TECHNICAL: (TECHNICAL_SYSTEM_PROMPT,  config.FEATHERLESS_TECH_MODEL),
    config.LEGAL_RISK:(LEGAL_RISK_SYSTEM_PROMPT, config.FEATHERLESS_LEGAL_MODEL),
}


def _env_positive_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if value <= 0:
        return default
    return value


def _safe_float(value: object, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    return parsed


def _action_controller_context(
    *,
    user_id: str,
    message: str,
    reply: str,
    route: str,
    price: float,
    flagged: bool,
    anomaly_reason: str | None,
) -> dict:
    victim_address = (
        os.getenv("AUTO_SLASH_VICTIM_ADDRESS")
        or os.getenv("VICTIM_WALLET_ADDRESS")
        or ""
    )
    suggested_slash_payout = _env_positive_float(
        "AUTO_SLASH_PAYOUT_USDC",
        _env_positive_float("SLASH_PAYOUT_USDC", 1.0),
    )
    min_slash_payout = _env_positive_float("AUTO_SLASH_MIN_PAYOUT_USDC", 0.01)
    try:
        available_bond_balance = max(float(get_bond_balance()), 0.0)
    except Exception:
        available_bond_balance = 0.0

    return {
        "user_id": user_id,
        "message": message,
        "reply": reply,
        "route_category": route,
        "price_usdc": price,
        "flagged": flagged,
        "anomaly_reason": anomaly_reason,
        "suggested_actions": {
            "settle_premium_amount_usdc": price,
            "victim_address": victim_address,
            "suggested_slash_payout_usdc": suggested_slash_payout,
            "min_slash_payout_usdc": min_slash_payout,
            "available_bond_balance_usdc": available_bond_balance,
        },
    }


def _run_ai_actions(
    *,
    user_id: str,
    message: str,
    reply: str,
    route: str,
    price: float,
    flagged: bool,
    anomaly_reason: str | None,
    payment_ref: str | None,
    payment_status: str,
) -> dict:
    result = {
        "payment_ref": payment_ref,
        "payment_status": payment_status,
        "slash_executed": False,
        "slash_tx_hash": None,
        "slash_payout": None,
        "slash_victim_address": None,
    }

    try:
        calls = call_gemini_action_controller(
            _action_controller_context(
                user_id=user_id,
                message=message,
                reply=reply,
                route=route,
                price=price,
                flagged=flagged,
                anomaly_reason=anomaly_reason,
            )
        )
    except ModelClientError as exc:
        logger.warning("Gemini action controller failed; no action tools will be executed: %s", exc)
        calls = []

    settled_by_ai = False
    victim_address = (
        os.getenv("AUTO_SLASH_VICTIM_ADDRESS")
        or os.getenv("VICTIM_WALLET_ADDRESS")
        or ""
    )
    default_payout = _env_positive_float(
        "AUTO_SLASH_PAYOUT_USDC",
        _env_positive_float("SLASH_PAYOUT_USDC", 1.0),
    )
    min_payout = _env_positive_float("AUTO_SLASH_MIN_PAYOUT_USDC", 0.01)

    for call in calls:
        name = str(call.get("name", "")).strip()
        args = call.get("args", {})
        if not isinstance(args, dict):
            args = {}

        if name == "settle_premium":
            if settled_by_ai:
                logger.warning("Ignoring duplicate AI settle_premium tool call")
                continue
            amount = _safe_float(args.get("amount_usdc"), price)
            try:
                result["payment_ref"] = pay_premium(amount)
                result["payment_status"] = "settled"
                settled_by_ai = True
            except Exception as exc:
                logger.error(
                    "AI-triggered premium settlement failed: route=%s amount=%s error=%s",
                    route,
                    amount,
                    exc,
                )
                result["payment_status"] = "payment_failed"
        elif name == "slash_performance_bond":
            if not flagged:
                logger.warning("Ignoring AI slash tool call because exchange is not flagged")
                continue
            if result["slash_executed"]:
                logger.warning("Ignoring duplicate AI slash_performance_bond tool call")
                continue
            payout = _safe_float(args.get("payout_amount_usdc"), default_payout)
            slash_victim = str(args.get("victim_address") or victim_address).strip()
            if not slash_victim:
                logger.warning("Ignoring AI slash tool call because victim address is missing")
                continue
            try:
                available_bond = max(float(get_bond_balance()), 0.0)
            except Exception as exc:
                logger.warning("Unable to read bond balance before AI slash: %s", exc)
                available_bond = 0.0
            payout = min(payout, available_bond)
            if payout < min_payout:
                logger.info(
                    "Skipping AI slash call: payout below minimum threshold "
                    "(payout=%s min=%s available=%s)",
                    payout,
                    min_payout,
                    available_bond,
                )
                continue
            try:
                result["slash_tx_hash"] = slash_bond(slash_victim, payout)
                result["slash_payout"] = payout
                result["slash_victim_address"] = slash_victim
                result["slash_executed"] = True
            except Exception as exc:
                logger.error(
                    "AI-triggered slash failed: victim=%s amount=%s error=%s",
                    slash_victim,
                    payout,
                    exc,
                )

    if not settled_by_ai:
        logger.warning("AI controller did not execute settle_premium; request remains unsettled")
        result["payment_status"] = "payment_failed"

    return result


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


def handle_request(message: str, user_id: str = "demo-user") -> dict:
    """Process one customer message end-to-end.

    Returns a dict matching the agreed response schema:
        reply, model, route_category, route_confidence, price_usdc,
        payment_status, flagged, anomaly_reason, latency_ms
    """
    t0 = time.monotonic()

    # 1. Route
    route_decision = route_message(message)
    route = route_decision["route"]

    # 2. Price
    price = get_price(route)

    # 3. Payment record
    payment = create_payment_record(user_id, route, price)
    payment_status = payment["payment_status"]
    payment_ref = payment.get("payment_ref")

    # 4. Generate reply
    try:
        reply, model_id = _generate_reply(route, message)
    except ModelClientError as exc:
        logger.error("Provider call failed: route=%s error=%s", route, exc)
        reply      = "I'm sorry, I'm unable to process your request right now. Please try again."
        model_id   = config.MODEL_MAP[route]
        payment_status = "provider_error"

    # 5. Anomaly detection
    anomaly = detect_anomaly(message, reply, route)

    slash_executed = False
    slash_tx_hash = None
    slash_payout = None
    slash_victim_address = None

    if payment_status != "provider_error":
        action_result = _run_ai_actions(
            user_id=user_id,
            message=message,
            reply=reply,
            route=route,
            price=price,
            flagged=anomaly["flagged"],
            anomaly_reason=anomaly["reason"],
            payment_ref=payment_ref,
            payment_status=payment_status,
        )
        payment_ref = action_result["payment_ref"]
        payment_status = action_result["payment_status"]
        slash_executed = bool(action_result["slash_executed"])
        slash_tx_hash = action_result["slash_tx_hash"]
        slash_payout = action_result["slash_payout"]
        slash_victim_address = action_result["slash_victim_address"]

    # 6. Latency
    latency_ms = int((time.monotonic() - t0) * 1000)

    result = {
        "reply":            reply,
        "model":            model_id,
        "route_category":   route,
        "route_confidence": route_decision["confidence"],
        "price_usdc":       price,
        "payment_status":   payment_status,
        "payment_ref":      payment_ref,
        "flagged":          anomaly["flagged"],
        "anomaly_reason":   anomaly["reason"],
        "slash_executed":   slash_executed,
        "slash_tx_hash":    slash_tx_hash,
        "slash_payout":     slash_payout,
        "slash_victim_address": slash_victim_address,
        "latency_ms":       latency_ms,
    }

    logger.info("Request handled: route=%s model=%s price=%s flagged=%s latency_ms=%d",
                route, model_id, price, anomaly["flagged"], latency_ms)

    _append_to_log({**result, "user_id": user_id, "message": message})
    return result
