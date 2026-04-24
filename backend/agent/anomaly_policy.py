from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agent.anomaly_detector import detect_anomaly


class AnomalyType(str, Enum):
    NONE = "none"
    JAILBREAK = "jailbreak"
    UNAUTHORIZED_REFUND = "unauthorized_refund"
    POLICY_BYPASS = "policy_bypass"
    PROMPT_INJECTION = "prompt_injection"


@dataclass(frozen=True)
class AnomalyResult:
    flagged: bool
    anomaly_type: AnomalyType
    confidence: float
    slash_recommended: bool

    @classmethod
    def clean(cls) -> "AnomalyResult":
        return cls(
            flagged=False,
            anomaly_type=AnomalyType.NONE,
            confidence=0.0,
            slash_recommended=False,
        )


def _map_reason_to_type(reason: str | None) -> tuple[AnomalyType, bool]:
    if not reason:
        return AnomalyType.NONE, False
    lowered = reason.lower()
    if "system-role" in lowered or "system-role prefix" in lowered or "prompt injection" in lowered:
        return AnomalyType.PROMPT_INJECTION, False
    if "refund" in lowered or "payout" in lowered:
        return AnomalyType.UNAUTHORIZED_REFUND, True
    if "policy" in lowered or "control" in lowered:
        return AnomalyType.POLICY_BYPASS, True
    if "jailbreak" in lowered:
        return AnomalyType.JAILBREAK, False
    return AnomalyType.JAILBREAK, False


async def check_anomaly(
    user_message: str,
    agent_reply: str,
    category: str,
    gemini_client=None,
) -> AnomalyResult:
    combined = f"{user_message}\n{agent_reply}".lower()
    if "system:" in combined or "<|system|>" in combined or "[system]" in combined or "<system>" in combined:
        return AnomalyResult(
            flagged=True,
            anomaly_type=AnomalyType.PROMPT_INJECTION,
            confidence=0.95,
            slash_recommended=False,
        )

    result = detect_anomaly(user_message, agent_reply, category)
    if not result["flagged"]:
        return AnomalyResult.clean()

    anomaly_type, slash_recommended = _map_reason_to_type(result.get("reason"))
    return AnomalyResult(
        flagged=True,
        anomaly_type=anomaly_type,
        confidence=float(result.get("confidence", 0.95)),
        slash_recommended=slash_recommended,
    )
