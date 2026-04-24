"""
scripts/generate_arc_proof.py
-------------------------------
Attempts to read on-chain bond balance. If the contract is reachable and has been
interacted with, records the proof. Otherwise triggers a topUpBond() or slash via
the API and records the resulting tx hash.

Output: backend/logs/arc_proof.json
"""

import json
import pathlib
import sys
import time

import httpx

API_URL = "http://localhost:8000"
LOGS_DIR = pathlib.Path(__file__).parent.parent / "logs"
ARC_EXPLORER_TX_BASE = "https://explorer.arc.io/tx"
SUBMISSION_EVIDENCE_JSON = LOGS_DIR / "submission_evidence.json"
SUBMISSION_EVIDENCE_MD = LOGS_DIR / "submission_evidence.md"


def _get_bond_status(client: httpx.Client) -> dict:
    resp = client.get(f"{API_URL}/bond/status", timeout=10.0)
    resp.raise_for_status()
    return resp.json()


def _trigger_slash(client: httpx.Client) -> dict:
    resp = client.post(
        f"{API_URL}/bond/slash",
        json={
            "victim_address": "0x191cc4e34e54444b9e10f4e3311c87382b0c0654",
            "payout_amount": 0.01,
        },
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json()


def _load_json(path: pathlib.Path, default: dict) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return default


def _render_submission_evidence(evidence: dict) -> str:
    criteria = evidence.get("criteria", {})
    stats = evidence.get("stats", {})
    slash_proof = evidence.get("slash_proof", {})

    def _pass_flag(key: str) -> str:
        return "PASS" if criteria.get(key, {}).get("pass") else "FAIL"

    tx_hash = slash_proof.get("tx_hash")
    explorer_url = slash_proof.get("explorer_url")

    lines = [
        "# Agent Indemnity Submission Evidence",
        "",
        f"Generated at: {evidence.get('generated_at', '')}",
        "",
        "## Required Criteria",
        "",
        "| Criterion | Status | Evidence |",
        "| --- | --- | --- |",
        f"| Real per-action pricing (<= $0.01) | {_pass_flag('per_action_pricing_leq_0_01')} | min=${stats.get('price_min_usdc', 0):.6f}, max=${stats.get('price_max_usdc', 0):.6f} |",
        f"| Transaction frequency (50+) | {_pass_flag('transaction_frequency_50_plus')} | {stats.get('total_requests', 0)} request records |",
        f"| On-chain slash/settlement proof | {_pass_flag('onchain_slash_proof')} | {tx_hash or 'None captured yet.'} |",
        f"| Margin explanation vs traditional per-action costs | {_pass_flag('traditional_cost_margin_gap')} | avg charge=${stats.get('price_avg_usdc', 0):.6f}, low-cost assumption=${evidence.get('pricing_economics', {}).get('traditional_cost_low_usdc', 0):.6f} |",
        "",
        "## Request Summary",
        "",
        f"- Settled requests: {stats.get('settled_requests', 0)}/{stats.get('total_requests', 0)}",
        f"- Flagged requests: {stats.get('flagged_requests', 0)}",
        f"- Total request volume: ${stats.get('total_volume_usdc', 0):.6f} USDC",
        f"- Avg latency: {stats.get('avg_latency_ms', 0)} ms",
        f"- Route breakdown: {stats.get('route_counts', {})}",
        f"- Model breakdown: {stats.get('model_counts', {})}",
        "",
        "## On-chain Proof",
        "",
        f"- tx_hash: `{tx_hash or ''}`",
        f"- explorer_url: {explorer_url or ''}",
        "",
        "## Margin Explanation (Traditional Direct Per-Action Settlement)",
        "",
        "Assumptions:",
        f"- Optimistic direct settlement cost per action: ${evidence.get('pricing_economics', {}).get('traditional_cost_low_usdc', 0):.6f}",
        f"- Congested direct settlement cost per action: ${evidence.get('pricing_economics', {}).get('traditional_cost_high_usdc', 0):.6f}",
        f"- Observed average charge per action: ${stats.get('price_avg_usdc', 0):.6f}",
        "",
        "Result:",
        f"- Avg per-action margin at low traditional cost: ${evidence.get('pricing_economics', {}).get('avg_margin_at_low_cost_usdc', 0):.6f}",
        f"- Avg per-action margin at high traditional cost: ${evidence.get('pricing_economics', {}).get('avg_margin_at_high_cost_usdc', 0):.6f}",
        "",
        "Interpretation:",
        "- If direct per-action settlement cost exceeds charged price, this model is economically negative per request.",
        "- Circle Nanopayments + batch settlement is used to avoid per-action settlement overhead.",
        "",
    ]
    return "\n".join(lines)


def _sync_submission_evidence(arc_proof: dict) -> None:
    evidence = _load_json(SUBMISSION_EVIDENCE_JSON, {})
    if not evidence:
        evidence = {
            "generated_at": arc_proof.get("timestamp"),
            "inputs": {},
            "criteria": {},
            "stats": {},
            "slash_proof": {},
            "pricing_economics": {},
        }

    criteria = evidence.setdefault("criteria", {})
    criteria.setdefault("onchain_slash_proof", {})["pass"] = bool(arc_proof.get("tx_hash"))
    slash_proof = evidence.setdefault("slash_proof", {})
    slash_proof["tx_hash"] = arc_proof.get("tx_hash")
    slash_proof["explorer_url"] = arc_proof.get("arc_explorer_url")
    evidence["generated_at"] = arc_proof.get("timestamp")

    SUBMISSION_EVIDENCE_JSON.write_text(json.dumps(evidence, indent=2))
    SUBMISSION_EVIDENCE_MD.write_text(_render_submission_evidence(evidence))


def main():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    with httpx.Client() as client:
        try:
            client.get(f"{API_URL}/health", timeout=5.0).raise_for_status()
        except Exception as exc:
            print(f"ERROR: FastAPI server not reachable at {API_URL}: {exc}")
            sys.exit(1)

        # Try to trigger a slash to get a tx hash
        print("Triggering bond slash for arc proof...")
        try:
            slash_result = _trigger_slash(client)
            tx_hash = slash_result.get("tx_hash", "")
            payout = slash_result.get("payout", 0.0)
            event_type = "bond_slashed"
            amount_usdc = payout
            print(f"  Slash result: tx_hash={tx_hash}, payout={payout}")
        except Exception as exc:
            print(f"  Slash failed: {exc}")
            tx_hash = ""
            event_type = "bond_status_check"
            amount_usdc = 0.0

        # Get bond status
        bond_status = _get_bond_status(client)
        print(f"  Bond balance: {bond_status.get('balance')} USDC")

        arc_proof = {
            "event_type": event_type,
            "tx_hash": tx_hash,
            "arc_explorer_url": f"{ARC_EXPLORER_TX_BASE}/{tx_hash}" if tx_hash else None,
            "amount_usdc": amount_usdc,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
            "bond_balance_after": bond_status.get("balance"),
        }

        proof_path = LOGS_DIR / "arc_proof.json"
        proof_path.write_text(json.dumps(arc_proof, indent=2))
        _sync_submission_evidence(arc_proof)
        print(f"\nSaved: {proof_path}")


if __name__ == "__main__":
    main()
