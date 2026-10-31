"""Which product attributes a shopper may see, and which stay private.

Catalogue rows carry free-form ``attributes`` JSON. Stores and importers put
private pricing inputs there too (Custom Nation's POF USA rows carry
``export_usd``, the supplier's export price). Two layers keep them private:

1. Import. ``split_private`` moves every key that matches ``private_key`` out
   of ``attributes``; the store keeps it in ``agent_rig.product_private_attributes``,
   which no shopper query reads. ``schema.sql`` moves keys already stored.
2. Boundary and search. ``shopper_attributes`` is an allowlist applied to
   shopper responses (``quotes.privacy.shopper_body``), shopper-facing model
   prompts (``Service.ask``) and every search index (``rank``, ``cn``,
   ``Service`` rows, the Postgres search text in ``store``).

``rigbox.logic`` is byte-mirrored into approved, immutable Skala packages, so
it is not changed; its callers hand it rows that are already allowlisted.

Top-level keys and the fields inside structured attributes are allowlisted:
a key a store invents tomorrow stays private until it is added here on
purpose. Structured attributes have fixed shapes (``_SHAPES``); any other
allowlisted key may hold a scalar or a list of scalars only. Free-form names
chosen by the store (option names, option labels, default names, a verified
fact's ``name``) cannot be allowlisted, so they are screened against the
private-key pattern instead (a denylist): ``options: {"rsr": [...]}`` passes.
"""

from __future__ import annotations

import re
from typing import Any

# Private pricing inputs and supplier provenance, matched anywhere in a key.
# export_* (e.g. Custom Nation's export_usd), wholesale, buy/purchase prices,
# markup and profit are pricing inputs just like cost, landed, duty and margin.
# schema.sql carries the same pattern for the stored-row migration
# (tests/test_rig_cost_guard.py keeps the two identical).
PRIVATE_KEY_PATTERN = (
    r"cost|duty|margin|landed|markup|profit|wholesale|(^|_)export|(^|_)(buy|purchase|dealer|trade)_?price"
    r"|(^|_)vat($|_)|(^|_)fx($|_)|exchange_rate|supplier|pricing_rule|^store$|^source_id$|ship.?from|^region$|^seen_at$"
)
_PRIVATE = re.compile(PRIVATE_KEY_PATTERN, re.I)

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

# Inner keys of structured attributes. ``stock`` is exactly what cn._stock
# reads; ``price_history`` is the was/now badge (archon catalogue); option
# choices are what cn reads (code, label, delta, sku) plus the shown price;
# ``verified`` is a cited fact.
STOCK_KEYS = frozenset({"status", "qty", "location", "lead", "label"})
PRICE_HISTORY_KEYS = frozenset({"was", "amount", "price", "on", "date", "label"})
OPTION_CHOICE_KEYS = frozenset({"code", "label", "delta", "sku", "price"})
VERIFIED_KEYS = frozenset({"name", "value", "source", "note"})

_SCALAR = (str, int, float, bool)


def private_key(key: Any) -> bool:
    return bool(_PRIVATE.search(str(key)))


def _scalar(value: Any) -> bool:
    return value is None or isinstance(value, _SCALAR)


def _pick(value: Any, keys: frozenset[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    # A listed field may hold a scalar or a list of scalars (verified "magazines": [12, 15, 18]).
    return {key: _scalars(item) for key, item in value.items() if key in keys and _scalars(item) is not None}


def _scalars(value: Any) -> Any:
    """A scalar, or a list of scalars. Anything nested is dropped (None)."""
    if _scalar(value):
        return value
    if isinstance(value, list):
        return [item for item in value if _scalar(item)]
    return None


def _choice(value: Any) -> Any:
    if _scalar(value):
        return value
    return _pick(value, OPTION_CHOICE_KEYS)


def _options(value: Any) -> dict[str, Any] | None:
    """{option name: [choice, ...]}. A choice is a scalar or {code,label,delta,sku,price}."""
    if not isinstance(value, dict):
        return None
    kept: dict[str, Any] = {}
    for name, choices in value.items():
        if private_key(name):
            continue
        if isinstance(choices, list):
            kept[str(name)] = [item for item in (_choice(entry) for entry in choices) if item is not None]
        elif isinstance(choices, dict):
            picked = {str(label): _choice(entry) for label, entry in choices.items() if not private_key(label)}
            kept[str(name)] = {label: entry for label, entry in picked.items() if entry is not None}
        elif _scalar(choices):
            kept[str(name)] = choices
    return kept


def _defaults(value: Any) -> dict[str, Any] | None:
    """{option name: chosen code}. Scalars only."""
    if not isinstance(value, dict):
        return None
    return {str(name): item for name, item in value.items() if not private_key(name) and _scalar(item)}


def _price_history(value: Any) -> Any:
    if isinstance(value, dict):
        return _pick(value, PRICE_HISTORY_KEYS)
    if isinstance(value, list):
        return [item for item in (_pick(entry, PRICE_HISTORY_KEYS) for entry in value) if item is not None]
    return None


def _verified_entry(entry: Any) -> Any:
    """A {name,value,source,note} fact, or a plain scalar.

    The entry's ``name`` is a key in all but form, so a private-looking name
    (``{"name": "export_usd", "value": ...}``) drops the whole entry. Nested
    lists (``["export_usd", 437]``) are dropped too.
    """
    if isinstance(entry, dict):
        if private_key(entry.get("name")):
            return None
        return _pick(entry, VERIFIED_KEYS)
    return entry if _scalar(entry) else None


def _verified(value: Any) -> Any:
    if isinstance(value, list):
        return [item for item in (_verified_entry(entry) for entry in value) if item is not None]
    return value if _scalar(value) else None


_SHAPES = {
    "stock": lambda value: _pick(value, STOCK_KEYS),
    "price_history": _price_history,
    "options": _options,
    "defaults": _defaults,
    "verified": _verified,
}


def shopper_attributes(attributes: Any) -> dict[str, Any]:
    """Allowlisted keys, each cut to its allowed shape. Never raises."""
    if not isinstance(attributes, dict):
        return {}
    kept: dict[str, Any] = {}
    for key, value in attributes.items():
        name = str(key)
        if name not in SHOPPER_ATTRIBUTES:
            continue
        shaped = _SHAPES.get(name, _scalars)(value)
        if shaped is not None:
            kept[name] = shaped
    return kept


def shopper_row(row: dict[str, Any]) -> dict[str, Any]:
    """A copy of a catalogue row whose attributes are shopper-safe (for search and ranking)."""
    attributes = row.get("attributes")
    return {**row, "attributes": shopper_attributes(attributes if isinstance(attributes, dict) else {})}


def shopper_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [shopper_row(row) for row in rows]


def split_private(attributes: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """(public, private): top-level keys that look like pricing inputs leave ``attributes``."""
    public = {key: value for key, value in attributes.items() if not private_key(key)}
    private = {key: value for key, value in attributes.items() if private_key(key)}
    return public, private
