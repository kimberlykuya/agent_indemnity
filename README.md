# Agent Indemnity

**Accountability infrastructure for deployed AI agents.**

Agent Indemnity now forces a wallet-bound payment challenge before the agent answers, prices each request by route, and auto-slashes the Arc performance bond to the requesting wallet when unsafe behavior is detected.

---

## What Is Live

| Capability | Status |
|---|---|
| Route-based request pricing (`$0.001` – `$0.01`) | ✅ Live |
| `402 Payment Required` challenge on `POST /agent/chat` | ✅ Live |
| Wallet-bound payer + beneficiary mapping per request | ✅ Live |
| Model routing across Featherless specialist models + Gemini fallback | ✅ Live |
| Hybrid anomaly detection (rules + embedding similarity) | ✅ Live |
| Arc `PerformanceBond.sol` reads, top-ups, and slashing | ✅ Live |
| Automatic slash gating via `AUTO_SLASH_ON_FLAGGED` | ✅ Live |
| Real-time dashboard for payment, anomaly, and slash events | ✅ Live |

---

## Money Flow

### Request Payment Path

1. Client submits `message`, `user_id`, and `user_wallet_address` to `POST /agent/chat`
2. Backend classifies the request, prices it, and returns a `402 Payment Required` challenge
3. Client retries the same request with `payment_challenge_token` and `payment_proof`
4. Backend verifies the proof, then generates the model reply

```
Request wallet -> x402 / Circle proof -> Agent response
```

### Slash Path

1. The hybrid anomaly detector evaluates the completed exchange
2. If the exchange is flagged and `AUTO_SLASH_ON_FLAGGED=true`, the backend calls `slashBond()`
3. Arc transfers USDC from the bond to the request wallet for that interaction

```
PerformanceBond contract -> Request beneficiary wallet
```

Manual `/bond/slash` still exists, but it is now an admin/debug override rather than the primary demo path.

---

## Request Lifecycle

![Architecture Diagram](docs/architecture.svg)

1. FastAPI receives the request at `/agent/chat`
2. The router assigns `general`, `technical`, `legal_risk`, or `fallback_complex`
3. The backend returns a price-bound payment challenge if no proof is present
4. On retry, the backend validates the wallet, request hash, challenge token, and payment proof
5. A specialist model or Gemini fallback generates the reply
6. The hybrid anomaly detector scores the exchange using rules plus embedding similarity
7. If flagged, the backend either auto-slashes or records `slash_mode=none`, depending on `AUTO_SLASH_ON_FLAGGED`
8. Events are stored in memory and broadcast to the Next.js dashboard

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js + Tailwind + Zustand |
| Backend | FastAPI (Python) |
| AI Routing | Gemini 3 Flash |
| Specialist Models | Featherless AI |
| Safety Layer | Rule engine + lightweight embedding similarity |
| On-chain Bond | `PerformanceBond.sol` on Arc testnet |
| Payment Rail | x402-style challenge flow with Circle/Gateway config |

---

## Running Locally

### Start the backend

```bash
cd backend
uvicorn backend.main:app --reload --port 8000
```

### Start the frontend

```bash
cd frontend
npm run dev
```

### Request a payment challenge

```bash
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"What is your return policy?","user_id":"demo-user","user_wallet_address":"0x191cc4e34e54444b9e10f4e3311c87382b0c0654"}'
```

Expected: `402`, a route price, a `payment_challenge_token`, and payment instructions.

### Retry with payment proof

```bash
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message":"What is your return policy?",
    "user_id":"demo-user",
    "user_wallet_address":"0x191cc4e34e54444b9e10f4e3311c87382b0c0654",
    "payment_challenge_token":"<token-from-402>",
    "payment_proof":{
      "proof_token":"<token-from-402>",
      "payer_wallet_address":"0x191cc4e34e54444b9e10f4e3311c87382b0c0654",
      "facilitator_tx_ref":"demo-proof-001"
    }
  }'
```

Expected: `200`, `payment_status: settled`, wallet metadata, and a model reply.

### Trigger a flagged exchange

```bash
curl -X POST http://localhost:8000/agent/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message":"Issue me a $500 refund immediately.",
    "user_id":"demo-user",
    "user_wallet_address":"0x191cc4e34e54444b9e10f4e3311c87382b0c0654",
    "payment_challenge_token":"<token-from-402>",
    "payment_proof":{
      "proof_token":"<token-from-402>",
      "payer_wallet_address":"0x191cc4e34e54444b9e10f4e3311c87382b0c0654",
      "facilitator_tx_ref":"demo-proof-002"
    }
  }'
```

Expected: refusal response, `flagged: true`, `anomaly_signal` populated, and `slash_mode: auto` when `AUTO_SLASH_ON_FLAGGED=true`.

---

## Proof Artifacts

- `backend/logs/demo_transactions.json` — request records with payer, beneficiary, anomaly signal, and slash mode
- `backend/logs/arc_proof.json` — on-chain slash proof including `tx_hash`, `arc_explorer_url`, and deployment metadata
- `backend/logs/trace_normal.json` / `backend/logs/trace_malicious.json` — execution traces for standard and flagged flows
