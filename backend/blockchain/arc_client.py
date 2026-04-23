import json
import os
from pathlib import Path

from dotenv import load_dotenv
from web3 import Web3


BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR.parent.parent / ".env"
ABI_PATH = BASE_DIR / "contract_abi.json"

load_dotenv(ENV_PATH)

ARC_RPC_URL = os.getenv("ARC_RPC_URL")
DEPLOYER_PRIVATE_KEY = os.getenv("DEPLOYER_PRIVATE_KEY")
PERFORMANCE_BOND_ADDRESS = os.getenv("PERFORMANCE_BOND_ADDRESS")

if not ARC_RPC_URL:
    raise ValueError("Missing ARC_RPC_URL in .env")

if not DEPLOYER_PRIVATE_KEY:
    raise ValueError("Missing DEPLOYER_PRIVATE_KEY in .env")

if not PERFORMANCE_BOND_ADDRESS:
    raise ValueError("Missing PERFORMANCE_BOND_ADDRESS in .env")

w3 = Web3(Web3.HTTPProvider(ARC_RPC_URL))

if not w3.is_connected():
    raise ConnectionError("Failed to connect to Arc RPC")

account = w3.eth.account.from_key(DEPLOYER_PRIVATE_KEY)
wallet_address = account.address

with ABI_PATH.open("r", encoding="utf-8") as abi_file:
    contract_abi = json.load(abi_file)

contract = w3.eth.contract(
    address=Web3.to_checksum_address(PERFORMANCE_BOND_ADDRESS),
    abi=contract_abi,
)
