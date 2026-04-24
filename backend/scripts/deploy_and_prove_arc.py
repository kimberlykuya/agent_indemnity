from __future__ import annotations

import json
import os
import pathlib
import sys
from datetime import datetime, timezone

from web3 import Web3

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from backend.blockchain.arc_client import DEPLOYER_PRIVATE_KEY, USDC_CONTRACT_ADDR, get_web3

ROOT = pathlib.Path(__file__).resolve().parents[2]
ARTIFACT_PATH = ROOT / "artifacts" / "contracts" / "PerformanceBond.sol" / "PerformanceBond.json"
LOGS_DIR = ROOT / "backend" / "logs"
ARC_EXPLORER_TX_BASE = "https://testnet.arcscan.app/tx"
SUBMISSION_EVIDENCE_JSON = LOGS_DIR / "submission_evidence.json"
ARC_PROOF_JSON = LOGS_DIR / "arc_proof.json"

ERC20_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "spender", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "owner", "type": "address"},
            {"internalType": "address", "name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def _load_json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text())


def _require_address(value: str, name: str) -> str:
    if not value or not Web3.is_address(value):
        raise RuntimeError(f"Invalid {name}")
    return Web3.to_checksum_address(value)


def _seed_amount_raw(balance_raw: int) -> int:
    seed = min(balance_raw, 1_000)
    if seed <= 0:
        raise RuntimeError("Deployer has no USDC balance to seed a bond")
    return seed


def _fee_defaults(w3: Web3) -> dict[str, int]:
    gas_price = int(w3.eth.gas_price)
    priority = max(1_500_000_000, gas_price // 10)
    return {
        "maxPriorityFeePerGas": priority,
        "maxFeePerGas": max(gas_price * 2, gas_price + priority),
    }


def _send_tx(w3: Web3, account, private_key: str, tx: dict, label: str) -> tuple[str, object]:
    prepared = dict(tx)
    prepared["chainId"] = w3.eth.chain_id
    prepared["nonce"] = w3.eth.get_transaction_count(account.address, "pending")
    prepared["gas"] = int(w3.eth.estimate_gas(prepared) * 1.2)
    prepared.update(_fee_defaults(w3))
    signed = w3.eth.account.sign_transaction(prepared, private_key=private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
    if receipt.status != 1:
        raise RuntimeError(f"{label} reverted")
    hash_hex = tx_hash.hex()
    if not hash_hex.startswith("0x"):
        hash_hex = f"0x{hash_hex}"
    return hash_hex, receipt


def _sync_submission_evidence(arc_proof: dict) -> None:
    evidence = json.loads(SUBMISSION_EVIDENCE_JSON.read_text())
    evidence["generated_at"] = arc_proof["timestamp"]
    evidence.setdefault("criteria", {}).setdefault("onchain_slash_proof", {})["pass"] = True
    evidence.setdefault("slash_proof", {})["tx_hash"] = arc_proof["tx_hash"]
    evidence["slash_proof"]["explorer_url"] = arc_proof["arc_explorer_url"]
    SUBMISSION_EVIDENCE_JSON.write_text(json.dumps(evidence, indent=2))


def main() -> int:
    if not ARTIFACT_PATH.exists():
        raise RuntimeError(f"Missing contract artifact: {ARTIFACT_PATH}")

    if not DEPLOYER_PRIVATE_KEY:
        raise RuntimeError("DEPLOYER_PRIVATE_KEY is not configured")
    if not USDC_CONTRACT_ADDR:
        raise RuntimeError("USDC_CONTRACT_ADDRESS is not configured")

    artifact = _load_json(ARTIFACT_PATH)
    abi = artifact["abi"]
    bytecode = artifact["bytecode"]

    w3 = get_web3()
    if not w3.is_connected():
        raise RuntimeError("Arc RPC is not reachable")

    deployer = w3.eth.account.from_key(DEPLOYER_PRIVATE_KEY)
    usdc_addr = _require_address(USDC_CONTRACT_ADDR, "USDC_CONTRACT_ADDRESS")
    agent_address = os.getenv("AGENT_WALLET_ADDRESS") or deployer.address
    if not Web3.is_address(agent_address):
        agent_address = deployer.address
    agent_address = Web3.to_checksum_address(agent_address)
    victim_address = os.getenv("VICTIM_WALLET_ADDRESS") or "0x191cc4e34e54444b9e10f4e3311c87382b0c0654"
    if not Web3.is_address(victim_address):
        victim_address = "0x191cc4e34e54444b9e10f4e3311c87382b0c0654"
    victim_address = Web3.to_checksum_address(victim_address)

    usdc = w3.eth.contract(address=usdc_addr, abi=ERC20_ABI)
    deployer_balance_raw = int(usdc.functions.balanceOf(deployer.address).call())
    amount_raw = _seed_amount_raw(deployer_balance_raw)
    amount_usdc = amount_raw / 1_000_000

    print(f"Deploying fresh PerformanceBond for proof...")
    contract_factory = w3.eth.contract(abi=abi, bytecode=bytecode)
    deploy_tx = contract_factory.constructor(usdc_addr, agent_address).build_transaction(
        {"from": deployer.address}
    )
    deploy_hash, deploy_receipt = _send_tx(w3, deployer, DEPLOYER_PRIVATE_KEY, deploy_tx, "deploy")
    contract_address = Web3.to_checksum_address(deploy_receipt.contractAddress)
    print(f"  Deployed contract: {contract_address}")
    print(f"  Deploy tx: {deploy_hash}")

    bond = w3.eth.contract(address=contract_address, abi=abi)
    allowance = int(usdc.functions.allowance(deployer.address, contract_address).call())
    if allowance < amount_raw:
        approve_tx = usdc.functions.approve(contract_address, amount_raw).build_transaction(
            {"from": deployer.address}
        )
        approve_hash, _ = _send_tx(w3, deployer, DEPLOYER_PRIVATE_KEY, approve_tx, "approve")
        print(f"  Approve tx: {approve_hash}")

    stake_tx = bond.functions.stakeBond(amount_raw).build_transaction({"from": deployer.address})
    stake_hash, _ = _send_tx(w3, deployer, DEPLOYER_PRIVATE_KEY, stake_tx, "stakeBond")
    print(f"  Stake tx: {stake_hash}")

    slash_tx = bond.functions.slashBond(victim_address, amount_raw).build_transaction(
        {"from": deployer.address}
    )
    slash_hash, _ = _send_tx(w3, deployer, DEPLOYER_PRIVATE_KEY, slash_tx, "slashBond")
    print(f"  Slash tx: {slash_hash}")

    bond_balance_after = float(bond.functions.getBondBalance().call()) / 1_000_000
    timestamp = datetime.now(timezone.utc).isoformat()
    arc_proof = {
        "event_type": "bond_slashed",
        "tx_hash": slash_hash,
        "arc_explorer_url": f"{ARC_EXPLORER_TX_BASE}/{slash_hash}",
        "amount_usdc": amount_usdc,
        "timestamp": timestamp,
        "bond_balance_after": bond_balance_after,
        "contract_address": contract_address,
        "deploy_tx_hash": deploy_hash,
        "stake_tx_hash": stake_hash,
    }

    ARC_PROOF_JSON.write_text(json.dumps(arc_proof, indent=2))
    _sync_submission_evidence(arc_proof)

    print(f"\nSaved proof: {ARC_PROOF_JSON}")
    print(f"Explorer: {arc_proof['arc_explorer_url']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1)
