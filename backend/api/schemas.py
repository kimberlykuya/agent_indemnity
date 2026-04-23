"""
api/schemas.py
---------------
Pydantic request / response models.

Matches the output of customer_service.handle_request exactly.
Keeps the API contract stable across Sprint 3 refactors.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Customer message")
    user_id: str = Field("demo-user", description="Caller identifier")


class RouteDecision(BaseModel):
    route:      str
    confidence: float
    reason:     str
    decided_by: str   # "rules" | "gemini"


class PaymentRecord(BaseModel):
    payment_status: str   # "priced" | "provider_error" | "flagged"
    price_usdc:     float
    currency:       str   # always "USDC"
    route_category: str
    buyer_id:       str


class AnomalyResult(BaseModel):
    flagged: bool
    reason:  str | None


class ChatResponse(BaseModel):
    reply:            str
    model:            str
    route_category:   str
    route_confidence: float
    price_usdc:       float
    payment_status:   str
    flagged:          bool
    anomaly_reason:   str | None
    latency_ms:       int
