from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
from threading import Lock


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _message_hash(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


@dataclass(frozen=True)
class PaymentChallenge:
    token: str
    message_hash: str
    user_id: str
    user_wallet_address: str
    route_category: str
    route_confidence: float | None
    price_usdc: float
    created_at: datetime
    expires_at: datetime
    used: bool = False


@dataclass(frozen=True)
class PaymentSettlement:
    payment_ref: str
    payer_wallet_address: str
    route_category: str
    route_confidence: float | None
    price_usdc: float


class PaymentGatewayError(RuntimeError):
    def __init__(self, message: str, *, code: str = "payment_gateway_error", status_code: int = 402) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class PaymentGateway:
    def __init__(self, *, ttl_seconds: int | None = None, now_factory=None) -> None:
        self._ttl_seconds = ttl_seconds or _env_int("PAYMENT_CHALLENGE_TTL_SECONDS", 300)
        self._now_factory = now_factory or _utcnow
        self._lock = Lock()
        self._challenges: dict[str, PaymentChallenge] = {}

    @property
    def payment_network(self) -> str:
        return os.getenv("PAYMENT_NETWORK_NAME", "Circle Gateway / x402")

    @property
    def facilitator_url(self) -> str | None:
        raw = os.getenv("X402_FACILITATOR_URL") or os.getenv("PAYMENT_FACILITATOR_URL")
        return raw.strip() if raw and raw.strip() else None

    def create_challenge(
        self,
        *,
        message: str,
        user_id: str,
        user_wallet_address: str,
        route_category: str,
        route_confidence: float | None,
        price_usdc: float,
    ) -> PaymentChallenge:
        now = self._now_factory()
        token = secrets.token_urlsafe(24)
        challenge = PaymentChallenge(
            token=token,
            message_hash=_message_hash(message),
            user_id=user_id,
            user_wallet_address=user_wallet_address,
            route_category=route_category,
            route_confidence=route_confidence,
            price_usdc=price_usdc,
            created_at=now,
            expires_at=now + timedelta(seconds=self._ttl_seconds),
        )
        with self._lock:
            self._challenges[token] = challenge
        return challenge

    def build_instructions(self, challenge: PaymentChallenge) -> dict[str, object]:
        instructions: dict[str, object] = {
            "currency": "USDC",
            "amount_usdc": round(challenge.price_usdc, 6),
            "required_proof_fields": [
                "proof_token",
                "payer_wallet_address",
                "facilitator_tx_ref",
            ],
            "payer_wallet_address": challenge.user_wallet_address,
            "request_binding": {
                "user_id": challenge.user_id,
                "route_category": challenge.route_category,
            },
        }
        if self.facilitator_url:
            instructions["facilitator_url"] = self.facilitator_url
        return instructions

    def verify_payment(
        self,
        *,
        message: str,
        user_id: str,
        user_wallet_address: str,
        challenge_token: str,
        payment_proof: dict[str, object],
    ) -> PaymentSettlement:
        challenge = self._get_challenge(challenge_token)
        now = self._now_factory()

        if challenge.used:
            raise PaymentGatewayError(
                "This payment challenge has already been used.",
                code="payment_challenge_consumed",
                status_code=409,
            )
        if now >= challenge.expires_at:
            raise PaymentGatewayError(
                "This payment challenge has expired. Request a fresh payment challenge.",
                code="payment_challenge_expired",
                status_code=402,
            )
        if challenge.user_id != user_id or challenge.message_hash != _message_hash(message):
            raise PaymentGatewayError(
                "The payment challenge does not match this request payload.",
                code="payment_request_mismatch",
                status_code=409,
            )
        if challenge.user_wallet_address != user_wallet_address:
            raise PaymentGatewayError(
                "The payer wallet does not match the active payment challenge.",
                code="payment_wallet_mismatch",
                status_code=409,
            )

        proof_token = str(payment_proof.get("proof_token") or "").strip()
        if proof_token != challenge_token:
            raise PaymentGatewayError(
                "Invalid payment proof token.",
                code="invalid_payment_proof",
                status_code=402,
            )

        proof_wallet = str(payment_proof.get("payer_wallet_address") or "").strip()
        if proof_wallet != user_wallet_address:
            raise PaymentGatewayError(
                "Payment proof wallet does not match the request wallet.",
                code="payment_wallet_mismatch",
                status_code=409,
            )

        facilitator_tx_ref = str(payment_proof.get("facilitator_tx_ref") or "").strip()
        if not facilitator_tx_ref:
            raise PaymentGatewayError(
                "Payment proof is missing facilitator_tx_ref.",
                code="invalid_payment_proof",
                status_code=402,
            )

        with self._lock:
            self._challenges[challenge_token] = replace(challenge, used=True)

        return PaymentSettlement(
            payment_ref=f"x402:{facilitator_tx_ref}",
            payer_wallet_address=user_wallet_address,
            route_category=challenge.route_category,
            route_confidence=challenge.route_confidence,
            price_usdc=challenge.price_usdc,
        )

    def _get_challenge(self, token: str) -> PaymentChallenge:
        with self._lock:
            challenge = self._challenges.get(token)
        if challenge is None:
            raise PaymentGatewayError(
                "Unknown payment challenge token. Request a new payment challenge.",
                code="payment_challenge_not_found",
                status_code=402,
            )
        return challenge
