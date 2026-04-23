"""
blockchain/arc_client.py
-------------------------
Arc EVM connection helper. Import-ready for Sprint 3 bond interactions.

Sprint 2: minimal — just exposes connection config and an optional
balance-fetch helper so Sprint 1 proof remains accessible.
"""

import os
import logging

logger = logging.getLogger(__name__)

ARC_RPC_URL            = os.getenv("ARC_RPC_URL",            "https://rpc.arc.network")
ARC_CHAIN_ID           = int(os.getenv("ARC_CHAIN_ID", "5042002"))
PERFORMANCE_BOND_ADDR  = os.getenv("PERFORMANCE_BOND_ADDRESS", "")
USDC_CONTRACT_ADDR     = os.getenv("USDC_CONTRACT_ADDRESS",    "")


def get_web3():
    """Return a connected Web3 instance. Lazy import to avoid startup cost."""
    from web3 import Web3
    w3 = Web3(Web3.HTTPProvider(ARC_RPC_URL))
    if not w3.is_connected():
        logger.warning({"rpc": ARC_RPC_URL}, "Arc RPC not reachable")
    return w3
