"""Provider-agnostic Locate payments. Test mode only, no concrete provider.

The payment processor for Locate checkout is not chosen yet. This module is
the interface a provider adapter will implement, and the guard every adapter
must pass before any call: RIG_LOCATE_PAYMENTS_MODE=test, and no key that
looks live. A refusal never echoes the key.

Two adapter shapes pass the same guard:

* PaymentProvider: one-shot capture(token) and refund (the #463 shape).
* PaymentAdapter: pay on Accept. create_intent on Accept, capture, refund,
  and cancel_intent (void an authorization that was not captured), each
  keyed by an idempotency key, plus webhook events verified with an
  HMAC-SHA256 signature (verify_webhook). TestAdapter is the built-in fake
  used by tests. It is never wired into the app, and there is no live mode.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import time
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


@dataclass(frozen=True)
class Intent:
    reference: str
    # "requires_capture" | "failed" | "canceled", or "captured" when a cancel
    # was refused because the intent had already been captured.
    status: str
    amount: Decimal
    currency: str
    test: bool


class PaymentAdapter(Protocol):
    """Pay on Accept. Implemented by a provider adapter once one is chosen.

    Every money-moving call takes an idempotency key. The same key must
    return the same object and move money at most once.
    """

    name: str

    def keys(self) -> list[str]: ...

    def webhook_secret(self) -> str:
        """Shared secret for webhook HMAC verification."""
        ...

    async def create_intent(self, *, amount: Decimal, currency: str, token: str, reference: str,
                            idempotency_key: str, metadata: dict[str, str]) -> Intent: ...

    async def capture_intent(self, *, intent: Intent, idempotency_key: str) -> Charge: ...

    async def cancel_intent(self, *, intent: Intent, idempotency_key: str) -> Intent:
        """Void an authorization. Returns status "canceled", or "captured" when
        the intent was already captured (then nothing is voided)."""
        ...

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


def intents(provider: Any) -> bool:
    """True when the configured adapter supports pay on Accept (intent then capture)."""
    return all(callable(getattr(provider, name, None)) for name in ("create_intent", "capture_intent", "cancel_intent"))


def _proven(value: Any, kind: type) -> Any:
    if not isinstance(value, kind) or value.test is not True:
        # An adapter that cannot prove test mode is treated as live.
        raise PaymentRefused("live_charge_refused")
    return value


async def create_intent(provider: Any, *, amount: Any, currency: str, token: str, reference: str,
                        metadata: dict[str, str], env: dict[str, str] | None = None) -> Intent:
    checked = guard(provider, env)
    intent = await checked.create_intent(amount=Decimal(str(amount)), currency=currency, token=token,
                                         reference=reference, idempotency_key=f"{reference}:intent",
                                         metadata=metadata)
    return _proven(intent, Intent)


async def capture_intent(provider: Any, intent: Intent, *, reference: str,
                         env: dict[str, str] | None = None) -> Charge:
    checked = guard(provider, env)
    charge = await checked.capture_intent(intent=_proven(intent, Intent), idempotency_key=f"{reference}:capture")
    return _proven(charge, Charge)


async def cancel_intent(provider: Any, intent: Intent, *, reference: str,
                        env: dict[str, str] | None = None) -> Intent:
    """Void an uncaptured authorization, keyed by the quote reference."""
    checked = guard(provider, env)
    voided = await checked.cancel_intent(intent=_proven(intent, Intent), idempotency_key=f"{reference}:cancel")
    return _proven(voided, Intent)


# Webhooks. Header: "t=<unix seconds>,v1=<hex hmac-sha256 of '<t>.<raw body>'>".
SIGNATURE_HEADER = "x-rig-payment-signature"
WEBHOOK_TOLERANCE = 300
WEBHOOK_MAX_BYTES = 65536
_EVENT_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def sign(secret: str, body: bytes, timestamp: int) -> str:
    digest = hmac.new(secret.encode(), str(timestamp).encode() + b"." + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def verify_webhook(provider: Any, body: bytes, header: str, *, now: float | None = None,
                   tolerance: int = WEBHOOK_TOLERANCE, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Verify a provider webhook and return the event. Fixed refusal codes only.

    Behind the same guard as payments: test mode, no live-looking secret.
    Constant-time compare, timestamp tolerance against replays, size cap.
    """
    checked = guard(provider, env)
    secret = str(checked.webhook_secret() or "")
    if not secret or live_key(secret):
        raise PaymentRefused("webhook_not_configured")
    if not isinstance(body, bytes | bytearray) or len(body) > WEBHOOK_MAX_BYTES:
        raise PaymentRefused("webhook_signature")
    parts: dict[str, list[str]] = {}
    for item in str(header or "").split(","):
        key, _, value = item.strip().partition("=")
        parts.setdefault(key, []).append(value)
    try:
        timestamp = int(parts.get("t", [""])[0])
    except ValueError:
        raise PaymentRefused("webhook_signature") from None
    if abs((time.time() if now is None else now) - timestamp) > tolerance:
        raise PaymentRefused("webhook_stale")
    expected = sign(secret, bytes(body), timestamp).split("v1=", 1)[1]
    if not any(hmac.compare_digest(expected, given) for given in parts.get("v1", []) if given):
        raise PaymentRefused("webhook_signature")
    try:
        event = json.loads(bytes(body))
    except ValueError:
        raise PaymentRefused("webhook_payload") from None
    if not isinstance(event, dict) or not _EVENT_ID.match(str(event.get("id") or "")) \
            or not isinstance(event.get("type"), str) or not isinstance(event.get("data"), dict):
        raise PaymentRefused("webhook_payload")
    return event


class TestAdapter:
    """Built-in fake PaymentAdapter for tests. Deterministic, never moves money.

    token "tok_decline" declines the intent, "tok_capture_fails" fails capture,
    "tok_capture_lost" captures but loses the response (raises ConnectionError).
    Same idempotency key -> same object, and each intent is captured, canceled
    and each charge refunded at most once (counted in .calls). A canceled
    intent cannot be captured; a captured one cannot be canceled.
    """

    __test__ = False  # not a pytest class
    name = "test-adapter"

    def __init__(self, secret: str | None = None) -> None:
        self._secret = secret or "whsec_test_" + secrets.token_hex(16)
        self.intents: dict[str, Intent] = {}
        self.charges: dict[str, Charge] = {}
        self.refunds: dict[str, Charge] = {}
        self.canceled: dict[str, Intent] = {}
        self.tokens: dict[str, str] = {}
        self.calls: list[tuple[str, str]] = []

    def keys(self) -> list[str]:
        return ["sk_test_adapter", self._secret]

    def webhook_secret(self) -> str:
        return self._secret

    async def create_intent(self, *, amount: Decimal, currency: str, token: str, reference: str,
                            idempotency_key: str, metadata: dict[str, str]) -> Intent:
        if idempotency_key not in self.intents:
            self.calls.append(("create_intent", idempotency_key))
            status = "failed" if token == "tok_decline" else "requires_capture"
            self.intents[idempotency_key] = Intent(f"pi_test_{hashlib.sha256(idempotency_key.encode()).hexdigest()[:16]}",
                                                   status, Decimal(amount), currency, True)
            self.tokens[self.intents[idempotency_key].reference] = token
        return self.intents[idempotency_key]

    async def capture_intent(self, *, intent: Intent, idempotency_key: str) -> Charge:
        if idempotency_key not in self.charges:
            self.calls.append(("capture", idempotency_key))
            voided = any(item.reference == intent.reference and item.status == "canceled"
                         for item in self.canceled.values())
            ok = intent.status == "requires_capture" and not voided \
                and self.tokens.get(intent.reference) != "tok_capture_fails"
            self.charges[idempotency_key] = Charge(intent.reference.replace("pi_", "ch_", 1),
                                                   "captured" if ok else "failed", intent.amount, intent.currency, True)
            if self.tokens.get(intent.reference) == "tok_capture_lost":
                raise ConnectionError("capture response lost")
        return self.charges[idempotency_key]

    async def cancel_intent(self, *, intent: Intent, idempotency_key: str) -> Intent:
        if idempotency_key not in self.canceled:
            self.calls.append(("cancel_intent", idempotency_key))
            charge = intent.reference.replace("pi_", "ch_", 1)
            captured = any(item.reference == charge and item.status == "captured" for item in self.charges.values())
            self.canceled[idempotency_key] = Intent(intent.reference, "captured" if captured else "canceled",
                                                    intent.amount, intent.currency, True)
        return self.canceled[idempotency_key]

    async def refund(self, *, charge: Charge, reason: str) -> Charge:
        if charge.reference not in self.refunds:
            self.calls.append(("refund", charge.reference))
            self.refunds[charge.reference] = Charge(charge.reference, "refunded", charge.amount, charge.currency, True)
        return self.refunds[charge.reference]

    def event(self, event_id: str, kind: str, reference: str, *, timestamp: int | None = None) -> tuple[bytes, str]:
        """A signed webhook delivery, as the provider would send it."""
        body = json.dumps({"id": event_id, "type": kind, "data": {"reference": reference}},
                          separators=(",", ":")).encode()
        return body, sign(self._secret, body, int(time.time()) if timestamp is None else timestamp)
