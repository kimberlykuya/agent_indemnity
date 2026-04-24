from __future__ import annotations

from datetime import datetime
from math import isfinite
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

PublicRouteCategory = Literal["general", "technical", "legal", "fallback"]
SettlementStatus = Literal["authorized", "settled", "failed"]
EventName = Literal["request_paid", "bond_slashed", "bond_topped_up", "anomaly_flagged"]
AnomalySignal = Literal["none", "rule", "embedding", "rule+embedding"]
SlashMode = Literal["none", "auto", "manual"]


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


class PaymentProof(APIModel):
    proof_token: str
    payer_wallet_address: str
    facilitator_tx_ref: str
    payment_tx_hash: str | None = None

    @field_validator("proof_token", "payer_wallet_address", "facilitator_tx_ref")
    @classmethod
    def validate_non_empty_fields(cls, value: str, info) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("payment_tx_hash")
    @classmethod
    def validate_optional_payment_tx_hash(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_non_empty(value, "payment_tx_hash")


class ChatRequest(APIModel):
    message: str = Field(..., description="Customer message")
    user_id: str = Field(..., description="Caller identifier")
    user_wallet_address: str = Field(..., description="Payer and beneficiary wallet for this request")
    payment_challenge_token: str | None = Field(default=None, description="Challenge token from the prior 402 response")
    payment_proof: PaymentProof | None = Field(default=None, description="x402/Circle proof payload for the retry")

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return _require_non_empty(value, "message")

    @field_validator("user_id")
    @classmethod
    def validate_user_id(cls, value: str) -> str:
        return _require_non_empty(value, "user_id")

    @field_validator("user_wallet_address")
    @classmethod
    def validate_user_wallet_address(cls, value: str) -> str:
        return _require_non_empty(value, "user_wallet_address")

    @field_validator("payment_challenge_token")
    @classmethod
    def validate_optional_challenge_token(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_non_empty(value, "payment_challenge_token")


class PaymentChallengeResponse(APIModel):
    kind: Literal["payment_required"] = "payment_required"
    message: str
    route_category: PublicRouteCategory
    route_confidence: float | None = None
    price_usdc: float
    payment_challenge_token: str
    expires_at: datetime
    payment_network: str
    facilitator_url: str | None = None
    payment_instructions: dict[str, Any]

    @field_validator("message", "payment_challenge_token", "payment_network")
    @classmethod
    def validate_non_empty_fields(cls, value: str, info) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("facilitator_url")
    @classmethod
    def validate_optional_facilitator_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_non_empty(value, "facilitator_url")

    @field_validator("price_usdc")
    @classmethod
    def validate_price(cls, value: float) -> float:
        return _require_non_negative_finite(value, "price_usdc")


class ChatResponse(APIModel):
    reply: str
    model: str
    route_category: PublicRouteCategory
    route_confidence: float | None = None
    price_usdc: float
    payment_status: SettlementStatus
    bond_balance: float
    flagged: bool
    payment_ref: str
    anomaly_reason: str | None = None
    slash_executed: bool = False
    slash_tx_hash: str | None = None
    slash_payout: float | None = None
    slash_victim_address: str | None = None
    payer_wallet_address: str
    beneficiary_wallet_address: str
    anomaly_signal: AnomalySignal = "none"
    slash_mode: SlashMode = "none"
    slash_error: str | None = None
    idempotent_replay: bool = False
    timestamp: datetime

    @field_validator("reply", "model", "payment_ref", "payer_wallet_address", "beneficiary_wallet_address")
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

    @field_validator("slash_error")
    @classmethod
    def validate_optional_slash_error(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_non_empty(value, "slash_error")

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
    beneficiary_wallet_address: str
    slash_mode: Literal["auto", "manual"]
    timestamp: datetime

    @field_validator("tx_hash", "beneficiary_wallet_address")
    @classmethod
    def validate_non_empty_fields(cls, value: str, info) -> str:
        return _require_non_empty(value, info.field_name)

    @field_validator("payout", "new_balance")
    @classmethod
    def validate_amounts(cls, value: float, info) -> float:
        return _require_non_negative_finite(value, info.field_name)


class BondStatusResponse(APIModel):
    balance: float
    state: str
    total_paid_requests: int = Field(..., ge=0)
    alert_floor_usdc: float = Field(..., ge=0)
    is_below_alert_floor: bool
    warning_message: str | None = None

    @field_validator("balance")
    @classmethod
    def validate_balance(cls, value: float) -> float:
        return _require_non_negative_finite(value, "balance")

    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str) -> str:
        return _require_non_empty(value, "state")

    @field_validator("warning_message")
    @classmethod
    def validate_optional_warning_message(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _require_non_empty(value, "warning_message")


class TransactionRecord(APIModel):
    type: EventName
    amount: float
    timestamp: datetime
    bond_balance_after: float | None = None
    model: str | None = None
    route_category: PublicRouteCategory | None = None
    status: SettlementStatus | None = None
    payment_ref: str | None = None
    tx_hash: str | None = None
    victim_address: str | None = None
    flagged: bool | None = None
    anomaly_reason: str | None = None
    anomaly_signal: AnomalySignal | None = None
    slash_mode: SlashMode | None = None
    payer_wallet_address: str | None = None
    beneficiary_wallet_address: str | None = None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: float) -> float:
        return _require_non_negative_finite(value, "amount")

    @field_validator("bond_balance_after")
    @classmethod
    def validate_optional_balance(cls, value: float | None) -> float | None:
        if value is None:
            return None
        return _require_non_negative_finite(value, "bond_balance_after")


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


ChatRequest.model_rebuild()
