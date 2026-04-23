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

# Minimal ABI — only the functions needed for Sprint 2 reads
_BOND_ABI = [
    {
        "inputs": [],
        "name": "getBondBalance",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    }
]


def get_bond_balance() -> float:
    """Return on-chain bond balance in USDC (6 decimal places → float).

    Returns 0.0 and logs a warning if the contract is unreachable.
    """
    if not PERFORMANCE_BOND_ADDR:
        logger.warning({}, "PERFORMANCE_BOND_ADDRESS not set — returning 0.0")
        return 0.0
    try:
        w3 = get_web3()
        contract = w3.eth.contract(
            address=w3.to_checksum_address(PERFORMANCE_BOND_ADDR),
            abi=_BOND_ABI,
        )
        raw: int = contract.functions.getBondBalance().call()
        return raw / 1_000_000  # USDC has 6 decimal places
    except Exception as exc:
        logger.warning({"error": str(exc)}, "get_bond_balance failed")
        return 0.0


def slash_bond(victim_address: str, payout_amount_usdc: float) -> str:
    """Placeholder — full implementation in Sprint 3.

    Returns a dummy tx hash so the demo can proceed without chain access.
    """
    logger.info({"victim": victim_address, "amount": payout_amount_usdc},
                "slash_bond called — Sprint 3 will execute on-chain")
    return "0x0000000000000000000000000000000000000000000000000000000000000000"
