from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from backend.services.payment_gateway import PaymentGateway, PaymentGatewayError


@dataclass(frozen=True)
class CirclePaymentAuthorization:
    challenge_token: str
    circle_wallet_id: str
    circle_wallet_address: str
    x_payment_header: str
    payment_proof: dict[str, object]


class CirclePaymentServiceError(RuntimeError):
    def __init__(self, message: str, *, code: str = "circle_payment_error", status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class CirclePaymentService:
    def __init__(self, payment_gateway: PaymentGateway, *, timeout_seconds: int = 30) -> None:
        self._payment_gateway = payment_gateway
        self._timeout_seconds = timeout_seconds
        self._mock_mode = self._env_flag("CIRCLE_MOCK_MODE")
        if self._mock_mode:
            print("[HACKATHON MODE] Using mocked Circle responses")

    def authorize_payment(
        self,
        *,
        message: str,
        user_id: str,
        user_wallet_address: str,
        challenge_token: str,
    ) -> CirclePaymentAuthorization:
        self._require_circle_config()
        challenge = self._payment_gateway.get_challenge(challenge_token)

        if challenge.user_id != user_id:
            raise CirclePaymentServiceError(
                "Circle payment authorization does not match the active user.",
                code="circle_payment_mismatch",
                status_code=409,
            )
        if challenge.user_wallet_address != user_wallet_address:
            raise CirclePaymentServiceError(
                "Circle payment authorization does not match the beneficiary wallet.",
                code="circle_payment_mismatch",
                status_code=409,
            )

        wallet = self._ensure_circle_wallet(user_id=user_id)
        typed_data = self._payment_gateway.build_typed_data(challenge)
        signature = self._sign_typed_data(
            wallet_id=str(wallet["id"]),
            wallet_address=str(wallet["address"]),
            typed_data=typed_data,
        )

        x_payment_payload = {
            "version": "x402-circle-v1",
            "network": os.getenv("CIRCLE_BLOCKCHAIN", "ARC-TESTNET"),
            "challengeToken": challenge_token,
            "circleWalletId": str(wallet["id"]),
            "circleWalletAddress": str(wallet["address"]),
            "beneficiaryWalletAddress": user_wallet_address,
            "typedData": typed_data,
            "signature": signature,
            "facilitator": self._payment_gateway.facilitator_url,
            "amountUsdc": challenge.price_usdc,
        }
        x_payment_header = json.dumps(x_payment_payload, separators=(",", ":"), ensure_ascii=True)
        payment_proof = {
            "proof_token": challenge_token,
            "payer_wallet_address": user_wallet_address,
            "facilitator_tx_ref": f"circle-sign-{int(time.time() * 1000)}",
            "circle_wallet_id": str(wallet["id"]),
            "circle_wallet_address": str(wallet["address"]),
            "x_payment_header": x_payment_header,
            "x_payment_payload": x_payment_payload,
        }
        return CirclePaymentAuthorization(
            challenge_token=challenge_token,
            circle_wallet_id=str(wallet["id"]),
            circle_wallet_address=str(wallet["address"]),
            x_payment_header=x_payment_header,
            payment_proof=payment_proof,
        )

    def _require_circle_config(self) -> None:
        if self._mock_mode:
            return
        missing = [
            name
            for name in ("CIRCLE_API_KEY", "CIRCLE_WALLET_SET_ID")
            if not os.getenv(name, "").strip()
        ]
        if not (os.getenv("CIRCLE_ENTITY_SECRET", "").strip() or os.getenv("CIRCLE_ENTITY_SECRET_CIPHERTEXT", "").strip()):
            missing.append("CIRCLE_ENTITY_SECRET or CIRCLE_ENTITY_SECRET_CIPHERTEXT")
        if missing:
            raise CirclePaymentServiceError(
                f"Missing Circle configuration: {', '.join(missing)}",
                code="circle_payment_misconfigured",
                status_code=500,
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {os.getenv('CIRCLE_API_KEY', '').strip()}",
            "Content-Type": "application/json",
        }

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

    def _base_url(self) -> str:
        return os.getenv("CIRCLE_API_BASE_URL", "https://api.circle.com").rstrip("/")

    def _request(self, method: str, path: str, *, json_body: dict | None = None) -> dict:
        if self._mock_mode:
            # Mock Circle API responses
            if path == "/v1/w3s/config/entity/publicKey":
                return {"data": {"publicKey": "-----BEGIN PUBLIC KEY-----\nMFwwDQYJKoZIhvcNAQEBBQADSwAwSAJBAKj34GkWiFAoNsgQcL41IfqxQQYrQVDr\nkwn5M8tFfUY4MxX2F8fKWlbVk5CsRwfMIKcBJXLz9sTVH5mfHQ7J8okCAwEAAQ==\n-----END PUBLIC KEY-----"}}
            elif path == "/v1/w3s/developer/wallets":
                return {"data": {"wallets": []}}
            elif path.startswith("/v1/w3s/developer/sign/typedData"):
                return {"data": {"signature": "0xmocksignature"}}
            return {"data": {}}
        
        url = f"{self._base_url()}{path}"
        try:
            response = httpx.request(
                method,
                url,
                headers=self._headers(),
                json=json_body,
                timeout=self._timeout_seconds,
            )
        except httpx.HTTPError as exc:
            raise CirclePaymentServiceError(
                f"Circle API request failed: {exc}",
                code="circle_api_unreachable",
                status_code=502,
            ) from exc

        if response.status_code >= 400:
            try:
                detail = response.json()
            except ValueError:
                detail = response.text
            raise CirclePaymentServiceError(
                f"Circle API rejected request: {detail}",
                code="circle_api_rejected",
                status_code=502,
            )
        try:
            return response.json()
        except ValueError as exc:
            raise CirclePaymentServiceError(
                "Circle API returned invalid JSON.",
                code="circle_api_invalid_response",
                status_code=502,
            ) from exc

    def _entity_secret_ciphertext(self) -> str:
        precomputed = os.getenv("CIRCLE_ENTITY_SECRET_CIPHERTEXT", "").strip()
        if precomputed:
            return precomputed

        raw_secret = os.getenv("CIRCLE_ENTITY_SECRET", "").strip()
        if not raw_secret:
            raise CirclePaymentServiceError(
                "Missing Circle entity secret. Set CIRCLE_ENTITY_SECRET or CIRCLE_ENTITY_SECRET_CIPHERTEXT.",
                code="circle_payment_misconfigured",
                status_code=500,
            )

        body = self._request("GET", "/v1/w3s/config/entity/publicKey")
        public_key_pem = str(body.get("data", {}).get("publicKey") or "").strip()
        if not public_key_pem:
            raise CirclePaymentServiceError(
                "Circle entity public key is missing from the API response.",
                code="circle_api_invalid_response",
                status_code=502,
            )
        public_key = serialization.load_pem_public_key(public_key_pem.encode("utf-8"))
        ciphertext = public_key.encrypt(
            raw_secret.encode("utf-8"),
            padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None),
        )
        return base64.b64encode(ciphertext).decode("ascii")

    def _ensure_circle_wallet(self, *, user_id: str) -> dict[str, object]:
        if self._mock_mode:
            # Generate deterministic mock wallet based on user_id
            wallet_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"mock.circle.{user_id}"))
            # Generate deterministic mock address
            mock_address = "0x" + hashlib.sha256(f"mock.{user_id}".encode()).hexdigest()[:40]
            return {
                "id": wallet_id,
                "address": mock_address,
                "blockchain": os.getenv("CIRCLE_BLOCKCHAIN", "ARC-TESTNET"),
                "accountType": "EOA",
            }
        
        wallet_set_id = os.getenv("CIRCLE_WALLET_SET_ID", "").strip()
        blockchain = os.getenv("CIRCLE_BLOCKCHAIN", "ARC-TESTNET").strip()
        idempotency_key = str(
            uuid.uuid5(uuid.NAMESPACE_URL, f"{wallet_set_id}:{blockchain}:{user_id}")
        )
        create_body = self._request(
            "POST",
            "/v1/w3s/developer/wallets",
            json_body={
                "idempotencyKey": idempotency_key,
                "accountType": "EOA",
                "blockchains": [blockchain],
                "count": 1,
                "walletSetId": wallet_set_id,
                "entitySecretCiphertext": self._entity_secret_ciphertext(),
            },
        )
        created_wallets = create_body.get("data", {}).get("wallets") or []
        if not created_wallets:
            raise CirclePaymentServiceError(
                "Circle wallet creation returned no wallets.",
                code="circle_api_invalid_response",
                status_code=502,
            )
        return created_wallets[0]

    def _sign_typed_data(self, *, wallet_id: str, wallet_address: str, typed_data: dict[str, object]) -> str:
        if self._mock_mode:
            # Generate deterministic mock signature based on wallet + typed data
            sig_input = json.dumps({"wallet_id": wallet_id, "typed_data": typed_data}, sort_keys=True)
            mock_sig = "0x" + hashlib.sha256(sig_input.encode()).hexdigest() + hashlib.sha256(f"sig.{wallet_id}".encode()).hexdigest()
            return mock_sig
        
        blockchain = os.getenv("CIRCLE_BLOCKCHAIN", "ARC-TESTNET").strip()
        response = self._request(
            "POST",
            "/v1/w3s/developer/sign/typedData",
            json_body={
                "walletId": wallet_id,
                "entitySecretCiphertext": self._entity_secret_ciphertext(),
                "data": typed_data,
                "memo": f"Agent Indemnity x402 authorization for {wallet_address}",
                "blockchain": blockchain,
            },
        )
        signature = str(response.get("data", {}).get("signature") or "").strip()
        if not signature:
            raise CirclePaymentServiceError(
                "Circle signTypedData response did not include a signature.",
                code="circle_api_invalid_response",
                status_code=502,
            )
        return signature
