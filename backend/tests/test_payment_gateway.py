from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.services.payment_gateway import PaymentGateway, PaymentGatewayError


FIXED_NOW = datetime(2026, 4, 24, 8, 0, 0, tzinfo=timezone.utc)


def test_invalid_facilitator_url_raises_clean_gateway_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAYMENT_GATEWAY_MODE", "facilitator")
    monkeypatch.setenv("X402_FACILITATOR_URL", "https://...")

    gateway = PaymentGateway(now_factory=lambda: FIXED_NOW)
    challenge = gateway.create_challenge(
        message="hello",
        user_id="user_1",
        user_wallet_address="0xabc123",
        route_category="general",
        route_confidence=0.9,
        price_usdc=0.001,
    )

    with pytest.raises(PaymentGatewayError) as exc_info:
        gateway.verify_payment(
            message="hello",
            user_id="user_1",
            user_wallet_address="0xabc123",
            challenge_token=challenge.token,
            payment_proof={
                "proof_token": challenge.token,
                "payer_wallet_address": "0xabc123",
                "facilitator_tx_ref": "demo-ref",
            },
        )

    assert exc_info.value.code == "payment_gateway_misconfigured"
    assert exc_info.value.status_code == 500
    assert "valid HTTP(S) URL" in exc_info.value.message
