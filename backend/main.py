from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from backend.agent import config
    from backend.api.routes import router
    from backend.api.websocket_manager import WebSocketManager
    from backend.services.chat_service import ChatService
    from backend.services.event_store import EventStore
    from backend.services.metrics_service import MetricsService
    from backend.services.payment_gateway import PaymentGateway
except ImportError:  # pragma: no cover - Railway root_directory="backend" fallback
    from agent import config
    from api.routes import router
    from api.websocket_manager import WebSocketManager
    from services.chat_service import ChatService
    from services.event_store import EventStore
    from services.metrics_service import MetricsService
    from services.payment_gateway import PaymentGateway

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.validate_config()
    logger.info("Loaded model configuration from root .env: %s", config.get_model_config())
    event_store = EventStore()
    app.state.event_store = event_store
    app.state.websocket_manager = WebSocketManager()
    app.state.payment_gateway = PaymentGateway()
    app.state.chat_service = ChatService(payment_gateway=app.state.payment_gateway)
    app.state.metrics_service = MetricsService(event_store)
    app.state.utcnow = lambda: datetime.now(timezone.utc)
    yield


def create_app() -> FastAPI:
    frontend_origin = os.getenv("FRONTEND_ORIGIN", "https://agent-indemnity.vercel.app")
    extra_frontend_origins = [
        origin.strip()
        for origin in os.getenv("FRONTEND_ORIGINS", "").split(",")
        if origin.strip()
    ]

    app = FastAPI(
        title="Agent Indemnity API",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            frontend_origin,
            *extra_frontend_origins,
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    return app


app = create_app()
