from __future__ import annotations

import asyncio

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

from .schemas import WebSocketEvent


class WebSocketManager:
    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    @property
    def active_connections(self) -> tuple[WebSocket, ...]:
        return tuple(self._connections)

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        try:
            self._connections.remove(websocket)
        except ValueError:
            return

    async def broadcast(self, event_name: str, data: dict) -> None:
        envelope = jsonable_encoder(
            WebSocketEvent(event=event_name, data=data).model_dump(mode="json")
        )
        async with self._lock:
            connections = list(self._connections)

        stale_connections: list[WebSocket] = []
        for websocket in connections:
            try:
                await websocket.send_json(envelope)
            except Exception:
                stale_connections.append(websocket)

        if stale_connections:
            async with self._lock:
                for websocket in stale_connections:
                    self.disconnect(websocket)
