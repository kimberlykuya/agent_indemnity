"""
agent/router.py
----------------
Two-stage message router.

Stage 1 — rules_route(): fast keyword matching, zero cost.
Stage 2 — gemini_route(): Gemini structured-output classification,
           called only when rules confidence is below threshold.

Public API: route_message() — always returns a valid route dict.
"""

import json
import logging
import re

from agent import config
from agent.model_clients import ModelClientError, call_gemini_router
from agent.prompts import ROUTER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword sets (Stage 1)
# ---------------------------------------------------------------------------
_LEGAL_KW = {
    "refund", "chargeback", "compensation", "lawsuit", "policy",
    "liability", "compliance", "legal", "dispute", "claim",
}
_TECH_KW = {
    "bug", "error", "api", "integration", "crash", "broken",
    "failed", "timeout", "login", "exception", "stacktrace",
    "401", "403", "500", "502", "503",
}

_ALLOWED_ROUTES = set(config.ALL_ROUTES)


# ---------------------------------------------------------------------------
# Stage 1 — rules-based
# ---------------------------------------------------------------------------
def rules_route(message: str) -> dict:
    """Classify by keyword matching.

    Returns: {"route": str, "confidence": float, "reason": str}
    """
    words = set(re.findall(r"[a-z0-9]+", message.lower()))
    legal_hits = words & _LEGAL_KW
    tech_hits  = words & _TECH_KW

    if legal_hits and not tech_hits:
        return {
            "route": config.LEGAL_RISK,
            "confidence": 0.90,
            "reason": f"legal keywords: {sorted(legal_hits)}",
        }
    if tech_hits and not legal_hits:
        return {
            "route": config.TECHNICAL,
            "confidence": 0.90,
            "reason": f"technical keywords: {sorted(tech_hits)}",
        }
    if legal_hits and tech_hits:
        return {
            "route": config.GENERAL,
            "confidence": 0.40,
            "reason": "mixed legal+technical signals — low confidence",
        }
    return {
        "route": config.GENERAL,
        "confidence": 0.90,
        "reason": "no domain keywords matched; defaulting to general",
    }


# ---------------------------------------------------------------------------
# Stage 2 — Gemini structured-output
# ---------------------------------------------------------------------------
def gemini_route(message: str) -> dict:
    """Classify via Gemini structured JSON output.

    Falls back to fallback_complex on any error or invalid output.
    Returns: {"route": str, "confidence": float, "reason": str}
    """
    _safe_fallback = {
        "route": config.FALLBACK_COMPLEX,
        "confidence": 0.50,
        "reason": "Gemini classification failed — defaulting to fallback_complex",
    }
    try:
        raw = call_gemini_router(message, ROUTER_SYSTEM_PROMPT)
        data = json.loads(raw)
        route = data.get("route", "")
        if route not in _ALLOWED_ROUTES:
            logger.warning("Gemini returned unknown route: %s", route)
            return _safe_fallback
        return {
            "route": route,
            "confidence": float(data.get("confidence", 0.5)),
            "reason": str(data.get("reason", "")),
        }
    except (ModelClientError, json.JSONDecodeError, KeyError, ValueError) as exc:
        logger.warning("Gemini route failed; using fallback_complex: %s", exc)
        return _safe_fallback


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def route_message(message: str) -> dict:
    """Route a message using two-stage classification.

    Returns a dict with keys: route, confidence, reason, decided_by.
    Always returns a valid result — never raises.
    """
    rules = rules_route(message)

    if rules["confidence"] >= config.RULE_CONFIDENCE_THRESHOLD:
        logger.info("Route decided by rules: %s (confidence=%.2f)",
                    rules["route"], rules["confidence"])
        return {**rules, "decided_by": "rules"}

    gemini = gemini_route(message)
    logger.info("Route decided by Gemini: %s (confidence=%.2f)",
                gemini["route"], gemini["confidence"])
    return {**gemini, "decided_by": "gemini"}
