"""
agent/route_categories.py
--------------------------
Canonical route categories for the AgentIndemnity customer-service agent.

Every inbound message is classified into exactly one RouteCategory.
The category drives model selection (model_map.py) and per-request
pricing (price_table.py).
"""

from enum import Enum


class RouteCategory(str, Enum):
    """Four canonical routing tiers for the customer-service agent."""

    # Everyday questions: product info, hours, policies, greetings
    GENERAL = "general"

    # Complaints that reference refunds, disputes, SLA breaches, or legal terms
    LEGAL = "legal"

    # Bug reports, integration issues, error codes, API/SDK questions
    TECHNICAL = "technical"

    # Ambiguous, mixed-intent, or low-confidence prompts — routed to the
    # strongest model for deep reasoning
    FALLBACK = "fallback"

    # ------------------------------------------------------------------ #
    # Convenience helpers                                                  #
    # ------------------------------------------------------------------ #

    @property
    def label(self) -> str:
        """Human-readable label for dashboards and logs."""
        return {
            RouteCategory.GENERAL: "General Query",
            RouteCategory.LEGAL: "Legal / Refund / Dispute",
            RouteCategory.TECHNICAL: "Technical Issue",
            RouteCategory.FALLBACK: "Ambiguous / High-Stakes Fallback",
        }[self]

    @property
    def risk_level(self) -> str:
        """Relative risk level; used to decide anomaly-check depth."""
        return {
            RouteCategory.GENERAL: "low",
            RouteCategory.LEGAL: "high",
            RouteCategory.TECHNICAL: "medium",
            RouteCategory.FALLBACK: "high",
        }[self]
