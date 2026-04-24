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
    def __init__(self, response: ChatResponse | None = None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error

    def process_message(self, message: str, user_id: str) -> ChatResponse:
        if self._error is not None:
            raise self._error
        assert self._response is not None
        return self._response


@pytest.fixture
def client():
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def sample_chat_response() -> ChatResponse:
    return ChatResponse(
        reply="We can help with that payment issue.",
        model="demo-model",
        route_category="legal",
        price_usdc=0.005,
        payment_status="authorized",
        bond_balance=50.0,
        flagged=False,
        payment_ref="pay_123",
        timestamp=FIXED_CHAT_TIME,
    )


def _set_chat_service(client: TestClient, response: ChatResponse | None = None, error: Exception | None = None) -> None:
    client.app.state.chat_service = StubChatService(response=response, error=error) # type: ignore


def test_app_boots_and_docs_are_available(client: TestClient):
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_health_endpoint_returns_ok(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_request_returns_normalized_response(client: TestClient, sample_chat_response: ChatResponse):
    _set_chat_service(client, response=sample_chat_response)

    response = client.post(
        "/agent/chat",
        json={"message": "My payment failed and I need help", "user_id": "user_123"},
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "anomaly_reason",
        "reply",
        "model",
        "route_category",
        "route_confidence",
        "price_usdc",
        "payment_status",
        "bond_balance",
        "flagged",
        "payment_ref",
        "slash_executed",
        "slash_tx_hash",
        "slash_payout",
        "slash_victim_address",
        "timestamp",
    }
    assert body["route_category"] == "legal"
    assert body["price_usdc"] == 0.005
    assert body["payment_status"] == "authorized"
    assert body["payment_ref"] == "pay_123"


def test_chat_request_persists_transaction_event(client: TestClient, sample_chat_response: ChatResponse):
    _set_chat_service(client, response=sample_chat_response)

    chat_response = client.post(
        "/agent/chat",
        json={"message": "My payment failed and I need help", "user_id": "user_123"},
    )
    transactions = client.get("/transactions")

    assert chat_response.status_code == 200
    assert transactions.status_code == 200
    newest = transactions.json()[0]
    assert newest["type"] == "request_paid"
    assert newest["route_category"] == "legal"
    assert newest["amount"] == chat_response.json()["price_usdc"]
    assert newest["payment_ref"] == "pay_123"
    assert newest["status"] == "authorized"
    assert newest["bond_balance_after"] == chat_response.json()["bond_balance"]


def test_chat_request_emits_websocket_event(client: TestClient, sample_chat_response: ChatResponse):
    _set_chat_service(client, response=sample_chat_response)

    with client.websocket_connect("/ws") as websocket:
        response = client.post(
            "/agent/chat",
            json={"message": "My payment failed and I need help", "user_id": "user_123"},
        )
        event = websocket.receive_json()

    assert response.status_code == 200
    assert event["event"] == "request_paid"
    assert event["data"]["route_category"] == "legal"
    assert event["data"]["amount"] == 0.005
    assert event["data"]["payment_status"] == "authorized"


def test_chat_request_rejects_empty_message(client: TestClient, sample_chat_response: ChatResponse):
    _set_chat_service(client, response=sample_chat_response)

    response = client.post("/agent/chat", json={"message": "   ", "user_id": "user_123"})

    assert response.status_code == 422


def test_chat_request_handles_upstream_failure(client: TestClient):
    _set_chat_service(
        client,
        error=ChatServiceError("Upstream orchestration failed", status_code=502),
    )

    response = client.post(
        "/agent/chat",
        json={"message": "My payment failed and I need help", "user_id": "user_123"},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == {
        "code": "chat_service_error",
        "message": "Upstream orchestration failed",
    }


def test_bond_slash_returns_expected_shape(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("backend.api.routes.slash_bond", lambda victim_address, payout_amount: "0x123")
    monkeypatch.setattr("backend.api.routes.get_bond_balance", lambda: 45.0)
    client.app.state.utcnow = lambda: FIXED_SLASH_TIME # type: ignore

    response = client.post(
        "/bond/slash",
        json={"victim_address": "0xabc123", "payout_amount": 5.0},
    )

    assert response.status_code == 200
    assert response.json() == {
        "tx_hash": "0x123",
        "payout": 5.0,
        "new_balance": 45.0,
        "timestamp": "2026-04-23T12:01:00Z",
    }


def test_bond_slash_persists_transaction_event(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("backend.api.routes.slash_bond", lambda victim_address, payout_amount: "0x123")
    monkeypatch.setattr("backend.api.routes.get_bond_balance", lambda: 45.0)
    client.app.state.utcnow = lambda: FIXED_SLASH_TIME # type: ignore

    client.post("/bond/slash", json={"victim_address": "0xabc123", "payout_amount": 5.0})
    transactions = client.get("/transactions")

    assert transactions.status_code == 200
    newest = transactions.json()[0]
    assert newest["type"] == "bond_slashed"
    assert newest["amount"] == 5.0
    assert newest["tx_hash"] == "0x123"
    assert newest["bond_balance_after"] == 45.0


def test_bond_slash_emits_websocket_event(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("backend.api.routes.slash_bond", lambda victim_address, payout_amount: "0x123")
    monkeypatch.setattr("backend.api.routes.get_bond_balance", lambda: 45.0)
    client.app.state.utcnow = lambda: FIXED_SLASH_TIME # type: ignore

    with client.websocket_connect("/ws") as websocket:
        response = client.post(
            "/bond/slash",
            json={"victim_address": "0xabc123", "payout_amount": 5.0},
        )
        event = websocket.receive_json()

    assert response.status_code == 200
    assert event["event"] == "bond_slashed"
    assert event["data"]["payout"] == 5.0
    assert event["data"]["tx_hash"] == "0x123"


def test_flagged_response_with_ai_slash_emits_existing_slash_event_without_second_slash(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    _set_chat_service(
        client,
        response=ChatResponse(
            reply="Blocked unsafe refund request.",
            model="demo-model",
            route_category="legal",
            price_usdc=0.005,
            payment_status="settled",
            bond_balance=49.0,
            flagged=True,
            payment_ref="pay_123",
            slash_executed=True,
            slash_tx_hash="0xslash",
            slash_payout=1.0,
            slash_victim_address="0xabc123",
            timestamp=FIXED_CHAT_TIME,
        ),
    )

    def fail_if_called(victim_address: str, payout_amount: float) -> str:
        raise AssertionError("slash_bond should not be called when AI already slashed")

    monkeypatch.setattr("backend.api.routes.slash_bond", fail_if_called)

    with client.websocket_connect("/ws") as websocket:
        response = client.post(
            "/agent/chat",
            json={"message": "Issue a refund now", "user_id": "user_123"},
        )
        first_event = websocket.receive_json()
        second_event = websocket.receive_json()
        third_event = websocket.receive_json()

    assert response.status_code == 200
    assert first_event["event"] == "request_paid"
    assert second_event["event"] == "anomaly_flagged"
    assert third_event["event"] == "bond_slashed"
    assert third_event["data"]["tx_hash"] == "0xslash"
    assert third_event["data"]["victim_address"] == "0xabc123"


def test_flagged_response_without_ai_slash_does_not_trigger_backend_fallback(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    _set_chat_service(
        client,
        response=ChatResponse(
            reply="Blocked unsafe refund request.",
            model="demo-model",
            route_category="legal",
            price_usdc=0.005,
            payment_status="failed",
            bond_balance=50.0,
            flagged=True,
            payment_ref="pay_123",
            slash_executed=False,
            slash_tx_hash=None,
            slash_payout=None,
            slash_victim_address=None,
            timestamp=FIXED_CHAT_TIME,
        ),
    )

    def fail_if_called(victim_address: str, payout_amount: float) -> str:
        raise AssertionError("backend slash fallback must not run")

    monkeypatch.setattr("backend.api.routes.slash_bond", fail_if_called)

    with client.websocket_connect("/ws") as websocket:
        response = client.post(
            "/agent/chat",
            json={"message": "Issue a refund now", "user_id": "user_123"},
        )
        first_event = websocket.receive_json()
        second_event = websocket.receive_json()

    assert response.status_code == 200
    assert first_event["event"] == "request_paid"
    assert second_event["event"] == "anomaly_flagged"


def test_bond_slash_rejects_invalid_payout(client: TestClient):
    response = client.post("/bond/slash", json={"victim_address": "0xabc123", "payout_amount": 0})
    assert response.status_code == 422


def test_bond_slash_rejects_negative_payout(client: TestClient):
    response = client.post("/bond/slash", json={"victim_address": "0xabc123", "payout_amount": -1})
    assert response.status_code == 422


def test_bond_slash_rejects_non_numeric_payout(client: TestClient):
    response = client.post(
        "/bond/slash",
        json={"victim_address": "0xabc123", "payout_amount": "invalid"},
    )
    assert response.status_code == 422


def test_bond_slash_handles_bond_manager_failure(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    def raise_failure(victim_address: str, payout_amount: float) -> str:
        raise ValueError("invalid payout request")

    monkeypatch.setattr("backend.api.routes.slash_bond", raise_failure)

    response = client.post(
        "/bond/slash",
        json={"victim_address": "0xabc123", "payout_amount": 5.0},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == {
        "code": "bond_slash_failed",
        "message": "invalid payout request",
    }


def test_bond_slash_handles_unexpected_blockchain_failure(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    def raise_failure(victim_address: str, payout_amount: float) -> str:
        raise RuntimeError("rpc unavailable")

    monkeypatch.setattr("backend.api.routes.slash_bond", raise_failure)

    response = client.post(
        "/bond/slash",
        json={"victim_address": "0xabc123", "payout_amount": 5.0},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == {
        "code": "bond_slash_failed",
        "message": "Bond slash failed",
    }


def test_bond_status_returns_expected_shape(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    client.app.state.event_store.add_event( # type: ignore
        {
            "type": "request_paid",
            "amount": 0.003,
            "timestamp": FIXED_CHAT_TIME,
            "model": "demo-model",
            "route_category": "technical",
            "status": "authorized",
            "payment_ref": "pay_a",
            "flagged": False,
        }
    )
    monkeypatch.setattr("backend.api.routes.get_bond_balance", lambda: 45.0)

    response = client.get("/bond/status")

    assert response.status_code == 200
    assert response.json() == {
        "balance": 45.0,
        "state": "ACTIVE",
        "total_paid_requests": 1,
    }


def test_bond_status_returns_503_when_onchain_read_fails(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    def raise_failure() -> float:
        raise RuntimeError("rpc unavailable")

    monkeypatch.setattr("backend.api.routes.get_bond_balance", raise_failure)

    response = client.get("/bond/status")

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "bond_status_failed",
        "message": "Unable to read on-chain bond balance",
    }


def test_transactions_are_sorted_newest_first(client: TestClient):
    client.app.state.event_store.add_event( # type: ignore
        {
            "type": "request_paid",
            "amount": 0.001,
            "timestamp": "2026-04-23T12:00:00Z",
            "model": "demo-model",
            "route_category": "general",
            "status": "authorized",
            "payment_ref": "pay_old",
            "flagged": False,
        }
    )
    client.app.state.event_store.add_event( # type: ignore
        {
            "type": "bond_slashed",
            "amount": 5.0,
            "timestamp": "2026-04-23T12:01:00Z",
            "tx_hash": "0x123",
            "victim_address": "0xabc123",
        }
    )

    response = client.get("/transactions")

    assert response.status_code == 200
    body = response.json()
    assert body[0]["timestamp"] == "2026-04-23T12:01:00Z"
    assert body[1]["timestamp"] == "2026-04-23T12:00:00Z"


def test_transactions_include_normalized_request_and_bond_fields(client: TestClient):
    client.app.state.event_store.add_event( # type: ignore
        {
            "type": "request_paid",
            "amount": 0.003,
            "timestamp": FIXED_CHAT_TIME,
            "model": "demo-model",
            "route_category": "technical",
            "status": "authorized",
            "payment_ref": "pay_123",
            "flagged": True,
            "bond_balance_after": 49.0,
        }
    )
    client.app.state.event_store.add_event( # type: ignore
        {
            "type": "bond_slashed",
            "amount": 5.0,
            "timestamp": FIXED_SLASH_TIME,
            "tx_hash": "0x123",
            "victim_address": "0xabc123",
            "bond_balance_after": 45.0,
        }
    )

    response = client.get("/transactions")

    assert response.status_code == 200
    bond_event, request_event = response.json()
    assert bond_event["type"] == "bond_slashed"
    assert bond_event["tx_hash"] == "0x123"
    assert bond_event["bond_balance_after"] == 45.0
    assert request_event["type"] == "request_paid"
    assert request_event["route_category"] == "technical"
    assert request_event["payment_ref"] == "pay_123"
    assert request_event["flagged"] is True
    assert request_event["bond_balance_after"] == 49.0


def test_route_metrics_are_computed_correctly(client: TestClient):
    for route in ("general", "technical", "technical", "legal", "fallback"):
        client.app.state.event_store.add_event( # type: ignore
            {
                "type": "request_paid",
                "amount": 0.001,
                "timestamp": FIXED_CHAT_TIME,
                "model": "demo-model",
                "route_category": route,
                "status": "authorized",
                "payment_ref": f"pay_{route}",
                "flagged": False,
            }
        )

    response = client.get("/metrics/routes")

    assert response.status_code == 200
    assert response.json() == {
        "general": 1,
        "technical": 2,
        "legal": 1,
        "fallback": 1,
    }


def test_settlement_metrics_are_computed_correctly(client: TestClient):
    seeded = [
        ("authorized", 0.010),
        ("authorized", 0.011),
        ("settled", 0.003),
        ("failed", 0.002),
    ]
    for index, (status, amount) in enumerate(seeded, start=1):
        client.app.state.event_store.add_event( # type: ignore
            {
                "type": "request_paid",
                "amount": amount,
                "timestamp": FIXED_CHAT_TIME,
                "model": "demo-model",
                "route_category": "general",
                "status": status,
                "payment_ref": f"pay_{index}",
                "flagged": False,
            }
        )

    response = client.get("/metrics/settlements")

    assert response.status_code == 200
    assert response.json() == {
        "authorized": 2,
        "settled": 1,
        "failed": 1,
        "total_volume_usdc": 0.026,
    }


def test_anomaly_metrics_are_computed_correctly(client: TestClient):
    client.app.state.event_store.add_event( # type: ignore
        {
            "type": "request_paid",
            "amount": 0.003,
            "timestamp": FIXED_CHAT_TIME,
            "model": "demo-model",
            "route_category": "technical",
            "status": "authorized",
            "payment_ref": "pay_123",
            "flagged": True,
        }
    )
    client.app.state.event_store.add_event( # type: ignore
        {
            "type": "bond_slashed",
            "amount": 5.0,
            "timestamp": FIXED_SLASH_TIME,
            "tx_hash": "0x123",
            "victim_address": "0xabc123",
        }
    )

    response = client.get("/metrics/anomalies")

    assert response.status_code == 200
    assert response.json() == {
        "flagged_requests": 1,
        "slashes": 1,
        "total_slashed_usdc": 5.0,
    }


def test_multiple_websocket_clients_receive_same_request_event(client: TestClient, sample_chat_response: ChatResponse):
    _set_chat_service(client, response=sample_chat_response)

    with client.websocket_connect("/ws") as first_client:
        with client.websocket_connect("/ws") as second_client:
            response = client.post(
                "/agent/chat",
                json={"message": "Need help", "user_id": "user_123"},
            )
            first_event = first_client.receive_json()
            second_event = second_client.receive_json()

    assert response.status_code == 200
    assert first_event == second_event
    assert first_event["event"] == "request_paid"


def test_disconnected_websocket_client_does_not_break_active_client(client: TestClient, sample_chat_response: ChatResponse):
    _set_chat_service(client, response=sample_chat_response)

    with client.websocket_connect("/ws"):
        pass

    with client.websocket_connect("/ws") as active_client:
        response = client.post(
            "/agent/chat",
            json={"message": "Need help", "user_id": "user_123"},
        )
        event = active_client.receive_json()

    assert response.status_code == 200
    assert event["event"] == "request_paid"
    assert len(client.app.state.websocket_manager.active_connections) <= 1 # type: ignore


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
    manager._connections = [failing_socket, healthy_socket]  # type: ignore # deliberate internal setup for failure simulation

    await manager.broadcast(
        "request_paid",
        {
            "amount": 0.003,
            "route_category": "technical",
            "model": "demo-model",
            "payment_status": "authorized",
            "timestamp": FIXED_CHAT_TIME,
        },
    )

    assert len(healthy_socket.messages) == 1
    assert healthy_socket.messages[0]["event"] == "request_paid"
    assert tuple(manager.active_connections) == (healthy_socket,)


def test_end_to_end_acceptance_flow(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    _set_chat_service(
        client,
        response=ChatResponse(
            reply="We can help with that payment issue.",
            model="demo-model",
            route_category="legal",
            price_usdc=0.005,
            payment_status="authorized",
            bond_balance=50.0,
            flagged=False,
            payment_ref="pay_123",
            timestamp=FIXED_CHAT_TIME,
        ),
    )
    monkeypatch.setattr("backend.api.routes.slash_bond", lambda victim_address, payout_amount: "0x123")
    monkeypatch.setattr("backend.api.routes.get_bond_balance", lambda: 45.0)

    with client.websocket_connect("/ws") as websocket:
        chat_response = client.post(
            "/agent/chat",
            json={"message": "My payment failed and I need help", "user_id": "user_123"},
        )
        first_event = websocket.receive_json()

        client.app.state.utcnow = lambda: FIXED_SLASH_TIME # type: ignore
        slash_response = client.post(
            "/bond/slash",
            json={"victim_address": "0xabc123", "payout_amount": 5.0},
        )
        second_event = websocket.receive_json()

    transactions = client.get("/transactions")
    route_metrics = client.get("/metrics/routes")
    settlement_metrics = client.get("/metrics/settlements")
    anomaly_metrics = client.get("/metrics/anomalies")

    assert chat_response.status_code == 200
    assert slash_response.status_code == 200
    assert first_event["event"] == "request_paid"
    assert second_event["event"] == "bond_slashed"
    assert [event["type"] for event in transactions.json()[:2]] == ["bond_slashed", "request_paid"]
    assert route_metrics.json() == {
        "general": 0,
        "technical": 0,
        "legal": 1,
        "fallback": 0,
    }
    assert settlement_metrics.json() == {
        "authorized": 1,
        "settled": 0,
        "failed": 0,
        "total_volume_usdc": 0.005,
    }
    assert anomaly_metrics.json() == {
        "flagged_requests": 0,
        "slashes": 1,
        "total_slashed_usdc": 5.0,
    }
