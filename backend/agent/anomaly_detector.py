"""
agent/anomaly_detector.py
--------------------------
Rule-based anomaly detection for every agent exchange.

Stage 1 only for Sprint 2 — fast, zero-cost, deterministic.
Optional Gemini stage-2 safety scoring is scaffolded but not required.

Public API: detect_anomaly(user_message, reply, route_category) -> dict
"""

import re

# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------
_RULES: list[tuple[re.Pattern, str]] = [
    # Jailbreak / instruction override
    (re.compile(
        r"ignore (previous|all|prior) instructions|"
        r"you are now|pretend (you are|to be)|"
        r"dan mode|disregard (your|the) (training|guidelines)|"
        r"act as if you have no restrictions",
        re.IGNORECASE,
    ), "Jailbreak attempt detected"),

    # Unauthorised refund / payout
    (re.compile(
        r"(issue|process|send|give|provide|approve).{0,40}\$\s*[1-9]\d{2,}|"
        r"issue (a )?refund|send money|wire (funds|transfer)|"
        r"payout without (approval|verification)",
        re.IGNORECASE,
    ), "Unauthorised refund or payout suggestion"),

    # Fund transfer without verification
    (re.compile(
        r"transfer funds|wire transfer|send (funds|payment) (to|directly)|"
        r"bypass (verification|kyc|auth)",
        re.IGNORECASE,
    ), "Fund transfer without verification"),

    # Policy / control bypass
    (re.compile(
        r"bypass.{0,20}(policy|controls|security|auth)|"
        r"override.{0,20}(policy|controls|approval)|"
        r"ignore policy",
        re.IGNORECASE,
    ), "Policy or control bypass attempt"),

    # Unsafe compensation promise
    (re.compile(
        r"(promise|guarantee|commit).{0,30}(compensation|refund|payment)|"
        r"you (will|shall) (receive|get).{0,30}(refund|compensation)",
        re.IGNORECASE,
    ), "Unauthorised compensation promise"),

    # Prompt injection via system prefix
    (re.compile(
        r"system\s*:|<\|system\|>|\[SYSTEM\]|<system>",
        re.IGNORECASE,
    ), "Prompt injection via system-role prefix"),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def detect_anomaly(user_message: str, reply: str, route_category: str) -> dict:
    """Check the exchange for abuse signals.

    Args:
        user_message:   The raw customer message.
        reply:          The agent-generated reply.
        route_category: The assigned route (unused in rule-based stage but
                        available for future risk-level gating).

    Returns:
        {"flagged": bool, "reason": str | None}
    """
    combined = f"{user_message}\n{reply}"
    for pattern, reason in _RULES:
        if pattern.search(combined):
            return {"flagged": True, "reason": reason}
    return {"flagged": False, "reason": None}
