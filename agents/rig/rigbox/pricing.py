"""Private landed-cost calculations. Only the final ZAR amount is public."""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def number(value, *, maximum="1000000000") -> Decimal:
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > Decimal(maximum):
            raise ValueError()
        return result
    except (ValueError, InvalidOperation, TypeError):
        raise ValueError("Enter a finite, non-negative amount within the allowed range.") from None


def price_rule(values: dict) -> dict[str, str]:
    """Freight is per item in supplier currency. Margin is a gross margin %."""
    freight = number(values.get("freight", 0))
    duty = number(values.get("duty_percent", 0), maximum="1000")
    margin = number(values.get("margin_percent", 0), maximum="99.99")
    return {"freight": str(freight), "duty_percent": str(duty), "margin_percent": str(margin)}


def indicative_price(cost, rule: dict, rate) -> Decimal:
    validated = price_rule(rule)
    fx = number(rate, maximum="1000000")
    if not fx:
        raise ValueError("A founder-set exchange rate is required.")
    landed = (number(cost) + Decimal(validated["freight"])) * (1 + Decimal(validated["duty_percent"]) / 100)
    amount = landed * fx / (1 - Decimal(validated["margin_percent"]) / 100)
    return number(amount, maximum="1000000000000").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
