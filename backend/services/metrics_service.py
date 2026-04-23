from __future__ import annotations

from backend.services.event_store import EventStore


class MetricsService:
    def __init__(self, event_store: EventStore) -> None:
        self._event_store = event_store

    def get_route_metrics(self) -> dict[str, int]:
        return self._event_store.get_route_metrics()

    def get_settlement_metrics(self) -> dict[str, float | int]:
        return self._event_store.get_settlement_metrics()

    def get_anomaly_metrics(self) -> dict[str, float | int]:
        return self._event_store.get_anomaly_metrics()
