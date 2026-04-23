from .arc_client import account, contract, wallet_address, w3


def stake_bond(amount_usdc: float) -> str:
    amount_6dp = int(amount_usdc * 10**6)

    nonce = w3.eth.get_transaction_count(wallet_address)
    gas_price = w3.eth.gas_price

    tx = contract.functions.stakeBond(amount_6dp).build_transaction(
        {
            "from": wallet_address,
            "nonce": nonce,
            "gas": 200000,
            "gasPrice": gas_price,
        }
    )

    signed_tx = w3.eth.account.sign_transaction(tx, private_key=account.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    return receipt.transactionHash.hex()


def get_bond_balance() -> float:
    raw_balance = contract.functions.getBondBalance().call()
    return raw_balance / 10**6


if __name__ == "__main__":
    print("Current bond balance:", get_bond_balance())
