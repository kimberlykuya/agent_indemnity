"""
tests/test_sprint2_core.py
---------------------------
TDD tests for Sprint 2 core modules:
  - route_categories.py
  - price_table.py
  - model_map.py
  - anomaly_policy.py

10 test prompts spanning all four route categories, with at least two
anomaly-triggering prompts verified against the rule engine.

Run:
    pytest backend/tests/test_sprint2_core.py -v

Note: async tests require pytest-asyncio; sync tests use asyncio.run().
"""
import asyncio
import sys
from pathlib import Path

import pytest

# Make backend/ importable when pytest is run from the repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.anomaly_policy import AnomalyResult, AnomalyType, check_anomaly
from agent.model_map import InferenceProvider, get_model
from agent.price_table import get_price
from agent.route_categories import RouteCategory


# ===========================================================================
# Shared fixtures
# ===========================================================================

@pytest.fixture(
    params=[
        RouteCategory.GENERAL,
        RouteCategory.LEGAL,
        RouteCategory.TECHNICAL,
        RouteCategory.FALLBACK,
    ]
)
def every_category(request):
    return request.param


# ===========================================================================
# price_table tests
# ===========================================================================

class TestPriceTable:
    def test_all_categories_have_prices(self, every_category):
        """Every RouteCategory must resolve to a price without error."""
        entry = get_price(every_category)
        assert entry.usdc > 0

    def test_prices_are_sub_cent(self, every_category):
        """All prices must be ≤ $0.01 (hackathon acceptance criterion)."""
        entry = get_price(every_category)
        assert entry.usdc <= 0.01, (
            f"{every_category} price ${entry.usdc} exceeds the $0.01 cap"
        )

    def test_micro_units_consistent(self, every_category):
        """usdc_micro must equal usdc * 1_000_000 (6 decimal-place USDC)."""
        entry = get_price(every_category)
        expected_micro = round(entry.usdc * 1_000_000)
        assert entry.usdc_micro == expected_micro, (
            f"{every_category}: micro {entry.usdc_micro} ≠ {expected_micro}"
        )

    def test_legal_more_expensive_than_general(self):
        assert get_price(RouteCategory.LEGAL).usdc > get_price(RouteCategory.GENERAL).usdc

    def test_fallback_most_expensive(self):
        fallback = get_price(RouteCategory.FALLBACK).usdc
        for cat in [RouteCategory.GENERAL, RouteCategory.LEGAL, RouteCategory.TECHNICAL]:
            assert fallback >= get_price(cat).usdc


# ===========================================================================
# model_map tests
# ===========================================================================

class TestModelMap:
    def test_all_categories_have_models(self, every_category):
        """Every RouteCategory must map to a ModelSpec."""
        spec = get_model(every_category)
        assert spec.model_id

    def test_fallback_is_gemini(self):
        spec = get_model(RouteCategory.FALLBACK)
        assert spec.provider == InferenceProvider.GEMINI

    def test_specialist_tiers_are_featherless(self):
        for cat in [RouteCategory.GENERAL, RouteCategory.LEGAL, RouteCategory.TECHNICAL]:
            spec = get_model(cat)
            assert spec.provider == InferenceProvider.FEATHERLESS, (
                f"{cat} should use Featherless, got {spec.provider}"
            )

    def test_featherless_specs_have_api_base(self):
        for cat in [RouteCategory.GENERAL, RouteCategory.LEGAL, RouteCategory.TECHNICAL]:
            spec = get_model(cat)
            assert spec.api_base is not None and "featherless" in spec.api_base

    def test_gemini_fallback_has_no_api_base(self):
        spec = get_model(RouteCategory.FALLBACK)
        assert spec.api_base is None


# ===========================================================================
# route_categories tests
# ===========================================================================

class TestRouteCategories:
    def test_risk_levels_defined(self, every_category):
        assert every_category.risk_level in ("low", "medium", "high")

    def test_legal_and_fallback_high_risk(self):
        assert RouteCategory.LEGAL.risk_level == "high"
        assert RouteCategory.FALLBACK.risk_level == "high"

    def test_general_is_low_risk(self):
        assert RouteCategory.GENERAL.risk_level == "low"


# ===========================================================================
# anomaly_policy — 10 test prompts (data-driven)
# ===========================================================================

from tests.prompts.anomaly_prompts import PROMPTS


@pytest.mark.parametrize("prompt", PROMPTS, ids=[p["id"] for p in PROMPTS])
def test_prompt(prompt):
    result = asyncio.run(check_anomaly(
        user_message=prompt["user_message"],
        agent_reply=prompt["agent_reply"],
        category=prompt["category"],
        gemini_client=None,
    ))

    assert result.flagged == prompt["expect_flagged"], (
        f"[{prompt['id']}] flagged={result.flagged}, expected={prompt['expect_flagged']}"
    )

    expected = prompt["expect_type"]
    if isinstance(expected, tuple):
        assert result.anomaly_type in expected, (
            f"[{prompt['id']}] anomaly_type={result.anomaly_type}, expected one of {expected}"
        )
    else:
        assert result.anomaly_type == expected, (
            f"[{prompt['id']}] anomaly_type={result.anomaly_type}, expected={expected}"
        )

    if prompt["expect_slash"] is not None:
        assert result.slash_recommended == prompt["expect_slash"], (
            f"[{prompt['id']}] slash_recommended={result.slash_recommended}"
        )


# ---------------------------------------------------------------------------
# AnomalyResult.clean() factory
# ---------------------------------------------------------------------------

def test_anomaly_result_clean_factory():
    r = AnomalyResult.clean()
    assert not r.flagged
    assert r.anomaly_type == AnomalyType.NONE
    assert r.confidence == 0.0
    assert not r.slash_recommended

