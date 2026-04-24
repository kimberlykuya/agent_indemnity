from __future__ import annotations

from datetime import datetime, timezone

from pydantic import ValidationError

try:
    from backend.api.schemas import ChatResponse, PaymentChallengeResponse
except ImportError:  # pragma: no cover - compatibility fallback
    from api.schemas import ChatResponse, PaymentChallengeResponse

try:
    from backend.agent.customer_service import handle_paid_request, quote_request
except ImportError:  # pragma: no cover - compatibility fallback
    from agent.customer_service import handle_paid_request, quote_request

try:
    from backend.blockchain.bond_manager import get_bond_balance
except ImportError:  # pragma: no cover - compatibility fallback
    from blockchain.bond_manager import get_bond_balance

try:
    from backend.services.payment_gateway import PaymentGateway, PaymentGatewayError
except ImportError:  # pragma: no cover - compatibility fallback
    from services.payment_gateway import PaymentGateway, PaymentGatewayError

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


class PaymentRequiredError(RuntimeError):
    def __init__(self, payload: PaymentChallengeResponse) -> None:
        super().__init__(payload.message)
        self.payload = payload


class ChatService:
    def __init__(
        self,
        quoter=quote_request,
        paid_handler=handle_paid_request,
        payment_gateway: PaymentGateway | None = None,
        bond_balance_reader=get_bond_balance,
        now_factory=None,
    ) -> None:
        self._quoter = quoter
        self._paid_handler = paid_handler
        self._payment_gateway = payment_gateway or PaymentGateway()
        self._bond_balance_reader = bond_balance_reader
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))

    def process_message(
        self,
        *,
        message: str,
        user_id: str,
        user_wallet_address: str,
        payment_challenge_token: str | None = None,
        payment_proof: dict | None = None,
    ) -> ChatResponse:
        if not payment_challenge_token or payment_proof is None:
            raise self._payment_required(
                message=message,
                user_id=user_id,
                user_wallet_address=user_wallet_address,
            )

        try:
            settlement = self._payment_gateway.verify_payment(
                message=message,
                user_id=user_id,
                user_wallet_address=user_wallet_address,
                challenge_token=payment_challenge_token,
                payment_proof=payment_proof,
            )
        except PaymentGatewayError as exc:
            raise ChatServiceError(exc.message, status_code=exc.status_code, code=exc.code) from exc

        try:
            raw = self._paid_handler(
                message=message,
                user_id=user_id,
                user_wallet_address=user_wallet_address,
                route=settlement.route_category,
                route_confidence=settlement.route_confidence,
                price=settlement.price_usdc,
                payment_ref=settlement.payment_ref,
            )
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
                route_confidence=raw.get("route_confidence"),
                price_usdc=raw["price_usdc"],
                payment_status=self._normalize_payment_status(raw.get("payment_status")),
                bond_balance=bond_balance,
                flagged=bool(raw.get("flagged", False)),
                payment_ref=str(raw["payment_ref"]),
                anomaly_reason=raw.get("anomaly_reason"),
                slash_executed=bool(raw.get("slash_executed", False)),
                slash_tx_hash=raw.get("slash_tx_hash"),
                slash_payout=raw.get("slash_payout"),
                slash_victim_address=raw.get("slash_victim_address"),
                payer_wallet_address=str(raw["payer_wallet_address"]),
                beneficiary_wallet_address=str(raw["beneficiary_wallet_address"]),
                anomaly_signal=str(raw.get("anomaly_signal", "none")),
                slash_mode=str(raw.get("slash_mode", "none")),
                timestamp=self._now_factory(),
            )
        except KeyError as exc:
            raise ChatServiceError("Chat service returned an incomplete response", status_code=500) from exc
        except ValidationError as exc:
            raise ChatServiceError("Chat service returned an invalid response", status_code=500) from exc

    def _payment_required(
        self,
        *,
        message: str,
        user_id: str,
        user_wallet_address: str,
    ) -> PaymentRequiredError:
        try:
            quote = self._quoter(message)
        except Exception as exc:
            raise ChatServiceError("Failed to quote chat request", status_code=502, code="pricing_failed") from exc

        challenge = self._payment_gateway.create_challenge(
            message=message,
            user_id=user_id,
            user_wallet_address=user_wallet_address,
            route_category=str(quote["route_category"]),
            route_confidence=quote.get("route_confidence"),
            price_usdc=float(quote["price_usdc"]),
        )

        payload = PaymentChallengeResponse(
            message="Payment required before the agent can answer this request.",
            route_category=self._normalize_route(challenge.route_category),
            route_confidence=challenge.route_confidence,
            price_usdc=challenge.price_usdc,
            payment_challenge_token=challenge.token,
            expires_at=challenge.expires_at,
            payment_network=self._payment_gateway.payment_network,
            facilitator_url=self._payment_gateway.facilitator_url,
            payment_instructions=self._payment_gateway.build_instructions(challenge),
        )
        return PaymentRequiredError(payload)

    @staticmethod
    def _normalize_route(route_category: str) -> str:
        try:
            return _ROUTE_MAP[route_category]
        except KeyError as exc:
            raise ChatServiceError("Unknown route category from orchestrator", status_code=500) from exc

    @staticmethod
    def _normalize_payment_status(payment_status: str | None) -> str:
        if payment_status == "settled":
            return "settled"
        if payment_status in {"provider_error", "payment_failed", "failed"}:
            return "failed"
        return "authorized"
