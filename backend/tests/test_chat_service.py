from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.services.chat_service import ChatService, ChatServiceError, PaymentRequiredError
from backend.services.payment_gateway import PaymentGatewayError, PaymentSettlement


FIXED_NOW = datetime(2026, 4, 24, 8, 0, 0, tzinfo=timezone.utc)


class StubGateway:
    payment_network = "Circle Gateway / x402"
    facilitator_url = "https://facilitator.example"

    def __init__(self, settlement: PaymentSettlement | None = None, error: Exception | None = None) -> None:
        self._settlement = settlement
        self._error = error

    def create_challenge(self, **kwargs):
        from backend.services.payment_gateway import PaymentChallenge

        return PaymentChallenge(
            token="challenge-token",
            message_hash="hash",
            user_id=kwargs["user_id"],
            user_wallet_address=kwargs["user_wallet_address"],
            route_category=kwargs["route_category"],
            route_confidence=kwargs["route_confidence"],
            price_usdc=kwargs["price_usdc"],
            created_at=FIXED_NOW,
            expires_at=FIXED_NOW,
        )

    def build_instructions(self, challenge):
        return {"amount_usdc": challenge.price_usdc}

    def verify_payment(self, **kwargs):
        if self._error is not None:
            raise self._error
        assert self._settlement is not None
        return self._settlement


def test_process_message_raises_payment_required_without_proof() -> None:
    service = ChatService(
        quoter=lambda message: {
            "route_category": "general",
            "route_confidence": 0.9,
            "price_usdc": 0.001,
        },
        paid_handler=lambda **kwargs: {},
        payment_gateway=StubGateway(),
        bond_balance_reader=lambda: 100.0,
        now_factory=lambda: FIXED_NOW,
    )

    with pytest.raises(PaymentRequiredError) as exc_info:
        service.process_message(
            message="hello",
            user_id="user_1",
            user_wallet_address="0xabc123",
        )

    assert exc_info.value.payload.payment_challenge_token == "challenge-token"
    assert exc_info.value.payload.price_usdc == 0.001


def test_process_message_raises_on_gateway_error() -> None:
    service = ChatService(
        quoter=lambda message: {
            "route_category": "general",
            "route_confidence": 0.9,
            "price_usdc": 0.001,
        },
        paid_handler=lambda **kwargs: {},
        payment_gateway=StubGateway(
            error=PaymentGatewayError("Invalid payment proof", code="invalid_payment_proof", status_code=402)
        ),
        bond_balance_reader=lambda: 100.0,
        now_factory=lambda: FIXED_NOW,
    )

    with pytest.raises(ChatServiceError) as exc_info:
        service.process_message(
            message="hello",
            user_id="user_1",
            user_wallet_address="0xabc123",
            payment_challenge_token="challenge-token",
            payment_proof={
                "proof_token": "challenge-token",
                "payer_wallet_address": "0xabc123",
                "facilitator_tx_ref": "demo-ref",
            },
        )

    assert exc_info.value.status_code == 402
    assert exc_info.value.code == "invalid_payment_proof"


def test_process_message_returns_normalized_paid_response() -> None:
    service = ChatService(
        quoter=lambda message: {
            "route_category": "general",
            "route_confidence": 0.9,
            "price_usdc": 0.001,
        },
        paid_handler=lambda **kwargs: {
            "reply": "Processed",
            "model": "demo-model",
            "route_category": "general",
            "route_confidence": 0.9,
            "price_usdc": 0.001,
            "payment_status": "settled",
            "payment_ref": "0xpaydemo",
            "flagged": False,
            "anomaly_reason": None,
            "slash_executed": False,
            "slash_tx_hash": None,
            "slash_payout": None,
            "slash_victim_address": None,
            "payer_wallet_address": "0xabc123",
            "beneficiary_wallet_address": "0xabc123",
            "anomaly_signal": "none",
            "slash_mode": "none",
        },
        payment_gateway=StubGateway(
            settlement=PaymentSettlement(
                payment_ref="x402:pay_demo",
                payer_wallet_address="0xabc123",
                route_category="general",
                route_confidence=0.9,
                price_usdc=0.001,
            )
        ),
        bond_balance_reader=lambda: 100.0,
        now_factory=lambda: FIXED_NOW,
    )

    response = service.process_message(
        message="hello",
        user_id="user_1",
        user_wallet_address="0xabc123",
        payment_challenge_token="challenge-token",
        payment_proof={
            "proof_token": "challenge-token",
            "payer_wallet_address": "0xabc123",
            "facilitator_tx_ref": "demo-ref",
        },
    )

    assert response.payment_status == "settled"
    assert response.timestamp == FIXED_NOW
    assert response.payment_ref == "0xpaydemo"
    assert response.payer_wallet_address == "0xabc123"
    assert response.beneficiary_wallet_address == "0xabc123"
