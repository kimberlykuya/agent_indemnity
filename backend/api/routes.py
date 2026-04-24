from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from .schemas import (
    AnomalyMetricsResponse,
    BondStatusResponse,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    RouteMetricsResponse,
    SettlementMetricsResponse,
    SlashRequest,
    SlashResponse,
    TransactionRecord,
)

try:
    from backend.blockchain.bond_manager import get_bond_balance, slash_bond
except ImportError:  # pragma: no cover - compatibility fallback
    from blockchain.bond_manager import get_bond_balance, slash_bond

try:
    from backend.services.chat_service import ChatServiceError
except ImportError:  # pragma: no cover - compatibility fallback
    from services.chat_service import ChatServiceError

logger = logging.getLogger(__name__)

router = APIRouter()


class BondOperationError(RuntimeError):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})
def _utcnow(request: Request) -> datetime:
    now_factory = getattr(request.app.state, "utcnow", None)
    if callable(now_factory):
        return now_factory()
    return datetime.now(timezone.utc)


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/agent/chat", response_model=ChatResponse)
async def post_agent_chat(request: Request, payload: ChatRequest) -> ChatResponse:
    try:
        response = await run_in_threadpool(
            request.app.state.chat_service.process_message,
            message=payload.message,
            user_id=payload.user_id,
        )
    except ChatServiceError as exc:
        logger.exception("Chat service failed")
        raise _http_error(exc.status_code, exc.code, exc.message) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected chat failure")
        raise _http_error(500, "internal_error", "Unexpected server error") from exc

    event = TransactionRecord(
        type="request_paid",
        amount=response.price_usdc,
        timestamp=response.timestamp,
        bond_balance_after=response.bond_balance,
        model=response.model,
        route_category=response.route_category,
        status=response.payment_status,
        payment_ref=response.payment_ref,
        flagged=response.flagged,
    )
    request.app.state.event_store.add_event(event.model_dump())

    await request.app.state.websocket_manager.broadcast(
        "request_paid",
        {
            "amount": response.price_usdc,
            "route_category": response.route_category,
            "model": response.model,
            "payment_status": response.payment_status,
            "payment_ref": response.payment_ref,
            "flagged": response.flagged,
            "timestamp": response.timestamp,
            "bond_balance": response.bond_balance,
        },
    )

    if response.flagged:
        await request.app.state.websocket_manager.broadcast(
            "anomaly_flagged",
            {
                "route_category": response.route_category,
                "payment_ref": response.payment_ref,
                "timestamp": response.timestamp,
            },
        )
        if response.slash_executed and response.slash_tx_hash and response.slash_payout is not None:
            await _emit_bond_slashed_event(
                request,
                victim_address=response.slash_victim_address or "",
                response=SlashResponse(
                    tx_hash=response.slash_tx_hash,
                    payout=response.slash_payout,
                    new_balance=response.bond_balance,
                    timestamp=response.timestamp,
                ),
            )

    return response


def _perform_bond_slash(victim_address: str, payout_amount: float, timestamp: datetime) -> SlashResponse:
    try:
        tx_hash = slash_bond(victim_address, payout_amount)
        new_balance = get_bond_balance()
    except ValueError as exc:
        raise BondOperationError(str(exc), status_code=400) from exc
    except Exception as exc:
        raise BondOperationError("Bond slash failed", status_code=500) from exc

    return SlashResponse(
        tx_hash=tx_hash,
        payout=payout_amount,
        new_balance=new_balance,
        timestamp=timestamp,
    )


async def _emit_bond_slashed_event(
    request: Request,
    *,
    victim_address: str,
    response: SlashResponse,
) -> None:
    event = TransactionRecord(
        type="bond_slashed",
        amount=response.payout,
        timestamp=response.timestamp,
        bond_balance_after=response.new_balance,
        tx_hash=response.tx_hash,
        victim_address=victim_address,
    )
    request.app.state.event_store.add_event(event.model_dump())

    await request.app.state.websocket_manager.broadcast(
        "bond_slashed",
        {
            "payout": response.payout,
            "new_balance": response.new_balance,
            "tx_hash": response.tx_hash,
            "victim_address": victim_address,
            "timestamp": response.timestamp,
        },
    )


@router.post("/bond/slash", response_model=SlashResponse)
async def post_bond_slash(request: Request, payload: SlashRequest) -> SlashResponse:
    try:
        response = await run_in_threadpool(
            _perform_bond_slash,
            victim_address=payload.victim_address,
            payout_amount=payload.payout_amount,
            timestamp=_utcnow(request),
        )
    except BondOperationError as exc:
        logger.exception("Bond slash failed")
        raise _http_error(exc.status_code, "bond_slash_failed", exc.message) from exc
    except Exception as exc:  # pragma: no cover - safety net
        logger.exception("Unexpected bond slash failure")
        raise _http_error(500, "internal_error", "Unexpected server error") from exc

    await _emit_bond_slashed_event(
        request,
        victim_address=payload.victim_address,
        response=response,
    )
    return response


@router.get("/bond/status", response_model=BondStatusResponse)
async def get_bond_status(request: Request) -> BondStatusResponse:
    try:
        balance = await run_in_threadpool(get_bond_balance)
    except Exception as exc:
        logger.exception("Bond status read failed")
        raise _http_error(503, "bond_status_failed", "Unable to read on-chain bond balance") from exc
    return BondStatusResponse(
        balance=balance,
        state="ACTIVE" if balance > 0 else "DEPLETED",
        total_paid_requests=request.app.state.event_store.count_paid_requests(),
    )


@router.get("/transactions", response_model=list[TransactionRecord])
async def get_transactions(request: Request) -> list[TransactionRecord]:
    return [
        TransactionRecord.model_validate(event)
        for event in request.app.state.event_store.list_events()
    ]


@router.get("/metrics/routes", response_model=RouteMetricsResponse)
async def get_route_metrics(request: Request) -> RouteMetricsResponse:
    return RouteMetricsResponse(**request.app.state.metrics_service.get_route_metrics())


@router.get("/metrics/settlements", response_model=SettlementMetricsResponse)
async def get_settlement_metrics(request: Request) -> SettlementMetricsResponse:
    return SettlementMetricsResponse(**request.app.state.metrics_service.get_settlement_metrics())


@router.get("/metrics/anomalies", response_model=AnomalyMetricsResponse)
async def get_anomaly_metrics(request: Request) -> AnomalyMetricsResponse:
    return AnomalyMetricsResponse(**request.app.state.metrics_service.get_anomaly_metrics())


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    manager = websocket.app.state.websocket_manager
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
