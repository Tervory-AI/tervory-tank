"""Provider-agnostic Locate payments. Test mode only, no concrete provider.

The payment processor for Locate checkout is not chosen yet. This module is
the interface a provider adapter will implement, and the guard every adapter
must pass before any call: RIG_LOCATE_PAYMENTS_MODE=test, and no key that
looks live. A refusal never echoes the key.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

MODE_ENV = "RIG_LOCATE_PAYMENTS_MODE"
# Live key shapes for the providers under consideration and common processors.
# Stripe: sk_live_, pk_live_, rk_live_, whsec_ is not a mode marker.
# Paystack: sk_live_, pk_live_. Any *_live_* shape is refused.
_LIVE = re.compile(r"(?:^|[_-])live(?:[_-]|$)|^(?:sk|pk|rk)_live", re.I)


class PaymentRefused(Exception):
    """Fixed code only. Never includes a key, card data or a provider response."""


@dataclass(frozen=True)
class Charge:
    reference: str
    status: str  # "captured" | "failed" | "refunded"
    amount: Decimal
    currency: str
    test: bool


class PaymentProvider(Protocol):
    """Implemented by a provider adapter once one is chosen."""

    name: str

    def keys(self) -> list[str]:
        """Every credential the adapter will use, for the live-key guard."""
        ...

    async def capture(self, *, amount: Decimal, currency: str, token: str, reference: str,
                      metadata: dict[str, str]) -> Charge: ...

    async def refund(self, *, charge: Charge, reason: str) -> Charge: ...


def live_key(value: str) -> bool:
    return bool(value) and bool(_LIVE.search(value.strip()))


def guard(provider: PaymentProvider | None, env: dict[str, str] | None = None) -> PaymentProvider:
    """Refuse unless test mode is explicit and no credential looks live."""
    env = os.environ if env is None else env
    if env.get(MODE_ENV, "") != "test":
        raise PaymentRefused("payments_mode")
    if provider is None:
        raise PaymentRefused("payments_not_configured")
    keys = [key for key in provider.keys() if key]
    if any(live_key(key) for key in keys):
        raise PaymentRefused("live_key_refused")
    # The provider's own environment keys are checked too, whatever it reports.
    for name, value in env.items():
        if re.search(r"(STRIPE|PAYSTACK|PAYMENT)", name) and re.search(r"(KEY|SECRET)", name) and live_key(value):
            raise PaymentRefused("live_key_refused")
    return provider


async def capture(provider: PaymentProvider | None, *, amount: Any, currency: str, token: str,
                  reference: str, metadata: dict[str, str], env: dict[str, str] | None = None) -> Charge:
    checked = guard(provider, env)
    charge = await checked.capture(amount=Decimal(str(amount)), currency=currency, token=token,
                                   reference=reference, metadata=metadata)
    if not isinstance(charge, Charge) or charge.test is not True:
        # A provider that cannot prove test mode is treated as live.
        raise PaymentRefused("live_charge_refused")
    return charge


async def refund(provider: PaymentProvider | None, charge: Charge, reason: str,
                 env: dict[str, str] | None = None) -> Charge:
    return await guard(provider, env).refund(charge=charge, reason=reason)
