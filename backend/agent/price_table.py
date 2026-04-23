from __future__ import annotations

from dataclasses import dataclass

from agent.route_categories import RouteCategory

_PRICE_MAP = {
    RouteCategory.GENERAL: 0.001,
    RouteCategory.TECHNICAL: 0.003,
    RouteCategory.LEGAL: 0.005,
    RouteCategory.FALLBACK: 0.010,
}


@dataclass(frozen=True)
class PriceEntry:
    usdc: float

    @property
    def usdc_micro(self) -> int:
        return round(self.usdc * 1_000_000)


def get_price(category: RouteCategory) -> PriceEntry:
    return PriceEntry(usdc=_PRICE_MAP[category])
