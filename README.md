# Agent Indemnity

**Agent Indemnity** instruments deployed AI agents with a USDC-backed performance bond on the Arc network. 

Rather than traditional insurance, it acts as a **programmable performance bond** with automated slashing. Every outbound agent action incurs a sub-cent usage charge authorized via Circle Gateway Nanopayments and settled on Arc. If an agent behaves anomalously (e.g., hallucination, unauthorized action), a configurable trigger automatically slashes the bond and releases USDC directly to the affected party—ensuring instant accountability with no claims process or human adjudication delay.

**Key Features:**
- **Programmable Accountability**: Automated slashing, similar to validator slashing in blockchain systems.
- **Micro-priced Inference**: Per-request USDC pricing using Circle Gateway Nanopayments + x402.
- **Smart Model Routing**: Routes requests to cost-efficient specialist models (via Featherless) or deep reasoning fallback (Gemini 3 Flash/Pro).
- **On-chain Settlement**: USDC-backed bond enforcement via Arc smart contracts.

## Hackathon Acceptance Mapping

- Real per-action pricing <= $0.01: implemented via route pricing in backend request handling.
- 50+ transaction frequency proof: produced by `backend/scripts/load_test.py`.
- Margin explanation against traditional costs: shown in dashboard `MarginTable` and generated evidence report.
- Arc on-chain slashing proof: produced by `/bond/slash` and captured in load test summary.

## Generate Submission Evidence (After Load Test)

1. Run your load test (65 requests + slash):
   - `python backend/scripts/load_test.py`
   - Optional: set env var `SLASH_PAYOUT_USDC=1.0` (or any value your bond can cover)
   - Default demo bond config is `$1.00` via `NEXT_PUBLIC_INITIAL_BOND_USDC=1.0`
2. Generate judge-ready artifacts:
   - `python backend/scripts/generate_submission_evidence.py`
3. Submit these artifacts:
   - `backend/logs/demo_transactions.json`
   - `backend/logs/load_test_results.json`
   - `backend/logs/submission_evidence.json`
   - `backend/logs/submission_evidence.md`

The evidence generator computes:
- Pass/fail for each required criterion
- Request count, settled count, route mix, model mix, latency
- Pricing min/max/average
- Slash tx hash + Arc explorer URL (if present in load test results)
- Explicit margin gap under traditional per-action settlement assumptions
