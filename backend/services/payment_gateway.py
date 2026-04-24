from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets
from threading import Lock
from urllib.parse import urlparse
from pathlib import Path

import httpx


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


def _is_valid_http_url(value: str | None) -> bool:
    if not value:
        return False
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        return False
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc or "." not in parsed.netloc:
        return False
    if "..." in parsed.netloc or parsed.netloc.startswith(".") or parsed.netloc.endswith("."):
        return False
    return True


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
    settlement_source: str = "gateway_authorization"


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
        self._mock_mode = self._env_flag("CIRCLE_MOCK_MODE")

    @property
    def payment_network(self) -> str:
        return os.getenv("PAYMENT_NETWORK_NAME", "Circle Gateway / x402")

    @property
    def facilitator_url(self) -> str | None:
        raw = os.getenv("X402_FACILITATOR_URL") or os.getenv("PAYMENT_FACILITATOR_URL")
        return raw.strip() if raw and raw.strip() else None

    @property
    def gateway_mode(self) -> str:
        if self._mock_mode:
            return "stub"
        if os.getenv("PAYMENT_GATEWAY_MODE"):
            return os.getenv("PAYMENT_GATEWAY_MODE", "stub").strip().lower()
        return "facilitator" if self.facilitator_url else "stub"

    @staticmethod
    def _is_truthy(value: str | None) -> bool:
        return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}

    def _env_flag(self, name: str) -> bool:
        value = os.getenv(name)
        if self._is_truthy(value):
            return True

        repo_root = Path(__file__).resolve().parent.parent.parent
        for candidate in (
            repo_root / ".env",
            repo_root / "dev-controlled-projects" / ".env",
        ):
            if not candidate.exists():
                continue
            for line in candidate.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, raw = stripped.split("=", 1)
                if key.strip() == name:
                    return self._is_truthy(raw)
        return False

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
            instructions["gateway_mode"] = self.gateway_mode
        instructions["x402_typed_data"] = self.build_typed_data(challenge)
        return instructions

    def get_challenge(self, token: str) -> PaymentChallenge:
        return self._get_challenge(token)

    def build_typed_data(self, challenge: PaymentChallenge) -> dict[str, object]:
        chain_id_raw = os.getenv("ARC_CHAIN_ID", "5042002")
        try:
            chain_id = int(chain_id_raw)
        except ValueError:
            chain_id = 5042002
        return {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                ],
                "PaymentAuthorization": [
                    {"name": "challengeToken", "type": "string"},
                    {"name": "messageHash", "type": "string"},
                    {"name": "userId", "type": "string"},
                    {"name": "beneficiaryWallet", "type": "string"},
                    {"name": "routeCategory", "type": "string"},
                    {"name": "priceUsdcMicros", "type": "uint256"},
                    {"name": "expiresAt", "type": "uint256"},
                    {"name": "facilitator", "type": "string"},
                ],
            },
            "primaryType": "PaymentAuthorization",
            "domain": {
                "name": "AgentIndemnityX402",
                "version": "1",
                "chainId": chain_id,
            },
            "message": {
                "challengeToken": challenge.token,
                "messageHash": challenge.message_hash,
                "userId": challenge.user_id,
                "beneficiaryWallet": challenge.user_wallet_address,
                "routeCategory": challenge.route_category,
                "priceUsdcMicros": int(challenge.price_usdc * 1_000_000),
                "expiresAt": int(challenge.expires_at.timestamp()),
                "facilitator": self.facilitator_url or "",
            },
        }

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

        settlement = self._verify_with_gateway(
            challenge=challenge,
            challenge_token=challenge_token,
            user_wallet_address=user_wallet_address,
            facilitator_tx_ref=facilitator_tx_ref,
            payment_proof=payment_proof,
        )

        with self._lock:
            self._challenges[challenge_token] = replace(challenge, used=True)

        return settlement

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

    def _verify_with_gateway(
        self,
        *,
        challenge: PaymentChallenge,
        challenge_token: str,
        user_wallet_address: str,
        facilitator_tx_ref: str,
        payment_proof: dict[str, object],
    ) -> PaymentSettlement:
        if self.gateway_mode == "facilitator":
            return self._verify_with_facilitator(
                challenge=challenge,
                challenge_token=challenge_token,
                user_wallet_address=user_wallet_address,
                facilitator_tx_ref=facilitator_tx_ref,
                payment_proof=payment_proof,
            )
        return PaymentSettlement(
            payment_ref=str(payment_proof.get("payment_tx_hash") or f"x402:{facilitator_tx_ref}"),
            payer_wallet_address=user_wallet_address,
            route_category=challenge.route_category,
            route_confidence=challenge.route_confidence,
            price_usdc=challenge.price_usdc,
            settlement_source="stub_authorization",
        )

    def _verify_with_facilitator(
        self,
        *,
        challenge: PaymentChallenge,
        challenge_token: str,
        user_wallet_address: str,
        facilitator_tx_ref: str,
        payment_proof: dict[str, object],
    ) -> PaymentSettlement:
        if self._mock_mode:
            return PaymentSettlement(
                payment_ref=str(payment_proof.get("payment_tx_hash") or f"x402:{facilitator_tx_ref}"),
                payer_wallet_address=user_wallet_address,
                route_category=challenge.route_category,
                route_confidence=challenge.route_confidence,
                price_usdc=challenge.price_usdc,
                settlement_source="stub_authorization",
            )
        if not self.facilitator_url:
            raise PaymentGatewayError(
                "PAYMENT_GATEWAY_MODE=facilitator requires X402_FACILITATOR_URL.",
                code="payment_gateway_misconfigured",
                status_code=500,
            )
        if not _is_valid_http_url(self.facilitator_url):
            raise PaymentGatewayError(
                "X402_FACILITATOR_URL is not a valid HTTP(S) URL.",
                code="payment_gateway_misconfigured",
                status_code=500,
            )

        api_key = (
            os.getenv("GATEWAY_API_KEY")
            or os.getenv("CIRCLE_GATEWAY_API_KEY")
            or os.getenv("CIRCLE_API_KEY")
        )
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        x_payment_header = str(payment_proof.get("x_payment_header") or "").strip()
        if x_payment_header:
            headers["X-PAYMENT"] = x_payment_header

        payload = {
            "challenge_token": challenge_token,
            "facilitator_tx_ref": facilitator_tx_ref,
            "payer_wallet_address": user_wallet_address,
            "price_usdc": challenge.price_usdc,
            "route_category": challenge.route_category,
            "request_binding": {
                "user_id": challenge.user_id,
                "message_hash": challenge.message_hash,
            },
            "payment_proof": payment_proof,
            "typed_data": self.build_typed_data(challenge),
        }

        try:
            response = httpx.post(
                self.facilitator_url,
                json=payload,
                headers=headers,
                timeout=_env_int("PAYMENT_GATEWAY_TIMEOUT_SECONDS", 20),
            )
        except (httpx.HTTPError, UnicodeError, ValueError) as exc:
            raise PaymentGatewayError(
                f"Payment gateway verification failed: {exc}",
                code="payment_gateway_unreachable",
                status_code=502,
            ) from exc

        if response.status_code >= 400:
            detail = None
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise PaymentGatewayError(
                f"Payment gateway rejected authorization: {detail}",
                code="payment_gateway_rejected",
                status_code=402,
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise PaymentGatewayError(
                "Payment gateway returned invalid JSON.",
                code="payment_gateway_invalid_response",
                status_code=502,
            ) from exc

        authorized = bool(body.get("authorized", True))
        if not authorized:
            raise PaymentGatewayError(
                str(body.get("message") or "Payment authorization was denied."),
                code=str(body.get("code") or "payment_gateway_rejected"),
                status_code=402,
            )

        payment_ref = str(
            body.get("payment_tx_hash")
            or body.get("tx_hash")
            or body.get("payment_ref")
            or payment_proof.get("payment_tx_hash")
            or f"x402:{facilitator_tx_ref}"
        ).strip()
        if not payment_ref:
            raise PaymentGatewayError(
                "Payment gateway did not return a verifier-safe reference.",
                code="payment_gateway_invalid_response",
                status_code=502,
            )

        return PaymentSettlement(
            payment_ref=payment_ref,
            payer_wallet_address=user_wallet_address,
            route_category=challenge.route_category,
            route_confidence=challenge.route_confidence,
            price_usdc=challenge.price_usdc,
            settlement_source=str(body.get("settlement_source") or "facilitator_authorization"),
        )
