"""
generate_submission_evidence.py
--------------------------------
Builds a hackathon-ready evidence pack from local demo artifacts.

Inputs:
  - backend/logs/demo_transactions.json
  - backend/logs/load_test_results.json (optional, for slash tx proof)

Outputs:
  - backend/logs/submission_evidence.json
  - backend/logs/submission_evidence.md
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TRANSACTIONS = ROOT / "backend" / "logs" / "demo_transactions.json"
DEFAULT_LOAD_RESULTS = ROOT / "backend" / "logs" / "load_test_results.json"
DEFAULT_OUTPUT_JSON = ROOT / "backend" / "logs" / "submission_evidence.json"
DEFAULT_OUTPUT_MD = ROOT / "backend" / "logs" / "submission_evidence.md"
DEFAULT_EXPLORER_BASE = "https://explorer.arc.io/tx"
DEFAULT_TRADITIONAL_COST_LOW = 0.02
DEFAULT_TRADITIONAL_COST_HIGH = 0.20


def _read_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError(f"Expected JSON array in {path}")
    return [item for item in raw if isinstance(item, dict)]


def _round(value: float, digits: int = 6) -> float:
    return round(float(value), digits)


def _safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _find_slash(load_results: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in load_results:
        if item.get("type") == "slash" and item.get("success") and item.get("tx_hash"):
            return item
    return None


def _format_status(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _build_markdown(summary: dict[str, Any]) -> str:
    criteria = summary["criteria"]
    stats = summary["stats"]
    pricing = summary["pricing_economics"]
    slash = summary["slash_proof"]

    explorer_line = "None captured yet."
    if slash["tx_hash"]:
        explorer_line = f'{slash["tx_hash"]}\n- Explorer: {slash["explorer_url"]}'

    return f"""# Agent Indemnity Submission Evidence

Generated at: {summary["generated_at"]}

## Required Criteria

| Criterion | Status | Evidence |
| --- | --- | --- |
| Real per-action pricing (<= $0.01) | {_format_status(criteria["per_action_pricing_leq_0_01"]["pass"])} | min=${stats["price_min_usdc"]:.6f}, max=${stats["price_max_usdc"]:.6f} |
| Transaction frequency (50+) | {_format_status(criteria["transaction_frequency_50_plus"]["pass"])} | {stats["total_requests"]} request records |
| On-chain slash/settlement proof | {_format_status(criteria["onchain_slash_proof"]["pass"])} | {explorer_line} |
| Margin explanation vs traditional per-action costs | {_format_status(criteria["traditional_cost_margin_gap"]["pass"])} | avg charge=${pricing["average_price_usdc"]:.6f}, low-cost assumption=${pricing["traditional_cost_low_usdc"]:.6f} |

## Request Summary

- Settled requests: {stats["settled_requests"]}/{stats["total_requests"]}
- Flagged requests: {stats["flagged_requests"]}
- Total request volume: ${stats["total_volume_usdc"]:.6f} USDC
- Avg latency: {stats["avg_latency_ms"]} ms
- Route breakdown: {stats["route_counts"]}
- Model breakdown: {stats["model_counts"]}

## Margin Explanation (Traditional Direct Per-Action Settlement)

Assumptions:
- Optimistic direct settlement cost per action: ${pricing["traditional_cost_low_usdc"]:.6f}
- Congested direct settlement cost per action: ${pricing["traditional_cost_high_usdc"]:.6f}
- Observed average charge per action: ${pricing["average_price_usdc"]:.6f}

Result:
- Avg per-action margin at low traditional cost: ${pricing["avg_margin_at_low_cost_usdc"]:.6f}
- Avg per-action margin at high traditional cost: ${pricing["avg_margin_at_high_cost_usdc"]:.6f}

Interpretation:
- If direct per-action settlement cost exceeds charged price, this model is economically negative per request.
- Circle Nanopayments + batch settlement is used to avoid per-action settlement overhead.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate hackathon submission evidence artifacts.")
    parser.add_argument("--transactions", type=Path, default=DEFAULT_TRANSACTIONS)
    parser.add_argument("--load-results", type=Path, default=DEFAULT_LOAD_RESULTS)
    parser.add_argument("--out-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--out-md", type=Path, default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--explorer-base", default=DEFAULT_EXPLORER_BASE)
    parser.add_argument("--traditional-cost-low", type=float, default=DEFAULT_TRADITIONAL_COST_LOW)
    parser.add_argument("--traditional-cost-high", type=float, default=DEFAULT_TRADITIONAL_COST_HIGH)
    args = parser.parse_args()

    tx_rows = _read_json_array(args.transactions)
    load_rows = _read_json_array(args.load_results)
    slash_record = _find_slash(load_rows)

    prices = [_safe_float(row.get("price_usdc")) for row in tx_rows]
    latencies = [_safe_float(row.get("latency_ms")) for row in tx_rows if row.get("latency_ms") is not None]
    total_requests = len(tx_rows)
    settled_requests = sum(1 for row in tx_rows if row.get("payment_status") == "settled")
    flagged_requests = sum(1 for row in tx_rows if bool(row.get("flagged")))
    total_volume = _round(sum(prices))

    route_counts = dict(Counter(str(row.get("route_category", "unknown")) for row in tx_rows))
    model_counts = dict(Counter(str(row.get("model", "unknown")) for row in tx_rows))

    price_min = min(prices) if prices else 0.0
    price_max = max(prices) if prices else 0.0
    price_avg = _round(total_volume / total_requests, 6) if total_requests else 0.0

    low_cost = float(args.traditional_cost_low)
    high_cost = float(args.traditional_cost_high)
    margin_low = _round(price_avg - low_cost)
    margin_high = _round(price_avg - high_cost)

    slash_hash = str(slash_record.get("tx_hash")) if slash_record else None
    explorer_url = (
        f"{args.explorer_base.rstrip('/')}/{slash_hash}"
        if slash_hash
        else None
    )

    criteria = {
        "per_action_pricing_leq_0_01": {
            "pass": bool(prices) and price_max <= 0.01 and price_min > 0.0,
        },
        "transaction_frequency_50_plus": {
            "pass": total_requests >= 50,
        },
        "onchain_slash_proof": {
            "pass": bool(slash_hash),
        },
        "traditional_cost_margin_gap": {
            "pass": bool(prices) and all(price < low_cost for price in set(prices)),
        },
    }

    summary: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "transactions_path": str(args.transactions),
            "load_results_path": str(args.load_results),
        },
        "criteria": criteria,
        "stats": {
            "total_requests": total_requests,
            "settled_requests": settled_requests,
            "flagged_requests": flagged_requests,
            "price_min_usdc": _round(price_min),
            "price_max_usdc": _round(price_max),
            "price_avg_usdc": _round(price_avg),
            "total_volume_usdc": total_volume,
            "avg_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
            "route_counts": route_counts,
            "model_counts": model_counts,
        },
        "slash_proof": {
            "tx_hash": slash_hash,
            "explorer_url": explorer_url,
        },
        "pricing_economics": {
            "average_price_usdc": _round(price_avg),
            "traditional_cost_low_usdc": _round(low_cost),
            "traditional_cost_high_usdc": _round(high_cost),
            "avg_margin_at_low_cost_usdc": margin_low,
            "avg_margin_at_high_cost_usdc": margin_high,
        },
    }

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    args.out_md.write_text(_build_markdown(summary), encoding="utf-8")

    print(f"Evidence JSON written to: {args.out_json}")
    print(f"Evidence Markdown written to: {args.out_md}")
    print(f"50+ frequency pass: {criteria['transaction_frequency_50_plus']['pass']}")
    print(f"On-chain slash proof present: {criteria['onchain_slash_proof']['pass']}")


if __name__ == "__main__":
    main()
