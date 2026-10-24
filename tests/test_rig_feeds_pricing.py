"""Private price math uses decimal amounts and rejects malformed rules."""

import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agents" / "rig"))

from rigbox.pricing import indicative_price, price_rule  # noqa: E402


def test_landed_cost_and_gross_margin_are_converted_once():
    rule = price_rule({"freight": "10", "duty_percent": "15", "margin_percent": "20"})
    assert indicative_price("100", rule, "18.50") == Decimal("2925.31")


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "1e100", "", None])
def test_invalid_cost_never_produces_a_shopper_price(value):
    with pytest.raises(ValueError):
        indicative_price(value, price_rule({}), "18.50")


def test_missing_rate_and_impossible_margin_are_refused():
    with pytest.raises(ValueError):
        indicative_price("10", price_rule({}), "0")
    with pytest.raises(ValueError):
        price_rule({"margin_percent": "100"})
