"""
agent/anomaly_policy.py
------------------------
Two-stage anomaly detection policy for every agent reply.

Stage 1 — Rules-first (fast, zero-cost):
  Pattern-match the prompt and reply against a curated set of abuse
  signals.  If a rule fires, return immediately without calling the LLM.

Stage 2 — Gemini structured-output check (only when rule stage is
  inconclusive or when the route risk level is "high"):
  Ask Gemini Flash to score the exchange and return a typed verdict.

AnomalyResult is the canonical output.  Upstream code (router, FastAPI)
only depends on this dataclass — the two-stage internals are hidden.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum

from .prompts.anomaly import ANOMALY_CHECK
from .route_categories import RouteCategory


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

class AnomalyType(str, Enum):
    NONE = "none"
    JAILBREAK = "jailbreak"
    REFUND_ABUSE = "refund_abuse"
    POLICY_VIOLATION = "policy_violation"
    PII_EXPOSURE = "pii_exposure"
    PROMPT_INJECTION = "prompt_injection"
    UNAUTHORIZED_ACTION = "unauthorized_action"


@dataclass
class AnomalyResult:
    flagged: bool
    anomaly_type: AnomalyType
    confidence: float          # 0.0–1.0
    reason: str
    triggered_by: str          # "rules" | "gemini" | "none"
    slash_recommended: bool    # True → bond slashing is warranted

    @classmethod
    def clean(cls) -> "AnomalyResult":
        """Convenience factory for a non-flagged result."""
        return cls(
            flagged=False,
            anomaly_type=AnomalyType.NONE,
            confidence=0.0,
            reason="No anomaly detected.",
            triggered_by="none",
            slash_recommended=False,
        )


# ---------------------------------------------------------------------------
# Stage 1 — Rule patterns
# ---------------------------------------------------------------------------

@dataclass
class _Rule:
    pattern: re.Pattern
    anomaly_type: AnomalyType
    confidence: float
    slash_recommended: bool


_RULES: list[_Rule] = [
    # Jailbreak / role override attempts
    _Rule(
        pattern=re.compile(
            r"(ignore (previous|all) instructions|you are now|pretend (you are|to be)|"
            r"DAN mode|disregard (your|the) (training|guidelines)|jailbreak|"
            r"act as if you have no restrictions)",
            re.IGNORECASE,
        ),
        anomaly_type=AnomalyType.JAILBREAK,
        confidence=0.95,
        slash_recommended=True,
    ),
    # Suspicious large refund demands
    _Rule(
        pattern=re.compile(
            r"(issue|process|send|give|provide).{0,40}\$\s*[1-9]\d{2,}",
            re.IGNORECASE,
        ),
        anomaly_type=AnomalyType.REFUND_ABUSE,
        confidence=0.85,
        slash_recommended=True,
    ),
    # Prompt injection via system-role spoofing
    _Rule(
        pattern=re.compile(
            r"(system:\s*|<\|system\|>|\[SYSTEM\]|<system>)",
            re.IGNORECASE,
        ),
        anomaly_type=AnomalyType.PROMPT_INJECTION,
        confidence=0.90,
        slash_recommended=True,
    ),
    # Unauthorized privileged action requests
    _Rule(
        pattern=re.compile(
            r"(delete (all|every|the) (user|account|record|data)|"
            r"drop (table|database)|truncate|admin override|bypass (auth|security))",
            re.IGNORECASE,
        ),
        anomaly_type=AnomalyType.UNAUTHORIZED_ACTION,
        confidence=0.92,
        slash_recommended=True,
    ),
    # PII solicitation from the agent
    _Rule(
        pattern=re.compile(
            r"(give me|tell me|reveal|show me|print).{0,30}"
            r"(credit card|cvv|ssn|social security|password|api key|secret)",
            re.IGNORECASE,
        ),
        anomaly_type=AnomalyType.PII_EXPOSURE,
        confidence=0.88,
        slash_recommended=True,
    ),
]


def _check_rules(text: str) -> AnomalyResult | None:
    """Return an AnomalyResult if any rule fires, else None."""
    combined = text  # check the full exchange text
    for rule in _RULES:
        m = rule.pattern.search(combined)
        if m:
            return AnomalyResult(
                flagged=True,
                anomaly_type=rule.anomaly_type,
                confidence=rule.confidence,
                reason=f"Rule match: '{m.group(0)[:80]}'",
                triggered_by="rules",
                slash_recommended=rule.slash_recommended,
            )
    return None


# ---------------------------------------------------------------------------
# Stage 2 — Gemini structured-output check (async)
# ---------------------------------------------------------------------------


async def _check_gemini(
    user_message: str,
    agent_reply: str,
    *,
    gemini_client,  # google.genai.Client or compatible (google-genai SDK)
) -> AnomalyResult:
    """Call Gemini Flash with a structured-output prompt.

    Falls back to AnomalyResult.clean() on any error to avoid blocking the
    payment pipeline — anomaly errors are logged but not re-raised.
    """
    prompt = ANOMALY_CHECK.format(
        user_message=user_message[:2000],
        agent_reply=agent_reply[:2000],
    )
    try:
        response = await gemini_client.generate_content_async(prompt)
        raw = response.text.strip()
        # Strip optional markdown fences
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        return AnomalyResult(
            flagged=bool(data.get("flagged", False)),
            anomaly_type=AnomalyType(data.get("anomaly_type", "none")),
            confidence=float(data.get("confidence", 0.0)),
            reason=str(data.get("reason", "")),
            triggered_by="gemini",
            slash_recommended=bool(data.get("slash_recommended", False)),
        )
    except Exception as exc:  # noqa: BLE001
        logger.error({"error": str(exc)}, "Gemini anomaly check failed; defaulting to clean")
        return AnomalyResult.clean()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def check_anomaly(
    user_message: str,
    agent_reply: str,
    category: RouteCategory,
    *,
    gemini_client=None,
) -> AnomalyResult:
    """Run the two-stage anomaly check.

    Stage 1 runs first (always).  Stage 2 (Gemini) runs when:
      - the route risk level is "high", OR
      - stage 1 found no rule match (belt-and-suspenders for low-risk routes)

    If `gemini_client` is None, stage 2 is skipped (useful in tests).
    """
    exchange = f"{user_message}\n{agent_reply}"

    # Stage 1 — rules
    rule_result = _check_rules(exchange)
    if rule_result:
        logger.info(
            {"category": category, "anomaly_type": rule_result.anomaly_type},
            "Anomaly flagged by rules",
        )
        return rule_result

    # Stage 2 — Gemini (only when client is available)
    if gemini_client is not None and category.risk_level in ("high", "medium"):
        gemini_result = await _check_gemini(
            user_message, agent_reply, gemini_client=gemini_client
        )
        if gemini_result.flagged:
            logger.info(
                {"category": category, "anomaly_type": gemini_result.anomaly_type},
                "Anomaly flagged by Gemini",
            )
        return gemini_result

    return AnomalyResult.clean()
