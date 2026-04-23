from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError

from backend.api.schemas import ChatResponse

try:
    from backend.agent.customer_service import handle_request
except ImportError:  # pragma: no cover - compatibility fallback
    from agent.customer_service import handle_request

try:
    from backend.blockchain.bond_manager import get_bond_balance
except ImportError:  # pragma: no cover - compatibility fallback
    from blockchain.bond_manager import get_bond_balance

_ROUTE_MAP = {
    "general": "general",
    "technical": "technical",
    "legal_risk": "legal",
    "fallback_complex": "fallback",
}


class ChatServiceError(RuntimeError):
    def __init__(self, message: str, *, status_code: int = 502, code: str = "chat_service_error") -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class ChatService:
    def __init__(self, orchestrator=handle_request, bond_balance_reader=get_bond_balance, now_factory=None) -> None:
        self._orchestrator = orchestrator
        self._bond_balance_reader = bond_balance_reader
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))

    def process_message(self, message: str, user_id: str) -> ChatResponse:
        try:
            raw = self._orchestrator(message=message, user_id=user_id)
        except Exception as exc:
            raise ChatServiceError("Failed to process chat request", status_code=502) from exc

        try:
            bond_balance = self._bond_balance_reader()
        except Exception as exc:
            raise ChatServiceError("Failed to fetch bond balance", status_code=502) from exc

        try:
            return ChatResponse(
                reply=raw["reply"],
                model=raw["model"],
                route_category=self._normalize_route(raw["route_category"]),
                price_usdc=raw["price_usdc"],
                payment_status=self._normalize_payment_status(raw.get("payment_status")),
                bond_balance=bond_balance,
                flagged=bool(raw.get("flagged", False)),
                payment_ref=self._payment_ref(raw),
                timestamp=self._now_factory(),
            )
        except KeyError as exc:
            raise ChatServiceError("Chat service returned an incomplete response", status_code=500) from exc
        except ValidationError as exc:
            raise ChatServiceError("Chat service returned an invalid response", status_code=500) from exc

    @staticmethod
    def _normalize_route(route_category: str) -> str:
        try:
            return _ROUTE_MAP[route_category]
        except KeyError as exc:
            raise ChatServiceError("Unknown route category from orchestrator", status_code=500) from exc

    @staticmethod
    def _normalize_payment_status(payment_status: str | None) -> str:
        if payment_status == "provider_error":
            return "failed"
        return "authorized"

    @staticmethod
    def _payment_ref(raw: dict) -> str:
        payment_ref = raw.get("payment_ref")
        if payment_ref:
            return str(payment_ref)
        return f"pay_{uuid4().hex[:12]}"
