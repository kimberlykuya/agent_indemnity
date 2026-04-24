from __future__ import annotations

import logging
import os
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


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_positive_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if value <= 0:
        return default
    return value


def _auto_slash_config() -> dict[str, bool | float | str]:
    return {
        "enabled": _env_bool("AUTO_SLASH_ON_FLAGGED", True),
        "victim_address": (
            os.getenv("AUTO_SLASH_VICTIM_ADDRESS")
            or os.getenv("VICTIM_WALLET_ADDRESS")
            or ""
        ),
        "payout_usdc": _env_positive_float(
            "AUTO_SLASH_PAYOUT_USDC",
            _env_positive_float("SLASH_PAYOUT_USDC", 1.0),
        ),
        "min_payout_usdc": _env_positive_float("AUTO_SLASH_MIN_PAYOUT_USDC", 0.01),
    }


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
        await _auto_slash_if_flagged(request, response)

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


async def _auto_slash_if_flagged(request: Request, response: ChatResponse) -> None:
    if not response.flagged:
        return

    cfg = _auto_slash_config()
    if not bool(cfg["enabled"]):
        return

    victim_address = str(cfg["victim_address"])
    if not victim_address:
        logger.warning("AUTO_SLASH_ON_FLAGGED is enabled but no victim address is configured")
        return

    requested_payout = float(cfg["payout_usdc"])
    min_payout = float(cfg["min_payout_usdc"])
    available_bond = max(float(response.bond_balance), 0.0)
    payout = min(requested_payout, available_bond)
    if payout < min_payout:
        logger.info(
            "Skipping auto slash: payout below minimum threshold "
            "(payout=%s min=%s available=%s)",
            payout,
            min_payout,
            available_bond,
        )
        return

    try:
        slash_response = await run_in_threadpool(
            _perform_bond_slash,
            victim_address=victim_address,
            payout_amount=payout,
            timestamp=_utcnow(request),
        )
    except BondOperationError:
        logger.exception("Auto slash failed for flagged response")
        return
    except Exception:
        logger.exception("Unexpected auto slash failure")
        return

    await _emit_bond_slashed_event(
        request,
        victim_address=victim_address,
        response=slash_response,
    )
    response.bond_balance = slash_response.new_balance


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
    balance = await run_in_threadpool(get_bond_balance)
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
