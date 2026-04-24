from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PublicRouteCategory = Literal["general", "technical", "legal", "fallback"]
SettlementStatus = Literal["authorized", "settled", "failed"]
EventName = Literal["request_paid", "bond_slashed", "bond_topped_up", "anomaly_flagged"]


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _require_non_empty(value: str, field_name: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must be non-empty")
    return stripped


def _require_non_negative_finite(value: float, field_name: str) -> float:
    if not isfinite(value) or value < 0:
        raise ValueError(f"{field_name} must be finite and non-negative")
    return value


def _require_positive_finite(value: float, field_name: str) -> float:
    if not isfinite(value) or value <= 0:
        raise ValueError(f"{field_name} must be finite and greater than zero")
    return value


class HealthResponse(APIModel):
    status: Literal["ok"]


class ChatRequest(APIModel):
    message: str = Field(..., description="Customer message")
    user_id: str = Field(..., description="Caller identifier")

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return _require_non_empty(value, "message")

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        return _require_non_empty(value, "user_id")


class ChatResponse(APIModel):
    reply: str
    model: str
    route_category: PublicRouteCategory
    price_usdc: float
    payment_status: SettlementStatus
    bond_balance: float
    flagged: bool
    payment_ref: str
    slash_executed: bool = False
    slash_tx_hash: str | None = None
    slash_payout: float | None = None
    slash_victim_address: str | None = None
    timestamp: datetime

    @field_validator("reply", "model", "payment_ref")
    @classmethod
    def validate_non_empty_fields(cls, value: str, info) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("price_usdc", "bond_balance")
    @classmethod
    def validate_amounts(cls, value: float, info) -> float:
        return _require_non_negative_finite(value, info.field_name)

    @field_validator("slash_tx_hash")
    @classmethod
    def validate_optional_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_non_empty(value, "slash_tx_hash")

    @field_validator("slash_victim_address")
    @classmethod
    def validate_optional_victim_address(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_non_empty(value, "slash_victim_address")

    @field_validator("slash_payout")
    @classmethod
    def validate_optional_payout(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return _require_non_negative_finite(value, "slash_payout")


class SlashRequest(APIModel):
    victim_address: str
    payout_amount: float

    @field_validator("victim_address")
    @classmethod
    def validate_victim_address(cls, value: str) -> str:
        return _require_non_empty(value, "victim_address")

    @field_validator("payout_amount")
    @classmethod
    def validate_payout_amount(cls, value: float) -> float:
        return _require_positive_finite(value, "payout_amount")


class SlashResponse(APIModel):
    tx_hash: str
    payout: float
    new_balance: float
    timestamp: datetime

    @field_validator("tx_hash")
    @classmethod
    def validate_tx_hash(cls, value: str) -> str:
        return _require_non_empty(value, "tx_hash")

    @field_validator("payout", "new_balance")
    @classmethod
    def validate_amounts(cls, value: float, info) -> float:
        return _require_non_negative_finite(value, info.field_name)


class BondStatusResponse(APIModel):
    balance: float
    state: str
    total_paid_requests: int = Field(..., ge=0)

    @field_validator("balance")
    @classmethod
    def validate_balance(cls, value: float) -> float:
        return _require_non_negative_finite(value, "balance")

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str) -> str:
        return _require_non_empty(value, "state")


class TransactionRecord(APIModel):
    type: EventName
    amount: float
    timestamp: datetime
    model: str | None = None
    route_category: PublicRouteCategory | None = None
    status: SettlementStatus | None = None
    payment_ref: str | None = None
    tx_hash: str | None = None
    victim_address: str | None = None
    flagged: bool | None = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: float) -> float:
        return _require_non_negative_finite(value, "amount")


class RouteMetricsResponse(APIModel):
    general: int = Field(..., ge=0)
    technical: int = Field(..., ge=0)
    legal: int = Field(..., ge=0)
    fallback: int = Field(..., ge=0)


class SettlementMetricsResponse(APIModel):
    authorized: int = Field(..., ge=0)
    settled: int = Field(..., ge=0)
    failed: int = Field(..., ge=0)
    total_volume_usdc: float

    @field_validator("total_volume_usdc")
    @classmethod
    def validate_total_volume(cls, value: float) -> float:
        return _require_non_negative_finite(value, "total_volume_usdc")


class AnomalyMetricsResponse(APIModel):
    flagged_requests: int = Field(..., ge=0)
    slashes: int = Field(..., ge=0)
    total_slashed_usdc: float

    @field_validator("total_slashed_usdc")
    @classmethod
    def validate_total_slashed(cls, value: float) -> float:
        return _require_non_negative_finite(value, "total_slashed_usdc")


class WebSocketEvent(APIModel):
    event: EventName
    data: dict[str, Any]
