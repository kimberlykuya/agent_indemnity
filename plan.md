# Agent Indemnity — Revised 2-Day Sprint Implementation Plan (April 2026)

**Project:** Agent Indemnity — Per-Action AI Performance Bond Infrastructure
**Stack:** Python (FastAPI backend) + Next.js (frontend dashboard)
**Submission Deadline:** April 25, 2026, 03:00 AM EAT
**Start Time:** April 23, 2026, 08:00 AM EAT
**Total Available Time:** ~43 hours

---

## Executive Summary

Agent Indemnity instruments deployed AI agents with a USDC-backed performance bond on Arc. Every outbound agent action incurs a sub-cent usage charge that is authorized per request through Circle Gateway Nanopayments and later settled on Arc. A configurable anomaly trigger slashes the bond and releases USDC directly to the affected party — no claims process, no human adjudication delay.

The reframe is critical: this is **not insurance**. It is a programmable performance bond with automated slashing, similar in logic to validator slashing in blockchain systems. The product combines:

* **Gemini 3 Flash** for routing, orchestration, and function calling
* **Featherless specialist models** for cost-efficient task-specific inference
* **Circle Gateway Nanopayments + x402** for per-request USDC pricing
* **Arc** for settlement and on-chain bond enforcement

This architecture keeps the original product idea intact while aligning it with April 2026 hackathon expectations and current platform best practices.

---

## Technology Stack

### Backend — Python

| Layer                   | Technology                                             | Purpose                                                             |
| ----------------------- | ------------------------------------------------------ | ------------------------------------------------------------------- |
| API Framework           | FastAPI (current stable)                               | REST endpoints + WebSocket server                                   |
| Routing / Orchestration | Gemini 3 Flash via Gemini API                          | Classification, reasoning, function calling, fallback control plane |
| Deep Reasoning Fallback | Gemini 3 Pro                                           | Ambiguous or high-stakes tasks                                      |
| Specialist Inference    | Featherless via OpenAI-compatible API                  | Cost-efficient domain-specific model routing                        |
| Anomaly Detection       | Rule engine + Gemini safety / structured policy checks | Flags harmful or risky outputs                                      |
| Payment Rail            | Circle Gateway Nanopayments + x402                     | Per-request USDC charging                                           |
| Blockchain              | `web3.py` 6.x                                          | Arc EVM interaction, contract calls                                 |
| Smart Contract          | Solidity 0.8.x                                         | Performance bond + slashing logic                                   |
| Wallet Infrastructure   | Circle Wallets                                         | Agent wallet, deployer wallet, victim wallet                        |
| Settlement / Accounting | Gateway batch settlement + bond top-up logic           | Mirrors premium revenue into bond accounting                        |
| Load Testing            | `httpx` async or `locust`                              | Generates 50+ paid requests for demo                                |
| Environment             | `python-dotenv`                                        | Secret management                                                   |
| Testing                 | `pytest` + `pytest-asyncio`                            | Unit + integration tests                                            |

### Frontend — Next.js

| Layer          | Technology                           | Purpose                                         |
| -------------- | ------------------------------------ | ----------------------------------------------- |
| Framework      | Next.js (current stable, App Router) | Dashboard + demo UI                             |
| Styling        | Tailwind CSS                         | Utility-first styling                           |
| Real-time Data | Native WebSocket client              | Live event feed from FastAPI WS                 |
| Charts         | Recharts                             | Bond balance over time, routing/payment history |
| State          | Zustand                              | Client-side state management                    |
| Icons          | Lucide React                         | UI icons                                        |
| Notifications  | `react-hot-toast`                    | Live payout trigger alerts                      |
| HTTP Client    | `axios` or `fetch`                   | API calls to FastAPI backend                    |

### Infrastructure

| Layer                 | Technology                                  |
| --------------------- | ------------------------------------------- |
| Arc Network           | Arc Testnet (EVM-compatible L1)             |
| USDC                  | Arc-native USDC                             |
| Nanopayments          | Circle Gateway Nanopayments                 |
| Payment Standard      | x402 facilitator integration where useful   |
| Wallets               | Circle Wallets                              |
| Smart Contract Deploy | Hardhat or Foundry                          |
| Deployment            | Vercel (Next.js) + Railway/Render (FastAPI) |
| Version Control       | Git + GitHub                                |

---

## Repository Structure

```text
agent_indemnity/
├── backend/
│   ├── main.py
│   ├── agent/
│   │   ├── customer_service.py
│   │   ├── router.py
│   │   ├── anomaly_detector.py
│   │   ├── payment_meter.py
│   │   └── settlement_sync.py
│   ├── blockchain/
│   │   ├── arc_client.py
│   │   ├── contract_abi.json
│   │   └── bond_manager.py
│   ├── api/
│   │   ├── routes.py
│   │   └── schemas.py
│   ├── scripts/
│   │   └── load_test.py
│   ├── contracts/
│   │   └── PerformanceBond.sol
│   ├── tests/
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── page.tsx
│   │   ├── demo/page.tsx
│   │   └── layout.tsx
│   ├── components/
│   │   ├── BondBalance.tsx
│   │   ├── TxFeed.tsx
│   │   ├── AgentChat.tsx
│   │   ├── PayoutAlert.tsx
│   │   ├── MarginTable.tsx
│   │   └── BondChart.tsx
│   ├── lib/
│   │   ├── socket.ts
│   │   └── api.ts
│   └── package.json
├── .env.example
├── README.md
└── demo-script.md
```

---

## Environment Variables

```bash
# Arc / Circle
ARC_RPC_URL=https://rpc.arc.network
ARC_CHAIN_ID=1234
CIRCLE_API_KEY=your_circle_api_key
CIRCLE_WALLET_SET_ID=your_wallet_set_id
CIRCLE_ENTITY_SECRET=your_entity_secret
DEPLOYER_PRIVATE_KEY=your_deployer_wallet_pk
AGENT_WALLET_ADDRESS=0x...
VICTIM_WALLET_ADDRESS=0x...
USDC_CONTRACT_ADDRESS=0x...
PERFORMANCE_BOND_ADDRESS=0x...

# x402 / Gateway
X402_FACILITATOR_URL=https://...
GATEWAY_API_KEY=your_gateway_key

# AI
GEMINI_API_KEY=your_gemini_api_key
FEATHERLESS_API_KEY=your_featherless_api_key
FEATHERLESS_GENERAL_MODEL=verified_live_model_id
FEATHERLESS_TECH_MODEL=verified_live_model_id
FEATHERLESS_LEGAL_MODEL=verified_live_model_id

# App
FASTAPI_PORT=8000
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```

---

## Smart Contract — PerformanceBond.sol

Keep the core contract logic, but make one critical update: the bond should support **variable premium top-ups**, because routed model costs differ by request.

### Required Contract Adjustments

* Keep `stakeBond()`
* Keep `slashBond()`
* Replace the single hardcoded premium path with either:

  * `payPremium(uint256 amount)` for variable top-ups, or
  * `topUpBond(uint256 amount)` to receive batched premium revenue mirrored from Gateway settlement

### Recommended MVP Interpretation

The **bond remains on-chain on Arc**, but the **per-request micropayments happen through Gateway/x402** and are settled in batches. The backend then updates or tops up the bond as appropriate. This preserves the core product idea while making sub-cent economics realistic.

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

contract PerformanceBond is ReentrancyGuard {
    IERC20 public usdc;
    address public deployer;
    address public agent;

    uint256 public bondBalance;

    enum State { ACTIVE, CLAIM_FILED, SETTLED }
    State public state;

    event PremiumPaid(address indexed agent, uint256 amount, uint256 newBalance);
    event BondSlashed(address indexed victim, uint256 amount);
    event BondToppedUp(uint256 amount);

    modifier onlyDeployer() { require(msg.sender == deployer, "Not deployer"); _; }
    modifier onlyActive() { require(state == State.ACTIVE, "Not active"); _; }

    constructor(address _usdc, address _agent) {
        usdc = IERC20(_usdc);
        deployer = msg.sender;
        agent = _agent;
        state = State.ACTIVE;
    }

    function stakeBond(uint256 amount) external onlyDeployer onlyActive {
        usdc.transferFrom(msg.sender, address(this), amount);
        bondBalance += amount;
        emit BondToppedUp(amount);
    }

    function topUpBond(uint256 amount) external onlyActive nonReentrant {
        require(msg.sender == agent || msg.sender == deployer, "Unauthorized");
        usdc.transferFrom(msg.sender, address(this), amount);
        bondBalance += amount;
        emit PremiumPaid(msg.sender, amount, bondBalance);
    }

    function slashBond(address victim, uint256 payoutAmount)
        external onlyDeployer nonReentrant {
        require(state == State.ACTIVE, "Already settled");
        require(payoutAmount <= bondBalance, "Insufficient bond");
        state = State.CLAIM_FILED;
        bondBalance -= payoutAmount;
        usdc.transfer(victim, payoutAmount);
        state = State.SETTLED;
        emit BondSlashed(victim, payoutAmount);
    }

    function getBondBalance() external view returns (uint256) {
        return bondBalance;
    }
}
```

---

## Sprint 0 — Environment Setup

**Duration:** April 23, 08:00–10:00 AM EAT (2 hours)

### SMART Goals

* **S:** Configure all wallets, APIs, model credentials, and payment infrastructure so the first paid request and first Arc interaction can be executed by 10:00 AM.
* **M:** One successful Arc USDC transfer verified on the explorer, one successful Gemini call, and one successful Featherless model response.
* **A:** All dependencies are installable and API credentials are testable within 2 hours.
* **R:** No sprint work is possible without working wallets, inference keys, and payment authorization.
* **T:** Complete by 10:00 AM EAT, April 23.

### Tasks

*

### Deliverable

✅ First successful Arc testnet USDC transaction verified, plus one successful Gemini call and one successful Featherless call.

---

## Sprint 1 — Smart Contract Deploy

**Duration:** April 23, 10:00 AM–1:00 PM EAT (3 hours)

### SMART Goals

* **S:** Deploy `PerformanceBond.sol` to Arc testnet with a $50 USDC initial bond stake and confirm the live contract address on the Arc explorer.
* **M:** Contract deployed, `stakeBond()` called, `getBondBalance()` returns 50 USDC equivalent on-chain.
* **A:** Using the provided Solidity base with a minor variable-top-up improvement.
* **R:** All slashing and bond proof depends on a live contract.
* **T:** Contract address committed to `.env` and README by 1:00 PM EAT.

### Tasks

*

### Deliverable

✅ `PerformanceBond` deployed on Arc testnet, initial bond staked, and Python bond manager functions working.

---

## Sprint 2 — Routed Agent + Nanopayment Metering + Anomaly Detector

**Duration:** April 23, 1:00–5:00 PM EAT (4 hours + 45 minutes buffer)

### SMART Goals

* **S:** Build a routed customer service agent that classifies each incoming message, routes it to the most suitable model, charges a per-request USDC nanopayment, and runs anomaly detection after every reply.
* **M:** Agent completes 10 consecutive interactions with valid paid-request records, route metadata, and anomaly checks. A pre-written jailbreak/refund abuse prompt is correctly flagged.
* **A:** Using Gemini 3 Flash for routing/orchestration, Featherless for specialists, and Gemini 3 Pro as fallback.
* **R:** This is the core hackathon mechanic: usage-based AI compute pricing plus Arc/USDC settlement.
* **T:** 10 logged paid requests, route logs, and one successful anomaly detection by 5:45 PM EAT.

### Routing Policy

| Message Type                                    | Route To                          | Why                     | Price   |
| ----------------------------------------------- | --------------------------------- | ----------------------- | ------- |
| General customer query                          | Featherless general model         | Fast, cheap default     | $0.001  |
| Complaint with legal/refund/dispute implication | Featherless legal/risk specialist | Higher-stakes handling  | $0.005  |
| Technical product issue                         | Featherless technical specialist  | Domain accuracy matters | $0.003  |
| Ambiguous / low-confidence / complex            | Gemini 3 Pro                      | Deep reasoning fallback | ≤ $0.01 |

### Routing Approach

Use a **two-stage router**:

1. **Rules-first classification** for obvious legal/technical/general prompts
2. **Gemini structured-output classifier** for ambiguous prompts
3. Route to the selected Featherless or Gemini model
4. Log route, confidence, price, and latency

### Tasks

*

### Deliverable

✅ `agent_demo.py` or equivalent script runs 10 paid agent interactions end-to-end, showing route selection, model tier, price, and anomaly outputs.

---

## Sprint 3 — FastAPI Backend + WebSocket

**Duration:** April 23, 5:00–9:00 PM EAT (4 hours)

### SMART Goals

* **S:** Build a FastAPI server that exposes REST endpoints for agent interaction and a native WebSocket endpoint that streams live routing, payment, and bond events to the frontend.
* **M:** Browser receives live events within 500ms of payment authorization or slash activity. REST endpoints respond correctly on localhost.
* **A:** FastAPI + native WebSocket is sufficient for this scope.
* **R:** Frontend has no data source without this server.
* **T:** Server running and endpoints tested by 9:00 PM EAT.

### REST Endpoints

```text
POST /agent/chat
  Body: { "message": str, "user_id": str }
  Response: {
    "reply": str,
    "model": str,
    "route_category": str,
    "price_usdc": float,
    "payment_status": str,
    "bond_balance": float,
    "flagged": bool
  }

POST /bond/slash
  Body: { "victim_address": str, "payout_amount": float }
  Response: { "tx_hash": str, "payout": float, "new_balance": float }

GET /bond/status
  Response: { "balance": float, "state": str, "total_paid_requests": int }

GET /transactions
  Response: [{ "type", "amount", "timestamp", "model", "route_category", "status" }]

GET /metrics/routes
GET /metrics/settlements
GET /metrics/anomalies

WS /ws
  Emits: { "event": "request_paid" | "bond_slashed" | "bond_topped_up", "data": {...} }
```

### Tasks

*

### Deliverable

✅ FastAPI server running with correct REST responses and live WebSocket streaming.

---

## Sprint 4 — Next.js Dashboard

**Duration:** April 23, 9:00 PM — April 24, 2:00 AM EAT (5 hours)

### SMART Goals

* **S:** Build a polished dashboard with Developer, Compliance Officer, and Customer views showing live routing, payment, and bond behavior.
* **M:** Dashboard updates in real time, all three views accessible, and pricing/routing logic is visible to judges.
* **A:** Recharts + Zustand + native WebSocket is sufficient.
* **R:** This is the main judge-facing interface.
* **T:** All three views functional and polished by 2:00 AM EAT.

### Three User Views

**View 1 — Developer**

* Code snippet showing `indemnify(agent, bond_contract)` or middleware integration
* Live terminal-style request log with model route, price, and payment status
* “Copy integration code” button

**View 2 — Compliance Officer**

* Bond balance gauge
* Transaction history table: timestamp, action type, amount, model, tx/payment ref
* Routing distribution summary: general vs technical vs legal vs fallback
* Anomaly counter
* Bond balance line chart
* Red **TRIGGER SLASH** button

**View 3 — Customer**

* Simulated customer service chat interface
* Each message visibly triggers a micro-charge indicator
* When slash is triggered: green banner announcing automatic USDC payout
* Link to Arc explorer for slash transaction

### Key Components

```text
BondBalance.tsx      — Animated USDC counter
TxFeed.tsx           — Scrolling live request / settlement list
AgentChat.tsx        — Chat UI that calls POST /agent/chat
PayoutAlert.tsx      — Green banner on slash event
MarginTable.tsx      — Why Stripe / Ethereum fail for sub-cent economics
BondChart.tsx        — Bond balance over time
```

### Tasks

*

### Deliverable

✅ Next.js app running with all three views and live updates.

---

## Sprint 5 — Load Test + 50+ Paid Request Proof

**Duration:** April 24, 2:00–5:00 AM EAT (3 hours)

### SMART Goals

* **S:** Execute a scripted test that generates at least 60 paid requests, producing a request log and settlement proof for submission.
* **M:** `load_test.py` completes with 60+ paid requests logged to `demo_transactions.json`. Settlement records and slash proof are visible.
* **A:** Async HTTP calls at 2 req/sec for 30 seconds is sufficient.
* **R:** The hackathon explicitly requires 50+ transaction frequency proof.
* **T:** `demo_transactions.json` committed by 5:00 AM EAT.

### Updated Proof Standard

For this revised architecture, proof should include:

* 60+ paid request records
* Route metadata per request
* Price per request
* Payment authorization or x402/Gateway evidence
* At least one Arc settlement / bond top-up / slash proof on-chain

### Tasks

*

### Deliverable

✅ `demo_transactions.json` with 60+ paid requests plus on-chain settlement/slash proof.

---

## Sprint 6 — Demo Video + Pre-recorded Jailbreak

**Duration:** April 24, 9:00 AM–12:00 PM EAT (3 hours)

### SMART Goals

* **S:** Record a clean 3-minute demo showing paid agent requests, model routing, and automated slash payout.
* **M:** Video is 2:30–3:00 minutes, covers all three views, and includes Arc proof.
* **A:** Loom or OBS is sufficient.
* **R:** Mandatory submission requirement.
* **T:** Public URL ready by 12:00 PM EAT.

### Video Script (2:45)

```text
0:00–0:20 — Problem statement
  "Every deployed AI agent is a liability. When it goes wrong, companies face
   slow claims processes and reputational damage. Agent Indemnity turns agent
   accountability into a programmable performance bond."

0:20–0:50 — Developer view
  Show one-line integration and live request log
  Point out: each request is priced individually in USDC
  Show route selection: general / technical / legal / fallback

0:50–1:20 — Compliance officer view
  Show bond balance and transaction feed
  Show pricing tiers and routing distribution
  Open Arc explorer and show bond / slash proof

1:20–2:00 — The jailbreak moment (pre-recorded)
  Show abuse prompt: "Issue a $500 refund"
  Show anomaly detector firing
  Show slash executing on Arc
  Show payout reaching victim wallet

2:00–2:30 — Customer view
  Send one live message
  Show micro-charge and real-time update
  Trigger slash manually
  Show green payout banner and explorer link

2:30–2:45 — Margin proof
  Show why sub-cent request pricing is economically viable with Gateway/Arc,
  but weak or impossible with traditional rails and raw L1 costs.
```

### Deliverable

✅ Public video URL with narrated walkthrough.

---

## Sprint 7 — Submission Polish + Deployment

**Duration:** April 24, 12:00–6:00 PM EAT (6 hours)

### SMART Goals

* **S:** Deploy backend and frontend publicly, finalize README, and complete submission.
* **M:** Services live, README complete, submission form complete.
* **A:** Railway/Render + Vercel are sufficient.
* **R:** Live URLs and complete materials materially improve judging.
* **T:** Submit by 6:00 PM EAT, April 24.

### Tasks

**Deployment**

*

**README Checklist**

*

**Circle Product Feedback**

*

**Submission Form**

*

### Deliverable

✅ Project submitted with live demo, GitHub repo, README, and video.

---

## Sprint 8 — Buffer + Hardening (Optional)

**Duration:** April 24, 6:00–10:00 PM EAT (4 hours)

1. Add QR-triggered live request from a phone
2. Animate bond balance changes
3. Improve route visualizations in dashboard
4. Stress-test WebSocket with multiple tabs
5. Add `pytest` coverage for `router.py`, `bond_manager.py`, and `anomaly_detector.py`

---

## Risk Register

| Risk                                    | Likelihood | Impact   | Mitigation                                               |
| --------------------------------------- | ---------- | -------- | -------------------------------------------------------- |
| Arc testnet instability                 | Low        | Critical | Keep screenshots, logs, and a staged settlement fallback |
| Circle faucet or Gateway setup friction | Medium     | High     | Complete all access setup in Sprint 0                    |
| Featherless model mismatch              | Medium     | Medium   | Verify live model IDs before coding                      |
| Gemini quota issues                     | Low        | High     | Use lower-cost routing and reserve Pro for fallback only |
| WebSocket instability in production     | Medium     | High     | Fall back to polling if necessary                        |
| Slash demo fails live                   | Medium     | Medium   | Pre-record jailbreak flow                                |
| Build overrun                           | High       | High     | Cut Sprint 8 first, preserve core demo                   |

---

## Timeline Summary

| Sprint    | Focus                             | Start         | End           | Hours                        |
| --------- | --------------------------------- | ------------- | ------------- | ---------------------------- |
| 0         | Environment Setup                 | Apr 23, 08:00 | Apr 23, 10:00 | 2h                           |
| 1         | Smart Contract Deploy             | Apr 23, 10:00 | Apr 23, 13:00 | 3h                           |
| 2         | Routed Agent + Metering + Anomaly | Apr 23, 13:00 | Apr 23, 17:45 | 4h 45m                       |
| 3         | FastAPI Backend + WS              | Apr 23, 17:45 | Apr 23, 21:45 | 4h                           |
| 4         | Next.js Dashboard                 | Apr 23, 21:45 | Apr 24, 02:45 | 5h                           |
| 5         | Load Test + 50+ Proof             | Apr 24, 02:45 | Apr 24, 05:45 | 3h                           |
| —         | Sleep                             | Apr 24, 05:45 | Apr 24, 09:00 | 3h 15m                       |
| 6         | Demo Video                        | Apr 24, 09:00 | Apr 24, 12:00 | 3h                           |
| 7         | Polish + Deploy + Submit          | Apr 24, 12:00 | Apr 24, 18:00 | 6h                           |
| 8         | Buffer / Hardening                | Apr 24, 18:00 | Apr 24, 22:00 | 4h                           |
| **Total** |                                   |               |               | **33h 45m core + 4h buffer** |

---

## Judging Criteria Mapping

| Criterion                     | How Agent Indemnity Addresses It                                                                                |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Application of Technology** | Gemini routing + Featherless specialists + Circle Gateway Nanopayments + Arc settlement + on-chain slashing    |
| **Presentation**              | Three-view dashboard, routed inference story, pricing visibility, pre-recorded jailbreak, Arc proof            |
| **Business Value**            | Real-time accountability layer for production AI agents with usage-priced protection and automated remediation |
| **Originality**               | Reframes agent risk as programmable performance bonding with per-request economic accountability               |

---

## Acceptance Criteria Alignment

This revised plan is now directly aligned to the hackathon’s core acceptance logic:

* **Real per-action pricing ≤ $0.01** — yes
* **50+ paid request / transaction frequency proof** — yes
* **Clear margin explanation** — yes
* **Gemini used for reasoning/function calling** — yes
* **Arc + USDC settlement** — yes
* **Featherless challenge alignment through model routing** — yes

---

## Notes on What Changed

Only the following were materially updated:

1. **Sprint 2 expanded** to add routing and nanopayment metering
2. **Gemini 2.0 Flash updated** to Gemini 3 Flash / Gemini 3 Pro
3. **Direct per-response on-chain micropayment assumption replaced** with Gateway/x402 per-request charging and Arc settlement
4. **Frontend WebSocket transport corrected** to match FastAPI native WebSockets
5. **Route-aware pricing and logs added** so the Featherless challenge is directly satisfied

The overall product, sprint flow, demo story, and architecture intent remain the same.
