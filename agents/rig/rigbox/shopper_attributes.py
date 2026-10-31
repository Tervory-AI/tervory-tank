"""Which product attributes a shopper may see.

Catalogue rows carry free-form ``attributes`` JSON. Stores and importers put
private pricing inputs there too (Custom Nation's POF USA rows carry
``export_usd``, the supplier's export price). ``rigbox.logic.public_product``
passes attributes through unchanged, and it is byte-mirrored into approved,
immutable Skala packages, so the guard lives here instead and runs at the
shopper boundary (``quotes.privacy.shopper_body``) and before shopper-facing
model prompts (``Service.ask``).

Allowlist, not denylist: a key a store invents tomorrow stays private until
it is added here on purpose. Values of allowed keys are still filtered
recursively by the private-key pattern in ``quotes.privacy``.
"""

from __future__ import annotations

from typing import Any

# Display copy and presentation flags the widget, /rig pages and cn.py read.
_DISPLAY = {
    "summary", "detail", "tagline", "match_note", "photo_note", "demo_note",
    "sample", "demo_item", "group", "kind", "relation", "upgrade_for",
    "features", "in_box", "included", "options", "defaults", "verified",
    "price_label", "price_history", "stock",
}
# Measurable facts that decide fit (docs/rig/catalogue-feed.md: thread, rail,
# tube size, length, bolt pattern...). Shown to shoppers by design.
_FIT_FACTS = {
    "thread", "rail", "mount", "footprint", "optic_cut", "fits_cuts", "fits_products",
    "tube_mm", "tube_size", "barrel_mm", "barrel_in", "length", "length_mm", "length_in",
    "bolt_pattern", "base", "body", "rounds", "capacity",
    "size", "weight", "weight_g", "material", "finish", "color", "colour",
}
SHOPPER_ATTRIBUTES = frozenset(_DISPLAY | _FIT_FACTS)


def shopper_attributes(attributes: Any) -> dict[str, Any]:
    """Keep only allowlisted top-level attribute keys. Never raises."""
    if not isinstance(attributes, dict):
        return {}
    return {key: value for key, value in attributes.items() if str(key) in SHOPPER_ATTRIBUTES}
