# Agent Indemnity

**Agent Indemnity** instruments deployed AI agents with a USDC-backed performance bond on the Arc network. 

Rather than traditional insurance, it acts as a **programmable performance bond** with automated slashing. Every outbound agent action incurs a sub-cent usage charge authorized via Circle Gateway Nanopayments and settled on Arc. If an agent behaves anomalously (e.g., hallucination, unauthorized action), a configurable trigger automatically slashes the bond and releases USDC directly to the affected party—ensuring instant accountability with no claims process or human adjudication delay.

**Key Features:**
- **Programmable Accountability**: Automated slashing, similar to validator slashing in blockchain systems.
- **Micro-priced Inference**: Per-request USDC pricing using Circle Gateway Nanopayments + x402.
- **Smart Model Routing**: Routes requests to cost-efficient specialist models (via Featherless) or deep reasoning fallback (Gemini 3 Flash/Pro).
- **On-chain Settlement**: USDC-backed bond enforcement via Arc smart contracts.
