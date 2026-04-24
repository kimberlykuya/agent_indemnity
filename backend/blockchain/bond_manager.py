import logging
import time
import re

from blockchain.arc_client import PERFORMANCE_BOND_ADDR, USDC_CONTRACT_ADDR, get_web3

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

_ERC20_ABI = [
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
]

_MAX_UINT256 = (1 << 256) - 1
_TXPOOL_FULL_RETRY_ATTEMPTS = 4
_TXPOOL_FULL_BACKOFF_SECONDS = 2.0
_TX_HASH_RE = re.compile(r"^0x[a-fA-F0-9]{64}$")


def _get_contract(w3):
    return w3.eth.contract(
        address=w3.to_checksum_address(PERFORMANCE_BOND_ADDR),
        abi=_BOND_ABI,
    )


def _get_usdc_contract(w3):
    if not USDC_CONTRACT_ADDR:
        raise ValueError("USDC_CONTRACT_ADDRESS not set")
    return w3.eth.contract(
        address=w3.to_checksum_address(USDC_CONTRACT_ADDR),
        abi=_ERC20_ABI,
    )


def _is_txpool_full_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "txpool is full" in message


def _send_contract_transaction(w3, account, private_key: str, tx) -> str:
    signed_tx = w3.eth.account.sign_transaction(tx, private_key=private_key)

    for attempt in range(1, _TXPOOL_FULL_RETRY_ATTEMPTS + 1):
        try:
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            hex_hash = tx_hash.hex()
            if not hex_hash.startswith("0x"):
                hex_hash = f"0x{hex_hash}"
            receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)
            if receipt.status != 1:
                raise RuntimeError("On-chain transaction reverted")
            return hex_hash
        except Exception as exc:
            if not _is_txpool_full_error(exc) or attempt == _TXPOOL_FULL_RETRY_ATTEMPTS:
                raise
            backoff = _TXPOOL_FULL_BACKOFF_SECONDS * attempt
            logger.warning(
                "Arc txpool full; retrying transaction submission in %.1fs (attempt %d/%d)",
                backoff,
                attempt,
                _TXPOOL_FULL_RETRY_ATTEMPTS,
            )
            time.sleep(backoff)

    raise RuntimeError("Unable to submit on-chain transaction")


def _ensure_usdc_allowance(w3, owner_address: str, amount_raw: int, private_key: str) -> str | None:
    usdc = _get_usdc_contract(w3)
    spender = w3.to_checksum_address(PERFORMANCE_BOND_ADDR)
    owner = w3.to_checksum_address(owner_address)
    current_allowance = int(usdc.functions.allowance(owner, spender).call())
    if current_allowance >= amount_raw:
        return None

    approve_tx = usdc.functions.approve(spender, _MAX_UINT256).build_transaction(
        {
            "from": owner,
            "nonce": w3.eth.get_transaction_count(owner, "pending"),
        }
    )
    approve_hash = _send_contract_transaction(w3, w3.eth.account.from_key(private_key), private_key, approve_tx)
    logger.info(
        "Approved USDC allowance for PerformanceBond: owner=%s spender=%s tx_hash=%s",
        owner,
        spender,
        approve_hash,
    )
    return approve_hash


def _read_onchain_bond_balance() -> float:
    if not PERFORMANCE_BOND_ADDR:
        raise ValueError("PERFORMANCE_BOND_ADDRESS not set")

    w3 = get_web3()
    contract = _get_contract(w3)
    raw: int = contract.functions.getBondBalance().call()
    return raw / 1_000_000


def get_bond_balance() -> float:
    """Return the on-chain bond balance in USDC."""
    return _read_onchain_bond_balance()


def is_verifier_safe_tx_hash(value: str | None) -> bool:
    return bool(value and _TX_HASH_RE.fullmatch(value.strip()))


def verify_topup_tx(
    tx_hash: str,
    *,
    expected_min_amount_usdc: float,
    allowed_sender_addresses: list[str] | tuple[str, ...] | None = None,
) -> str:
    """Verify that a confirmed Arc transaction is a topUpBond() call with enough value."""
    if not PERFORMANCE_BOND_ADDR:
        raise ValueError("PERFORMANCE_BOND_ADDRESS not set")
    if expected_min_amount_usdc <= 0:
        raise ValueError("expected_min_amount_usdc must be greater than zero")
    if not is_verifier_safe_tx_hash(tx_hash):
        raise ValueError("Invalid Arc transaction hash")

    w3 = get_web3()
    contract = _get_contract(w3)
    normalized_tx_hash = tx_hash.strip()
    tx = w3.eth.get_transaction(normalized_tx_hash)
    receipt = w3.eth.get_transaction_receipt(normalized_tx_hash)

    if receipt.status != 1:
        raise ValueError("Arc transaction has not confirmed successfully")

    tx_to = tx.get("to")
    if not tx_to or w3.to_checksum_address(tx_to) != w3.to_checksum_address(PERFORMANCE_BOND_ADDR):
        raise ValueError("Arc transaction does not target the performance bond contract")

    decoded_function, arguments = contract.decode_function_input(tx.get("input", "0x"))
    if decoded_function.fn_name != "topUpBond":
        raise ValueError("Arc transaction is not a topUpBond() call")

    amount_raw = int(arguments.get("amount", 0))
    expected_min_raw = int(expected_min_amount_usdc * 1_000_000)
    if amount_raw < expected_min_raw:
        raise ValueError("Arc topUpBond() amount is below the required premium")

    if allowed_sender_addresses:
        allowed = {w3.to_checksum_address(address) for address in allowed_sender_addresses if address}
        sender = w3.to_checksum_address(tx["from"])
        if allowed and sender not in allowed:
            raise ValueError("Arc topUpBond() sender is not authorized for this request")

    return normalized_tx_hash


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
    _ensure_usdc_allowance(w3, account.address, amount_raw, DEPLOYER_PRIVATE_KEY)

    tx = contract.functions.topUpBond(amount_raw).build_transaction(
        {
            "from": account.address,
            "nonce": w3.eth.get_transaction_count(account.address, "pending"),
        }
    )
    hex_hash = _send_contract_transaction(w3, account, DEPLOYER_PRIVATE_KEY, tx)
    logger.info("pay_premium executed on-chain: amount=%s tx_hash=%s", amount_usdc, hex_hash)
    return hex_hash


def slash_bond(victim_address: str, payout_amount_usdc: float) -> str:
    """Executes the on-chain slashBond transaction on the Arc network."""
    from blockchain.arc_client import DEPLOYER_PRIVATE_KEY
    if not PERFORMANCE_BOND_ADDR or not DEPLOYER_PRIVATE_KEY:
        raise ValueError("Missing PERFORMANCE_BOND_ADDRESS or DEPLOYER_PRIVATE_KEY")
    
    w3 = get_web3()
    contract = _get_contract(w3)
    
    account = w3.eth.account.from_key(DEPLOYER_PRIVATE_KEY)
    amount_raw = int(payout_amount_usdc * 1_000_000)
    
    tx = contract.functions.slashBond(
        w3.to_checksum_address(victim_address), 
        amount_raw
    ).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address, "pending"),
    })
    
    hex_hash = _send_contract_transaction(w3, account, DEPLOYER_PRIVATE_KEY, tx)
    logger.info(
        "slash_bond executed on-chain: victim=%s amount=%s tx_hash=%s",
        victim_address,
        payout_amount_usdc,
        hex_hash,
    )
    return hex_hash
