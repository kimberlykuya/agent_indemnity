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
import pathlib
import time

from agent import config
from agent.anomaly_detector import detect_anomaly
from agent.model_clients import ModelClientError, call_featherless, call_gemini_fallback
from agent.payment_meter import create_payment_record, get_price
from agent.prompts import (
    GENERAL_SYSTEM_PROMPT,
    LEGAL_RISK_SYSTEM_PROMPT,
    TECHNICAL_SYSTEM_PROMPT,
)
from agent.router import route_message

logger = logging.getLogger(__name__)

_LOG_FILE = pathlib.Path(__file__).parent.parent / "logs" / "demo_transactions.json"

# Map route → (system_prompt, model_id)
_ROUTE_CONFIG: dict[str, tuple[str, str]] = {
    config.GENERAL:   (GENERAL_SYSTEM_PROMPT,    config.FEATHERLESS_GENERAL_MODEL),
    config.TECHNICAL: (TECHNICAL_SYSTEM_PROMPT,  config.FEATHERLESS_TECH_MODEL),
    config.LEGAL_RISK:(LEGAL_RISK_SYSTEM_PROMPT, config.FEATHERLESS_LEGAL_MODEL),
}


def _generate_reply(route: str, message: str) -> tuple[str, str]:
    """Return (reply_text, model_id). Raises ModelClientError on failure."""
    if route == config.FALLBACK_COMPLEX:
        return call_gemini_fallback(message), config.GEMINI_FALLBACK_MODEL

    system_prompt, model_id = _ROUTE_CONFIG[route]
    return call_featherless(model_id, system_prompt, message), model_id


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

    # 4. Generate reply
    try:
        reply, model_id = _generate_reply(route, message)
        payment_status = payment["payment_status"]
    except ModelClientError as exc:
        logger.error("Provider call failed: route=%s error=%s", route, exc)
        reply      = "I'm sorry, I'm unable to process your request right now. Please try again."
        model_id   = config.MODEL_MAP[route]
        payment_status = "provider_error"

    # 5. Anomaly detection
    anomaly = detect_anomaly(message, reply, route)
    if anomaly["flagged"]:
        payment_status = "flagged"

    # 6. Latency
    latency_ms = int((time.monotonic() - t0) * 1000)

    result = {
        "reply":            reply,
        "model":            model_id,
        "route_category":   route,
        "route_confidence": route_decision["confidence"],
        "price_usdc":       price,
        "payment_status":   payment_status,
        "flagged":          anomaly["flagged"],
        "anomaly_reason":   anomaly["reason"],
        "latency_ms":       latency_ms,
    }

    logger.info("Request handled: route=%s model=%s price=%s flagged=%s latency_ms=%d",
                route, model_id, price, anomaly["flagged"], latency_ms)

    _append_to_log({**result, "user_id": user_id, "message": message})
    return result
