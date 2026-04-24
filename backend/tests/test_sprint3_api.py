from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.api.schemas import ChatResponse
from backend.api.websocket_manager import WebSocketManager
from backend.main import create_app
from backend.services.chat_service import ChatServiceError

FIXED_CHAT_TIME = datetime(2026, 4, 23, 12, 0, 0, tzinfo=timezone.utc)
FIXED_SLASH_TIME = datetime(2026, 4, 23, 12, 1, 0, tzinfo=timezone.utc)


class StubChatService:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error

    def process_message(self, **kwargs):
        if self._error is not None:
            raise self._error
        assert self._response is not None
        if isinstance(self._response, dict):
            return ChatResponse.model_validate(self._response)
        return self._response


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


def _set_chat_service(client: TestClient, response=None, error: Exception | None = None) -> None:
    client.app.state.chat_service = StubChatService(response=response, error=error)  # type: ignore


def test_health_endpoint_returns_ok(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_request_requires_payment_challenge(client: TestClient):
    response = client.post(
        "/agent/chat",
        json={
            "message": "My payment failed and I need help",
            "user_id": "user_123",
            "user_wallet_address": "0xabc123",
        },
    )

    assert response.status_code == 402
    body = response.json()
    assert body["kind"] == "payment_required"
    assert body["route_category"] in {"general", "technical", "legal", "fallback"}
    assert body["price_usdc"] > 0
    assert body["payment_challenge_token"]


def test_chat_request_handles_gateway_failure(client: TestClient):
    _set_chat_service(
        client,
        error=ChatServiceError("Invalid payment proof", status_code=402, code="invalid_payment_proof"),
    )

    response = client.post(
        "/agent/chat",
        json={
            "message": "My payment failed and I need help",
            "user_id": "user_123",
            "user_wallet_address": "0xabc123",
            "payment_challenge_token": "challenge",
            "payment_proof": {
                "proof_token": "challenge",
                "payer_wallet_address": "0xabc123",
                "facilitator_tx_ref": "demo-ref",
            },
        },
    )

    assert response.status_code == 402
    assert response.json()["detail"] == {
        "code": "invalid_payment_proof",
        "message": "Invalid payment proof",
    }


def test_paid_chat_request_persists_wallet_and_enforcement_metadata(client):
    _set_chat_service(
        client,
        response={
            "reply": "We can help with that payment issue.",
            "model": "demo-model",
            "route_category": "legal",
            "route_confidence": 0.92,
            "price_usdc": 0.005,
            "payment_status": "settled",
            "bond_balance": 50.0,
            "flagged": True,
            "payment_ref": "0xpay123",
            "anomaly_reason": "Embedding similarity matched an unauthorized refund or payout request",
            "slash_executed": True,
            "slash_tx_hash": "0xslash",
            "slash_payout": 1.0,
            "slash_victim_address": "0xabc123",
            "payer_wallet_address": "0xabc123",
            "beneficiary_wallet_address": "0xabc123",
            "anomaly_signal": "embedding",
            "slash_mode": "auto",
            "timestamp": FIXED_CHAT_TIME,
        },
    )

    with client.websocket_connect("/ws") as websocket:
        response = client.post(
            "/agent/chat",
            json={
                "message": "Refund me immediately",
                "user_id": "user_123",
                "user_wallet_address": "0xabc123",
                "payment_challenge_token": "challenge",
                "payment_proof": {
                    "proof_token": "challenge",
                    "payer_wallet_address": "0xabc123",
                    "facilitator_tx_ref": "demo-ref",
                },
            },
        )
        first_event = websocket.receive_json()
        second_event = websocket.receive_json()
        third_event = websocket.receive_json()

    assert response.status_code == 200
    body = response.json()
    assert body["payer_wallet_address"] == "0xabc123"
    assert body["beneficiary_wallet_address"] == "0xabc123"
    assert body["anomaly_signal"] == "embedding"
    assert body["slash_mode"] == "auto"

    assert first_event["event"] == "request_paid"
    assert first_event["data"]["payer_wallet_address"] == "0xabc123"
    assert second_event["event"] == "anomaly_flagged"
    assert second_event["data"]["beneficiary_wallet_address"] == "0xabc123"
    assert third_event["event"] == "bond_slashed"
    assert third_event["data"]["beneficiary_wallet_address"] == "0xabc123"
    assert third_event["data"]["slash_mode"] == "auto"


def test_manual_bond_slash_returns_manual_metadata(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("backend.api.routes.slash_bond", lambda victim_address, payout_amount: "0x123")
    monkeypatch.setattr("backend.api.routes.get_bond_balance", lambda: 45.0)
    client.app.state.utcnow = lambda: FIXED_SLASH_TIME  # type: ignore

    response = client.post(
        "/bond/slash",
        json={"victim_address": "0xabc123", "payout_amount": 5.0},
    )

    assert response.status_code == 200
    assert response.json() == {
        "tx_hash": "0x123",
        "payout": 5.0,
        "new_balance": 45.0,
        "beneficiary_wallet_address": "0xabc123",
        "slash_mode": "manual",
        "timestamp": "2026-04-23T12:01:00Z",
    }


def test_transactions_include_wallet_metadata(client):
    client.app.state.event_store.add_event(  # type: ignore
        {
            "type": "request_paid",
            "amount": 0.003,
            "timestamp": FIXED_CHAT_TIME,
            "model": "demo-model",
            "route_category": "technical",
            "status": "settled",
            "payment_ref": "0xpay123",
            "flagged": True,
            "anomaly_reason": "rule match",
            "anomaly_signal": "rule",
            "slash_mode": "none",
            "payer_wallet_address": "0xpayer",
            "beneficiary_wallet_address": "0xbeneficiary",
        }
    )

    response = client.get("/transactions")

    assert response.status_code == 200
    event = response.json()[0]
    assert event["payer_wallet_address"] == "0xpayer"
    assert event["beneficiary_wallet_address"] == "0xbeneficiary"
    assert event["anomaly_signal"] == "rule"


@pytest.mark.asyncio
async def test_broadcast_failure_on_one_socket_does_not_break_others():
    manager = WebSocketManager()

    class HealthySocket:
        def __init__(self) -> None:
            self.messages = []

        async def send_json(self, payload):
            self.messages.append(payload)

    class FailingSocket:
        async def send_json(self, payload):
            raise RuntimeError("socket closed")

    healthy_socket = HealthySocket()
    failing_socket = FailingSocket()
    manager._connections = [failing_socket, healthy_socket]  # type: ignore

    await manager.broadcast(
        "request_paid",
        {
            "amount": 0.003,
            "route_category": "technical",
            "model": "demo-model",
            "payment_status": "settled",
            "timestamp": FIXED_CHAT_TIME,
        },
    )

    assert len(healthy_socket.messages) == 1
    assert healthy_socket.messages[0]["event"] == "request_paid"
    assert tuple(manager.active_connections) == (healthy_socket,)
