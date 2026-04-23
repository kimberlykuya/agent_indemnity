"""
agent/payment_meter.py
-----------------------
Price each request and produce a serializable payment record.

No x402 / HTTP middleware here — that belongs at the API layer (Sprint 3).
"""

from agent import config


class UnknownRouteError(ValueError):
    """Raised when a route has no price entry."""


def get_price(route_category: str) -> float:
    """Return the USDC price for a route category.

    Raises UnknownRouteError for unrecognised routes.
    """
    if route_category not in config.PRICE_MAP:
        raise UnknownRouteError(
            f"No price defined for route '{route_category}'. "
            f"Valid routes: {config.ALL_ROUTES}"
        )
    return config.PRICE_MAP[route_category]


def create_payment_record(user_id: str, route_category: str, price_usdc: float) -> dict:
    """Return a serializable payment record dict.

    Shape:
        {
            "payment_status": "priced",
            "price_usdc": float,
            "currency": "USDC",
            "route_category": str,
            "buyer_id": str,
        }
    """
    return {
        "payment_status": "priced",
        "price_usdc":     price_usdc,
        "currency":       "USDC",
        "route_category": route_category,
        "buyer_id":       user_id,
    }
