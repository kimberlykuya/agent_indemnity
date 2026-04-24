from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.services.chat_service import ChatService, ChatServiceError


FIXED_NOW = datetime(2026, 4, 24, 8, 0, 0, tzinfo=timezone.utc)


def test_process_message_raises_on_provider_error() -> None:
    service = ChatService(
        orchestrator=lambda message, user_id: {
            "reply": "Temporary failure",
            "model": "demo-model",
            "route_category": "general",
            "price_usdc": 0.001,
            "payment_status": "provider_error",
            "flagged": False,
            "payment_ref": "pay_demo",
        },
        bond_balance_reader=lambda: 100.0,
        now_factory=lambda: FIXED_NOW,
    )

    with pytest.raises(ChatServiceError) as exc_info:
        service.process_message("hello", "user_1")

    assert exc_info.value.status_code == 502
    assert exc_info.value.code == "provider_unavailable"
    assert exc_info.value.message == "Upstream provider unavailable"


def test_process_message_normalizes_payment_failure_without_raising() -> None:
    service = ChatService(
        orchestrator=lambda message, user_id: {
            "reply": "Processed",
            "model": "demo-model",
            "route_category": "general",
            "price_usdc": 0.001,
            "payment_status": "payment_failed",
            "flagged": False,
            "payment_ref": "pay_demo",
        },
        bond_balance_reader=lambda: 100.0,
        now_factory=lambda: FIXED_NOW,
    )

    response = service.process_message("hello", "user_1")

    assert response.payment_status == "failed"
    assert response.timestamp == FIXED_NOW


def test_process_message_raises_when_payment_reference_is_missing() -> None:
    service = ChatService(
        orchestrator=lambda message, user_id: {
            "reply": "Processed",
            "model": "demo-model",
            "route_category": "general",
            "price_usdc": 0.001,
            "payment_status": "settled",
            "flagged": False,
        },
        bond_balance_reader=lambda: 100.0,
        now_factory=lambda: FIXED_NOW,
    )

    with pytest.raises(ChatServiceError) as exc_info:
        service.process_message("hello", "user_1")

    assert exc_info.value.status_code == 500
    assert exc_info.value.message == "Chat service returned an incomplete response"


def test_process_message_raises_settlement_failed_with_underlying_error() -> None:
    service = ChatService(
        orchestrator=lambda message, user_id: {
            "reply": "Processed",
            "model": "demo-model",
            "route_category": "general",
            "price_usdc": 0.001,
            "payment_status": "payment_failed",
            "payment_error": "{'code': -32003, 'message': 'txpool is full'}",
            "flagged": False,
        },
        bond_balance_reader=lambda: 100.0,
        now_factory=lambda: FIXED_NOW,
    )

    with pytest.raises(ChatServiceError) as exc_info:
        service.process_message("hello", "user_1")

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "settlement_failed"
    assert "txpool is full" in exc_info.value.message
