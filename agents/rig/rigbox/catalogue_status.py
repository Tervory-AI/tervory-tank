"""What is set up in one store's Rig room, as counts for the Workspace overview.

Every number comes from the room's own rows. Nothing private leaves: no feed address,
no quote email or webhook, no price inputs, only counts and yes/no facts.
"""
from __future__ import annotations

from typing import Any

from rigbox.logic import approved


def catalogue_status(products: list[dict[str, Any]], fits: list[dict[str, Any]],
                     feeds: list[dict[str, Any]], retailer: dict[str, Any] | None) -> dict[str, Any]:
    kept = [row for row in fits if str(row.get("source") or "") != "rejected"]
    live = [row for row in kept if approved(row)]
    waiting = [row for row in kept if not approved(row)]
    return {
        # "products" counts every catalogue row, "active" only the rows shoppers can find.
        "products": len(products),
        "active": sum(1 for row in products if row.get("active", True)),
        # "fits" stays the total the Workspace has always shown; "approved_fits" reach shoppers.
        "fits": len(fits),
        "approved_fits": len(live),
        "waiting_fits": len(waiting),
        "feeds": len(feeds),
        "delivery": bool(retailer and (retailer.get("email") or retailer.get("webhook"))),
    }
