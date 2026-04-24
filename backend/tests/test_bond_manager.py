from __future__ import annotations

from types import SimpleNamespace

from backend.blockchain import bond_manager


class _FakeApproveBuilder:
    def __init__(self) -> None:
        self.last_tx = None

    def build_transaction(self, tx):
        self.last_tx = tx
        return tx


class _FakeUsdcFunctions:
    def __init__(self, allowance_value: int, approve_builder: _FakeApproveBuilder) -> None:
        self._allowance_value = allowance_value
        self._approve_builder = approve_builder

    def allowance(self, owner, spender):
        return SimpleNamespace(call=lambda: self._allowance_value)

    def approve(self, spender, amount):
        return self._approve_builder


class _FakeUsdcContract:
    def __init__(self, allowance_value: int, approve_builder: _FakeApproveBuilder) -> None:
        self.functions = _FakeUsdcFunctions(allowance_value, approve_builder)


class _FakeWeb3:
    def __init__(self) -> None:
        self.eth = SimpleNamespace(
            get_transaction_count=lambda address, mode=None: 7,
            account=SimpleNamespace(from_key=lambda key: SimpleNamespace(address="0xowner")),
        )

    def to_checksum_address(self, value: str) -> str:
        return value


def test_ensure_usdc_allowance_skips_approve_when_allowance_is_sufficient(monkeypatch):
    w3 = _FakeWeb3()
    approve_builder = _FakeApproveBuilder()
    monkeypatch.setattr(
        bond_manager,
        "_get_usdc_contract",
        lambda _w3: _FakeUsdcContract(allowance_value=2_000, approve_builder=approve_builder),
    )

    sent = []
    monkeypatch.setattr(bond_manager, "_send_contract_transaction", lambda *args: sent.append(args) or "0xapprove")

    result = bond_manager._ensure_usdc_allowance(w3, "0xowner", 1_000, "secret")

    assert result is None
    assert sent == []


def test_ensure_usdc_allowance_approves_max_when_allowance_is_too_low(monkeypatch):
    w3 = _FakeWeb3()
    approve_builder = _FakeApproveBuilder()
    monkeypatch.setattr(
        bond_manager,
        "_get_usdc_contract",
        lambda _w3: _FakeUsdcContract(allowance_value=500, approve_builder=approve_builder),
    )

    sent = []
    monkeypatch.setattr(
        bond_manager,
        "_send_contract_transaction",
        lambda *args: sent.append(args) or "0xapprove",
    )

    result = bond_manager._ensure_usdc_allowance(w3, "0xowner", 1_000, "secret")

    assert result == "0xapprove"
    assert approve_builder.last_tx == {"from": "0xowner", "nonce": 7}
    assert len(sent) == 1
