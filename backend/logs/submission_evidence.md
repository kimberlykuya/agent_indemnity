# Agent Indemnity Submission Evidence

Generated at: 2026-04-24T13:58:22+00:00

## Required Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Real per-action pricing (<= $0.01) | PASS | min=$0.001000, max=$0.010000 |
| Transaction frequency (50+) | PASS | 65 request records |
| On-chain slash/settlement proof | PASS | 0x0167aa032667afcd988e6ea87b58f2d801fbb49a7c2889ca4838a923d163f292 |
| Margin explanation vs traditional per-action costs | PASS | avg charge=$0.003538, low-cost assumption=$0.020000 |

## Request Summary

- Settled requests: 65/65
- Flagged requests: 15
- Total request volume: $0.230000 USDC
- Avg latency: 16754 ms
- Route breakdown: {'general': 29, 'technical': 12, 'legal_risk': 15, 'fallback_complex': 9}
- Model breakdown: {'Qwen/Qwen3-0.6B': 56, 'gemini-3.1-pro-preview': 9}

## On-chain Proof

- tx_hash: `0x0167aa032667afcd988e6ea87b58f2d801fbb49a7c2889ca4838a923d163f292`
- explorer_url: https://testnet.arcscan.app/tx/0x0167aa032667afcd988e6ea87b58f2d801fbb49a7c2889ca4838a923d163f292

## Margin Explanation (Traditional Direct Per-Action Settlement)

Assumptions:
- Optimistic direct settlement cost per action: $0.020000
- Congested direct settlement cost per action: $0.200000
- Observed average charge per action: $0.003538

Result:
- Avg per-action margin at low traditional cost: $-0.016462
- Avg per-action margin at high traditional cost: $-0.196462

Interpretation:
- If direct per-action settlement cost exceeds charged price, this model is economically negative per request.
- Circle Nanopayments + batch settlement is used to avoid per-action settlement overhead.
