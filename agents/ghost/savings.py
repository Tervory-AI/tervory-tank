"""Model-spend evidence. Enforce stays offline; only Watch asks Tank for prices."""
from __future__ import annotations

import math
from typing import Any
from uuid import UUID


def code_cost(receipt: dict[str, Any]) -> dict[str, Any]:
    # These are model costs, not hosting or third-party control-plane charges.
    receipt.setdefault("cost_usd", 0)
    receipt.setdefault("would_have_cost_usd", None)
    receipt.setdefault("cost_basis", "code")
    receipt.setdefault("baseline_status", "unpriced")
    return receipt


def reference(receipt: dict[str, Any]) -> dict[str, Any]:
    # Never send log lines, email addresses, tokens, provider bodies or secrets.
    return {key: receipt[key] for key in
            ("kind", "action", "outcome", "step", "signal", "severity", "applied")
            if isinstance(receipt.get(key), (str, bool))}


async def price_receipt(tank, receipt: dict[str, Any], tenant: str) -> dict[str, Any]:
    tenant = str(UUID(tenant))
    if receipt.get("tenant_id", tenant) != tenant:
        raise ValueError("Receipt belongs to another tenant.")
    receipt["tenant_id"] = tenant
    code_cost(receipt)
    if receipt.get("baseline_status") == "priced" or not receipt.get("id"):
        return receipt
    try:
        result = await tank.call("POST", "/v1/ghost/autumbra/savings", {
            "tenant_id": tenant, "receipt_id": str(receipt["id"]), "reference": reference(receipt),
        })
        if result.get("tenant_id") != tenant or result.get("receipt_id") != str(receipt["id"]):
            raise ValueError("Receipt identity mismatch")
        amount = result.get("would_have_cost_usd")
        if amount is not None and (isinstance(amount, bool) or not isinstance(amount, (int, float))
                                   or not math.isfinite(amount) or amount < 0):
            raise ValueError("Invalid price")
        for key in ("would_have_cost_usd", "baseline_model", "baseline_status", "reference_tokens_in",
                    "reference_tokens_out", "baseline_basis", "ledger_id"):
            if key in result:
                receipt[key] = result[key]
    except (RuntimeError, ValueError, TypeError, KeyError):
        # The safety action already has a durable local receipt. Pricing cannot
        # replay it or turn a successful block into a failed action.
        receipt["baseline_status"] = "unavailable"
    return receipt
