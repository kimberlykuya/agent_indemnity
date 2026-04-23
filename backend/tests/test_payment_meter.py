"""tests/test_payment_meter.py — unit tests for agent/payment_meter.py"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from agent import config
from agent.payment_meter import UnknownRouteError, create_payment_record, get_price


class TestGetPrice:
    def test_every_route_has_price(self):
        for route in config.ALL_ROUTES:
            assert get_price(route) > 0

    def test_prices_match_policy(self):
        assert get_price(config.GENERAL)          == 0.001
        assert get_price(config.TECHNICAL)        == 0.003
        assert get_price(config.LEGAL_RISK)       == 0.005
        assert get_price(config.FALLBACK_COMPLEX) == 0.010

    def test_all_prices_sub_cent(self):
        for route in config.ALL_ROUTES:
            assert get_price(route) <= 0.01

    def test_unknown_route_raises(self):
        with pytest.raises(UnknownRouteError):
            get_price("nonexistent_route")

    def test_legal_risk_more_than_general(self):
        assert get_price(config.LEGAL_RISK) > get_price(config.GENERAL)

    def test_fallback_most_expensive(self):
        fallback_price = get_price(config.FALLBACK_COMPLEX)
        for route in config.ALL_ROUTES:
            assert fallback_price >= get_price(route)


class TestCreatePaymentRecord:
    def test_record_shape(self):
        rec = create_payment_record("user-1", config.GENERAL, 0.001)
        assert rec["payment_status"] == "priced"
        assert rec["price_usdc"]     == 0.001
        assert rec["currency"]       == "USDC"
        assert rec["route_category"] == config.GENERAL
        assert rec["buyer_id"]       == "user-1"

    def test_record_is_json_serializable(self):
        import json
        rec = create_payment_record("u", config.TECHNICAL, 0.003)
        assert json.dumps(rec)  # no exception
