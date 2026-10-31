"""Shopper serialization guard: pricing inputs stay on the server."""

import re
from typing import Any

from rigbox.shopper_attributes import shopper_attributes

# Private pricing inputs and supplier provenance, matched anywhere in a key.
# export_* (e.g. Custom Nation's export_usd), wholesale, buy/purchase prices,
# markup and profit are pricing inputs just like cost, landed, duty and margin.
_PRIVATE = re.compile(
    r"cost|duty|margin|landed|markup|profit|wholesale|(^|_)export|(^|_)(buy|purchase|dealer|trade)_?price"
    r"|(^|_)vat($|_)|(^|_)fx($|_)|exchange_rate|supplier|pricing_rule|^store$|^source_id$|ship.?from|^region$|^seen_at$",
    re.I,
)


def private_key(key: Any) -> bool:
    return bool(_PRIVATE.search(str(key)))


def shopper_body(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: shopper_body(shopper_attributes(item) if key == "attributes" and isinstance(item, dict) else item)
                for key, item in value.items() if not private_key(key)}
    if isinstance(value, list):
        return [shopper_body(item) for item in value]
    return value
