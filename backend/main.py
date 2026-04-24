from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.agent import config
from backend.api.routes import router
from backend.api.websocket_manager import WebSocketManager
from backend.services.chat_service import ChatService
from backend.services.event_store import EventStore
from backend.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.validate_config()
    logger.info("Loaded model configuration from root .env: %s", config.get_model_config())
    event_store = EventStore()
    app.state.event_store = event_store
    app.state.websocket_manager = WebSocketManager()
    app.state.chat_service = ChatService()
    app.state.metrics_service = MetricsService(event_store)
    app.state.utcnow = lambda: datetime.now(timezone.utc)
    yield


def create_app() -> FastAPI:
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
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    return app


app = create_app()
