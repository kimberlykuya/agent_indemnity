import json
import os
from pathlib import Path

from dotenv import load_dotenv
from solcx import compile_standard, install_solc
from web3 import Web3


load_dotenv()

ARC_RPC_URL = os.environ["ARC_RPC_URL"]
CHAIN_ID = int(os.environ["ARC_CHAIN_ID"])
PRIVATE_KEY = os.environ["DEPLOYER_PRIVATE_KEY"]
AGENT_WALLET_ADDRESS = os.environ["AGENT_WALLET_ADDRESS"]
USDC_CONTRACT_ADDRESS = os.environ["USDC_CONTRACT_ADDRESS"]


CONTRACT_PATH = (
    Path(__file__).resolve().parent.parent / "contracts" / "PerformanceBond.sol"
)


def main() -> None:
    w3 = Web3(Web3.HTTPProvider(ARC_RPC_URL))
    if not w3.is_connected():
        raise RuntimeError("Failed to connect to Arc RPC")

    account = w3.eth.account.from_key(PRIVATE_KEY)
    deployer_address = account.address

    print(f"Connected: {w3.is_connected()}")
    print(f"Deployer: {deployer_address}")

    source = CONTRACT_PATH.read_text(encoding="utf-8")

    install_solc("0.8.19")

    compiled = compile_standard(
        {
            "language": "Solidity",
            "sources": {"PerformanceBond.sol": {"content": source}},
            "settings": {"outputSelection": {"*": {"*": ["abi", "evm.bytecode"]}}},
        },
        solc_version="0.8.19",
    )

    contract_data = compiled["contracts"]["PerformanceBond.sol"]["PerformanceBond"]
    abi = contract_data["abi"]
    bytecode = contract_data["evm"]["bytecode"]["object"]

    abi_out = Path(__file__).resolve().parent / "contract_abi.json"
    abi_out.write_text(json.dumps(abi, indent=2), encoding="utf-8")
    print(f"ABI saved to: {abi_out}")

    contract = w3.eth.contract(abi=abi, bytecode=bytecode)

    nonce = w3.eth.get_transaction_count(deployer_address)
    gas_price = w3.eth.gas_price

    tx = contract.constructor(
        Web3.to_checksum_address(USDC_CONTRACT_ADDRESS),
        Web3.to_checksum_address(AGENT_WALLET_ADDRESS),
    ).build_transaction(
        {
            "from": deployer_address,
            "chainId": CHAIN_ID,
            "nonce": nonce,
            "gas": 2_500_000,
            "gasPrice": gas_price,
        }
    )

    signed_tx = w3.eth.account.sign_transaction(tx, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    print(f"Deployment tx hash: {tx_hash.hex()}")

    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    print(f"Contract deployed at: {receipt.contractAddress}")  # type: ignore

    env_line = f"PERFORMANCE_BOND_ADDRESS={receipt.contractAddress}"  # type: ignore
    print(env_line)


if __name__ == "__main__":
    main()
