from __future__ import annotations

from enum import Enum


class RouteCategory(str, Enum):
    GENERAL = "general"
    LEGAL = "legal"
    TECHNICAL = "technical"
    FALLBACK = "fallback"

    @property
    def risk_level(self) -> str:
        return {
            RouteCategory.GENERAL: "low",
            RouteCategory.TECHNICAL: "medium",
            RouteCategory.LEGAL: "high",
            RouteCategory.FALLBACK: "high",
        }[self]
