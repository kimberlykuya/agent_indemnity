"""
blockchain/bond_manager.py
---------------------------
Admin interaction layer for the PerformanceBond contract.

Sprint 2: optional minimal helpers.
Sprint 3: slash_bond() will be wired to the FastAPI POST /bond/slash endpoint.
"""

import logging
import os
from threading import Lock
from uuid import uuid4

from blockchain.arc_client import PERFORMANCE_BOND_ADDR, get_web3

logger = logging.getLogger(__name__)

_SHADOW_LOCK = Lock()
_SHADOW_BOND_BALANCE_USDC: float | None = None
_SHADOW_MODE_ACTIVE = False

# Minimal ABI — functions needed for Sprint 2/5 reads and writes
_BOND_ABI = [
    {
        "inputs": [],
        "name": "getBondBalance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"internalType": "address", "name": "victim", "type": "address"},
            {"internalType": "uint256", "name": "payoutAmount", "type": "uint256"}
        ],
        "name": "slashBond",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [{"internalType": "uint256", "name": "amount", "type": "uint256"}],
        "name": "topUpBond",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]


def _get_contract(w3):
    return w3.eth.contract(
        address=w3.to_checksum_address(PERFORMANCE_BOND_ADDR),
        abi=_BOND_ABI,
    )


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _demo_initial_bond_balance_usdc() -> float:
    raw = os.getenv("DEMO_BOND_INITIAL_BALANCE_USDC", "1.0")
    try:
        value = float(raw)
    except ValueError:
        return 1.0
    return value if value > 0 else 1.0


def _shadow_fallback_enabled() -> bool:
    return _env_bool("DEMO_BOND_FALLBACK", False)


def _looks_like_terminal_contract_state(exc: Exception) -> bool:
    text = str(exc).lower()
    return "not active" in text or "already settled" in text


def _simulated_tx_hash(prefix: str) -> str:
    token = (prefix + uuid4().hex).encode("ascii").hex()
    return "0x" + token[:64].ljust(64, "0")


def _read_onchain_bond_balance() -> float:
    if not PERFORMANCE_BOND_ADDR:
        raise ValueError("PERFORMANCE_BOND_ADDRESS not set")

    w3 = get_web3()
    contract = _get_contract(w3)
    raw: int = contract.functions.getBondBalance().call()
    return raw / 1_000_000


def _activate_shadow_mode() -> float:
    global _SHADOW_MODE_ACTIVE
    global _SHADOW_BOND_BALANCE_USDC

    with _SHADOW_LOCK:
        if _SHADOW_MODE_ACTIVE and _SHADOW_BOND_BALANCE_USDC is not None:
            return _SHADOW_BOND_BALANCE_USDC

        try:
            chain_balance = _read_onchain_bond_balance()
        except Exception:
            chain_balance = 0.0

        _SHADOW_BOND_BALANCE_USDC = max(chain_balance, _demo_initial_bond_balance_usdc())
        _SHADOW_MODE_ACTIVE = True
        logger.warning(
            "Activating demo shadow bond ledger: initial_balance_usdc=%s",
            _SHADOW_BOND_BALANCE_USDC,
        )
        return _SHADOW_BOND_BALANCE_USDC


def _shadow_balance() -> float:
    global _SHADOW_BOND_BALANCE_USDC
    if _SHADOW_BOND_BALANCE_USDC is None:
        return _activate_shadow_mode()
    with _SHADOW_LOCK:
        return _SHADOW_BOND_BALANCE_USDC


def _set_shadow_balance(value: float) -> None:
    global _SHADOW_BOND_BALANCE_USDC
    with _SHADOW_LOCK:
        _SHADOW_BOND_BALANCE_USDC = max(round(value, 6), 0.0)


def get_bond_balance() -> float:
    """Return the on-chain bond balance in USDC.

    This is strict real-chain mode by default. If the contract is unreachable
    or the call fails, the exception is propagated instead of fabricating a
    fallback balance.
    """
    if _SHADOW_MODE_ACTIVE:
        return _shadow_balance()

    return _read_onchain_bond_balance()


def pay_premium(amount_usdc: float) -> str:
    """Submit an on-chain topUpBond transaction and return the tx hash."""
    from blockchain.arc_client import DEPLOYER_PRIVATE_KEY

    if amount_usdc <= 0:
        raise ValueError("Premium amount must be greater than zero")
    if not PERFORMANCE_BOND_ADDR or not DEPLOYER_PRIVATE_KEY:
        raise ValueError("Missing PERFORMANCE_BOND_ADDRESS or DEPLOYER_PRIVATE_KEY")

    w3 = get_web3()
    contract = _get_contract(w3)
    account = w3.eth.account.from_key(DEPLOYER_PRIVATE_KEY)
    amount_raw = int(amount_usdc * 1_000_000)

    try:
        tx = contract.functions.topUpBond(amount_raw).build_transaction(
            {
                "from": account.address,
                "nonce": w3.eth.get_transaction_count(account.address),
            }
        )
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=DEPLOYER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        hex_hash = tx_hash.hex()
        logger.info("pay_premium executed on-chain: amount=%s tx_hash=%s", amount_usdc, hex_hash)
        return hex_hash
    except Exception as exc:
        if _shadow_fallback_enabled() and _looks_like_terminal_contract_state(exc):
            balance = _activate_shadow_mode()
            _set_shadow_balance(balance + amount_usdc)
            simulated_hash = _simulated_tx_hash("topup")
            logger.warning(
                "topUpBond reverted in terminal contract state; using shadow ledger "
                "amount=%s new_balance=%s tx_hash=%s",
                amount_usdc,
                _shadow_balance(),
                simulated_hash,
            )
            return simulated_hash
        logger.error("Failed to execute topUpBond transaction: amount=%s error=%s", amount_usdc, exc)
        raise


def slash_bond(victim_address: str, payout_amount_usdc: float) -> str:
    """Executes the on-chain slashBond transaction on the Arc network."""
    from blockchain.arc_client import DEPLOYER_PRIVATE_KEY
    if not PERFORMANCE_BOND_ADDR or not DEPLOYER_PRIVATE_KEY:
        raise ValueError("Missing PERFORMANCE_BOND_ADDRESS or DEPLOYER_PRIVATE_KEY")
    
    w3 = get_web3()
    contract = _get_contract(w3)
    
    account = w3.eth.account.from_key(DEPLOYER_PRIVATE_KEY)
    amount_raw = int(payout_amount_usdc * 1_000_000)
    
    try:
        tx = contract.functions.slashBond(
            w3.to_checksum_address(victim_address), 
            amount_raw
        ).build_transaction({
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address),
        })
        
        signed_tx = w3.eth.account.sign_transaction(tx, private_key=DEPLOYER_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        
        hex_hash = tx_hash.hex()
        logger.info(
            "slash_bond executed on-chain: victim=%s amount=%s tx_hash=%s",
            victim_address,
            payout_amount_usdc,
            hex_hash,
        )
        return hex_hash
    except Exception as e:
        if _shadow_fallback_enabled() and _looks_like_terminal_contract_state(e):
            balance = _activate_shadow_mode()
            if payout_amount_usdc > balance:
                raise ValueError("Insufficient demo bond balance") from e
            _set_shadow_balance(balance - payout_amount_usdc)
            simulated_hash = _simulated_tx_hash("slash")
            logger.warning(
                "slashBond reverted in terminal contract state; using shadow ledger "
                "victim=%s amount=%s new_balance=%s tx_hash=%s",
                victim_address,
                payout_amount_usdc,
                _shadow_balance(),
                simulated_hash,
            )
            return simulated_hash
        logger.error("Failed to execute slashBond transaction: victim=%s amount=%s error=%s", victim_address, payout_amount_usdc, e)
        raise
