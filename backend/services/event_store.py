from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from threading import Lock
from typing import Any


class EventStore:
    def __init__(self) -> None:
        self._events: list[dict[str, Any]] = []
        self._lock = Lock()

    def add_event(self, event: dict) -> None:
        normalized = deepcopy(event)
        timestamp = normalized.get("timestamp")
        if isinstance(timestamp, str):
            normalized["timestamp"] = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        with self._lock:
            self._events.append(normalized)

    def list_events(self) -> list[dict]:
        with self._lock:
            events = deepcopy(self._events)
        return sorted(events, key=self._event_timestamp, reverse=True)

    def count_paid_requests(self) -> int:
        return sum(1 for event in self.list_events() if event.get("type") == "request_paid")

    def get_route_metrics(self) -> dict[str, int]:
        metrics = {"general": 0, "technical": 0, "legal": 0, "fallback": 0}
        for event in self.list_events():
            if event.get("type") != "request_paid":
                continue
            route = event.get("route_category")
            if route in metrics:
                metrics[route] += 1
        return metrics

    def get_settlement_metrics(self) -> dict[str, float | int]:
        metrics = {"authorized": 0, "settled": 0, "failed": 0, "total_volume_usdc": 0.0}
        for event in self.list_events():
            if event.get("type") != "request_paid":
                continue
            status = event.get("status")
            amount = float(event.get("amount", 0.0))
            if status in ("authorized", "settled", "failed"):
                metrics[status] += 1
                metrics["total_volume_usdc"] += amount
        metrics["total_volume_usdc"] = round(metrics["total_volume_usdc"], 6)
        return metrics

    def get_anomaly_metrics(self) -> dict[str, float | int]:
        metrics = {"flagged_requests": 0, "slashes": 0, "total_slashed_usdc": 0.0}
        for event in self.list_events():
            if event.get("type") == "request_paid" and event.get("flagged"):
                metrics["flagged_requests"] += 1
            elif event.get("type") == "anomaly_flagged":
                metrics["flagged_requests"] += 1
            elif event.get("type") == "bond_slashed":
                metrics["slashes"] += 1
                metrics["total_slashed_usdc"] += float(event.get("amount", 0.0))
        metrics["total_slashed_usdc"] = round(metrics["total_slashed_usdc"], 6)
        return metrics

    @staticmethod
    def _event_timestamp(event: dict) -> datetime:
        timestamp = event.get("timestamp")
        if isinstance(timestamp, datetime):
            return timestamp
        if isinstance(timestamp, str):
            return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        raise ValueError("Event timestamp must be a datetime or ISO 8601 string")
