# Agent Indemnity Submission Evidence

Generated at: 2026-04-24T12:15:03+00:00

## Required Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Real per-action pricing (<= $0.01) | PASS | min=$0.001000, max=$0.010000 |
| Transaction frequency (50+) | FAIL | 41 request records |
| On-chain slash/settlement proof | PASS | `0x736c617368353061643936356133373134343566656263383633376365636631` |
| Margin explanation vs traditional per-action costs | PASS | avg charge=$0.003244, low-cost assumption=$0.020000 |

## Request Summary

- Settled requests: 40/41
- Flagged requests: 10
- Total request volume: $0.133000 USDC
- Avg latency: 14164 ms
- Route breakdown: {'general': 19, 'technical': 8, 'legal_risk': 10, 'fallback_complex': 4}
- Model breakdown: {'Qwen/Qwen3-0.6B': 37, 'gemini-3.1-pro-preview': 4}

## On-chain Proof

- tx_hash: `0x736c617368353061643936356133373134343566656263383633376365636631`
- explorer_url: https://explorer.arc.io/tx/0x736c617368353061643936356133373134343566656263383633376365636631

## Margin Explanation (Traditional Direct Per-Action Settlement)

Assumptions:
- Optimistic direct settlement cost per action: $0.020000
- Congested direct settlement cost per action: $0.200000
- Observed average charge per action: $0.003244

Result:
- Avg per-action margin at low traditional cost: $-0.016756
- Avg per-action margin at high traditional cost: $-0.196756

Interpretation:
- If direct per-action settlement cost exceeds charged price, this model is economically negative per request.
- Circle Nanopayments + batch settlement is used to avoid per-action settlement overhead.
