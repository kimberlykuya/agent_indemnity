"""
agent/price_table.py
---------------------
Per-request USDC pricing for each route category.

Prices are expressed in USDC (6 decimal places on-chain; represented here
as plain Python floats for arithmetic convenience).  All values are ≤ $0.01
as required by the hackathon acceptance criteria.

Price structure from plan.md Sprint 2:
  general   → $0.001   (fast, cheap default — Featherless general)
  legal     → $0.005   (higher-stakes handling — Featherless legal/risk)
  technical → $0.003   (domain accuracy — Featherless technical)
  fallback  → $0.010   (deep reasoning — Gemini 3 Pro)
"""

from dataclasses import dataclass

from .route_categories import RouteCategory


@dataclass(frozen=True)
class PriceEntry:
    """Immutable price descriptor for a single routing tier."""

    category: RouteCategory
    usdc: float          # e.g. 0.001
    usdc_micro: int      # usdc expressed in USDC micro-units (6 dp): 0.001 → 1000

    @property
    def display(self) -> str:
        return f"${self.usdc:.4f} USDC"


# ---------------------------------------------------------------------------
# Authoritative price table
# ---------------------------------------------------------------------------
PRICE_TABLE: dict[RouteCategory, PriceEntry] = {
    RouteCategory.GENERAL: PriceEntry(
        category=RouteCategory.GENERAL,
        usdc=0.001,
        usdc_micro=1_000,
    ),
    RouteCategory.TECHNICAL: PriceEntry(
        category=RouteCategory.TECHNICAL,
        usdc=0.003,
        usdc_micro=3_000,
    ),
    RouteCategory.LEGAL: PriceEntry(
        category=RouteCategory.LEGAL,
        usdc=0.005,
        usdc_micro=5_000,
    ),
    RouteCategory.FALLBACK: PriceEntry(
        category=RouteCategory.FALLBACK,
        usdc=0.010,
        usdc_micro=10_000,
    ),
}


def get_price(category: RouteCategory) -> PriceEntry:
    """Return the PriceEntry for a given RouteCategory.

    Raises KeyError for unknown categories (should never happen with
    a properly typed enum, but guards against future enum extensions
    that forget to update this table).
    """
    if category not in PRICE_TABLE:
        raise KeyError(
            f"No price defined for RouteCategory '{category}'. "
            "Update PRICE_TABLE in price_table.py."
        )
    return PRICE_TABLE[category]
