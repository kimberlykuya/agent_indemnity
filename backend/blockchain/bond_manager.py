"""
blockchain/bond_manager.py
---------------------------
Admin interaction layer for the PerformanceBond contract.

Sprint 2: optional minimal helpers.
Sprint 3: slash_bond() will be wired to the FastAPI POST /bond/slash endpoint.
"""

import logging

from blockchain.arc_client import PERFORMANCE_BOND_ADDR, get_web3

logger = logging.getLogger(__name__)

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


def get_bond_balance() -> float:
    """Return on-chain bond balance in USDC (6 decimal places → float).

    Returns 0.0 and logs a warning if the contract is unreachable.
    """
    if not PERFORMANCE_BOND_ADDR:
        logger.warning({}, "PERFORMANCE_BOND_ADDRESS not set — returning 0.0")
        return 0.0
    try:
        w3 = get_web3()
        contract = _get_contract(w3)
        raw: int = contract.functions.getBondBalance().call()
        return raw / 1_000_000  # USDC has 6 decimal places
    except Exception as exc:
        logger.warning({"error": str(exc)}, "get_bond_balance failed")
        return 0.0


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
        logger.error("Failed to execute slashBond transaction: victim=%s amount=%s error=%s", victim_address, payout_amount_usdc, e)
        raise
