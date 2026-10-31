"""Shopper serialization guard: pricing inputs stay on the server."""

import re
from typing import Any

_PRIVATE = re.compile(r"cost|duty|margin|landed|(^|_)vat($|_)|supplier|pricing_rule|^store$|^source_id$|ship.?from|^region$|^seen_at$", re.I)


def shopper_body(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: shopper_body(item) for key, item in value.items() if not _PRIVATE.search(str(key))}
    if isinstance(value, list):
        return [shopper_body(item) for item in value]
    return value
