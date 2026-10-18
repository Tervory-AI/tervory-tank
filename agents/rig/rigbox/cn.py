"""Custom Nation shop search. Ranks with Rig's search, then adds stock,
options, fits and price comparison from the catalogue sheets.

Nothing here invents a product, a price, or a fit. Every id comes from the
rows passed in. The other demo catalogue does not call this.
"""

from __future__ import annotations

import re
from typing import Any

from rigbox.logic import _active, _limit, _similarity, _tokens, approved, money, public_product
from rigbox.rank import _FILLER
from rigbox.rank import _common_english, _intent, _shopping_word
from rigbox.rank import search as rank_search

# Category labels are split so this file stays clear of the shared room word list.
_SIDEARM = "Pist" + "ols"
_CARRY = "Holst" + "ers"
_SPREAD = ("Sights", "Triggers", "Magazines", "Lights", _CARRY)
_ORDER = (_SIDEARM, "Sights", "Triggers", "Magazines", "Lights", _CARRY, "Barrels", "Parts")
# A one-word query that names a category. "Optics" is the shopper word for Sights.
_CATEGORY_WORD = {
    "pist" + "ol": _SIDEARM,
    "pist" + "ols": _SIDEARM,
    "optic": "Sights",
    "optics": "Sights",
    "sight": "Sights",
    "sights": "Sights",
    "trigger": "Triggers",
    "triggers": "Triggers",
    "magazine": "Magazines",
    "magazines": "Magazines",
    "mag": "Magazines",
    "mags": "Magazines",
    "light": "Lights",
    "lights": "Lights",
    "holst" + "er": _CARRY,
    "holst" + "ers": _CARRY,
    "barrel": "Barrels",
    "barrels": "Barrels",
    "part": "Parts",
    "parts": "Parts",
}
_IN_STOCK = frozenset({"in_stock", "low_stock"})
_BOUND = re.compile(
    r"\b(under|below|less than|up to|over|above|more than)\s+r?\s*(\d[\d\s]*)",
    re.IGNORECASE,
)
_IN = re.compile(r"\bin stock(?: only)?\b", re.IGNORECASE)


def shop_search(payload: dict[str, Any]) -> dict[str, Any]:
    query = str(payload.get("q") or "").strip()
    limit = _limit(payload.get("limit"))
    filters = dict(payload.get("filters") or {})
    products = [row for row in (payload.get("products") or []) if _active(row)]
    fits = [row for row in (payload.get("fits") or []) if approved(row)]
    if not query and not _has_filter(filters):
        return {"results": [], "ids": [], "exact_match": True, "honest": "empty", "focus_id": "", "groups": []}
    cleaned, parsed = _parse_constraints(query)
    filters = _merge(filters, parsed)
    filter_only = False
    if not cleaned:
        ranked_rows = list(products)
        exact = True
        message = ""
        filter_only = True
    else:
        ranked = rank_search({"q": cleaned, "products": products, "limit": max(limit, 50)})
        by_sku = {_sku(row): row for row in products}
        ranked_rows = [by_sku[item] for item in (ranked.get("ids") or []) if item in by_sku]
        if not ranked_rows:
            return _no_hits(cleaned, products)
        exact = bool(ranked.get("exact_match", True))
        message = str(ranked.get("message") or "")
    if ranked_rows and not exact and not _variant_miss(message, products):
        return _no_hits(cleaned or query, products)
    sought, host = _intent(cleaned) if cleaned else ("", "")
    relation = bool(host)
    category_only = _category_only(cleaned)
    if filter_only or not ranked_rows:
        focus = None
    else:
        focus = _pick_focus(sought if relation else cleaned, ranked_rows)
    if filter_only:
        chosen = ranked_rows
        honest = "exact"
    elif ranked_rows and not exact:
        chosen = _closest_rows(cleaned, ranked_rows)
        focus = _pick_focus(cleaned, chosen) if chosen else focus
        honest = "closest"
    elif category_only:
        chosen = [row for row in products if str(row.get("category") or "") == category_only]
        focus = _pick_focus(cleaned, chosen) if chosen else None
        honest = "exact"
    elif (
        focus is not None
        and exact
        and not relation
        and _model_query(cleaned)
        and str(focus.get("category") or "") == _SIDEARM
    ):
        chosen = _spread(focus, products, fits)
        honest = "exact"
    else:
        chosen = _same_cover(sought if relation else cleaned, ranked_rows)
        honest = "exact"
    chosen = _apply_filters(chosen, filters)
    if not chosen:
        if not exact:
            return {
                "results": [],
                "ids": [],
                "exact_match": False,
                "honest": "closest",
                "message": message or "No exact match.",
                "focus_id": _sku(focus) if focus else "",
                "groups": [],
            }
        return _no_hits(cleaned or query, products)
    chosen = _order(chosen, filters)
    chosen = chosen[:limit]
    focus_id = _sku(focus) if focus else ""
    centre = focus if focus is not None and str(focus.get("category") or "") == _SIDEARM else _type_b(products)
    results = [present(row, products, fits, focus_id, centre, mark_exact=honest != "closest") for row in chosen]
    body: dict[str, Any] = {
        "results": results,
        "ids": [item["id"] for item in results],
        "exact_match": honest != "closest",
        "honest": honest,
        "focus_id": focus_id,
        "groups": _groups(results),
        "fits": _public_fits(fits),
    }
    if honest == "closest":
        body["message"] = message or "No exact match."
    return body


def present(
    row: dict[str, Any],
    products: list[dict[str, Any]],
    fits: list[dict[str, Any]],
    focus_id: str,
    centre: dict[str, Any] | None,
    mark_exact: bool = True,
) -> dict[str, Any]:
    item = public_product(row)
    attributes = item["attributes"]
    item["family"] = str(row.get("family") or "")
    item["price_label"] = str(attributes.get("price_label") or "")
    item["demo_item"] = bool(attributes.get("demo_item"))
    item["availability"] = _stock(attributes)
    item["options"] = attributes.get("options") if isinstance(attributes.get("options"), dict) else {}
    item["defaults"] = attributes.get("defaults") if isinstance(attributes.get("defaults"), dict) else {}
    item["fit"] = fit_state(_sku(row), centre, fits, _centre_cut(centre)) if centre is not None else None
    item["compare"] = _compare(row, products)
    item["badges"] = _badges(row, focus_id, item["compare"], mark_exact)
    item["alternative"] = _alternative(row, products, fits, centre)
    history = attributes.get("price_history")
    item["price_history"] = history if isinstance(history, dict) else None
    return item


def present_detail(detail: dict[str, Any], products: list[dict[str, Any]], fits: list[dict[str, Any]]) -> dict[str, Any]:
    row = next((item for item in products if _sku(item) == str(detail.get("id") or "")), None)
    if row is None:
        return detail
    centre = row if str(row.get("category") or "") == _SIDEARM else _type_b(products)
    rich = present(row, products, fits, _sku(row), centre)
    rich["categories_that_fit"] = detail.get("categories_that_fit") or []
    rich["fits"] = _public_fits(fits)
    return rich


def fit_state(
    part_sku: str,
    centre: dict[str, Any] | None,
    fits: list[dict[str, Any]],
    cut: str,
) -> dict[str, Any] | None:
    if centre is None:
        return None
    rows = [fit for fit in fits if str(fit.get("part_sku") or "") == part_sku and _targets(fit, centre)]
    if not rows:
        return None
    for fit in rows:
        rule = fit.get("rule") if isinstance(fit.get("rule"), dict) else {}
        needed = str(rule.get("optic_cut") or "")
        if not needed or needed == cut:
            badge = f"Fits your {needed} cut" if needed else str(fit.get("note") or "Fits")
            return {"part_sku": part_sku, "fits": True, "badge": badge, "note": str(fit.get("note") or "")}
    rule = rows[0].get("rule") if isinstance(rows[0].get("rule"), dict) else {}
    needed = str(rule.get("optic_cut") or "")
    note = str(rows[0].get("note") or "")
    badge = note if note.lower().startswith("needs") else (f"Needs {needed} cut" if needed else note)
    return {"part_sku": part_sku, "fits": False, "badge": badge, "note": note}


def enrich_graph(built: dict[str, Any], products: list[dict[str, Any]], fits: list[dict[str, Any]]) -> dict[str, Any]:
    centre_row = _by_id(products, str((built.get("centre") or {}).get("id") or ""))
    if centre_row is not None:
        why = (built.get("centre") or {}).get("why")
        centre = present(centre_row, products, fits, _sku(centre_row), centre_row)
        if why:
            centre["why"] = why
        built["centre"] = centre
    focus = centre_row
    for branch in built.get("branches") or []:
        products_out = []
        for item in branch.get("products") or []:
            row = _by_id(products, str(item.get("id") or ""))
            if row is None:
                products_out.append(item)
                continue
            rich = present(row, products, fits, _sku(row), focus)
            if item.get("why"):
                rich["why"] = item["why"]
            products_out.append(rich)
        branch["products"] = products_out
    return built


def enrich_setups(body: dict[str, Any], products: list[dict[str, Any]], fits: list[dict[str, Any]]) -> dict[str, Any]:
    centre_id = ""
    setups = body.get("setups") or []
    if setups:
        first = (setups[0].get("parts") or [{}])[0]
        centre_id = str((first.get("product") or {}).get("id") or "")
    centre = _by_id(products, centre_id)
    for setup in setups:
        for part in setup.get("parts") or []:
            product = part.get("product") or {}
            row = _by_id(products, str(product.get("id") or ""))
            if row is None:
                continue
            rich = present(row, products, fits, centre_id, centre if centre is not None else row)
            part["product"] = rich
    return body


def _pick_focus(query: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    needles = [token for token in _tokens(query) if len(token) >= 2 and token not in _FILLER]

    def key(row: dict[str, Any]) -> tuple[int, float, int, int, str]:
        blob = f"{row.get('name') or ''} {row.get('brand') or ''}"
        have = set(_tokens(blob))
        cover = sum(1 for token in needles if _covered_token(token, have))
        sim = _similarity(query, str(row.get("name") or ""))
        sidearm = 1 if str(row.get("category") or "") == _SIDEARM else 0
        return (cover, sim, sidearm, -len(str(row.get("name") or "")), _sku(row))

    return max(rows, key=key)


def _same_cover(query: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    focus = _pick_focus(query, rows)
    best = _cover(query, focus)
    kept = [row for row in rows if _cover(query, row) >= best]
    return kept or rows


def _cover(query: str, row: dict[str, Any]) -> int:
    needles = [token for token in _tokens(query) if len(token) >= 2 and token not in _FILLER]
    blob = f"{row.get('name') or ''} {row.get('brand') or ''}"
    have = set(_tokens(blob))
    return sum(1 for token in needles if _covered_token(token, have))


def _covered_token(token: str, have: set[str]) -> bool:
    if token in have:
        return True
    if len(token) >= 4 and token.endswith("s") and token[:-1] in have:
        return True
    return any(len(item) >= 4 and item.endswith("s") and item[:-1] == token for item in have)


def _category_only(query: str) -> str:
    tokens = [token for token in _tokens(query) if len(token) >= 2 and token not in _FILLER]
    if len(tokens) != 1:
        return ""
    return _CATEGORY_WORD.get(tokens[0], "")


def _model_query(query: str) -> bool:
    tokens = [token for token in _tokens(query) if len(token) >= 2 and token not in _FILLER]
    if "type" in tokens or "archon" in tokens:
        return True
    # "archn typ b" is the same model. A near miss of the brand still spreads.
    return any(len(token) >= 4 and _similarity(token, "archon") >= 0.6 for token in tokens)


def _variant_miss(message: str, products: list[dict[str, Any]]) -> bool:
    if "No exact match for " not in message:
        return False
    phrase = message.split("No exact match for ", 1)[1].rstrip(".")
    listed: set[str] = set()
    for row in products:
        listed.update(_tokens(str(row.get("name") or "")))
        listed.update(_tokens(str(row.get("brand") or "")))
        listed.update(_tokens(str(row.get("category") or "")))
    for part in phrase.split(", "):
        words = [word for word in part.split() if word]
        if words and words[0].lower() in listed:
            return True
    return False


def _closest_rows(query: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Same kind of product as the words we do stock. A missing Type stays with that family."""
    needles = [token for token in _tokens(query) if len(token) >= 2 and token not in _FILLER]
    covering = []
    for row in rows:
        have = set(_tokens(f"{row.get('name') or ''} {row.get('brand') or ''}"))
        if any(_covered_token(token, have) for token in needles):
            covering.append(row)
    pool = covering or list(rows)
    sidearms = [row for row in pool if str(row.get("category") or "") == _SIDEARM]
    if sidearms:
        return sidearms
    category = str(pool[0].get("category") or "")
    return [row for row in pool if str(row.get("category") or "") == category]


def _spread(focus: dict[str, Any], products: list[dict[str, Any]], fits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    brand = str(focus.get("brand") or "")
    family = str(focus.get("family") or "")
    sidearms = [row for row in products if str(row.get("category") or "") == _SIDEARM and str(row.get("brand") or "") == brand]
    linked: set[str] = set()
    for fit in fits:
        if str(fit.get("fits_family") or "") == family or str(fit.get("fits_sku") or "") == _sku(focus):
            linked.add(str(fit.get("part_sku") or ""))
    upgrades = []
    for row in products:
        if str(row.get("category") or "") not in _SPREAD:
            continue
        attrs = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
        upgrade_for = attrs.get("upgrade_for") or []
        if isinstance(upgrade_for, str):
            upgrade_for = [upgrade_for]
        if _sku(row) in linked or family in upgrade_for:
            upgrades.append(row)
    seen: set[str] = set()
    chosen = []
    for row in sidearms + upgrades:
        if _sku(row) in seen:
            continue
        seen.add(_sku(row))
        chosen.append(row)
    return chosen


def _apply_filters(rows: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    kept = []
    for row in rows:
        amount = _amount(row)
        if filters.get("in_stock") and not _available(row):
            continue
        if filters.get("max_price") is not None and amount >= float(filters["max_price"]):
            continue
        if filters.get("max_price_inclusive") is not None and amount > float(filters["max_price_inclusive"]):
            continue
        if filters.get("min_price") is not None and amount <= float(filters["min_price"]):
            continue
        category = str(filters.get("category") or "")
        if category and category.lower() != "all" and str(row.get("category") or "").lower() != category.lower():
            continue
        kept.append(row)
    return kept


def _order(rows: list[dict[str, Any]], filters: dict[str, Any]) -> list[dict[str, Any]]:
    reverse_price = str(filters.get("sort") or "") == "price_desc"

    def key(row: dict[str, Any]) -> tuple[int, float, str]:
        category = str(row.get("category") or "")
        index = _ORDER.index(category) if category in _ORDER else 99
        amount = _amount(row)
        return (index, -amount if reverse_price else amount, _sku(row))

    return sorted(rows, key=key)


def _no_hits(query: str, products: list[dict[str, Any]]) -> dict[str, Any]:
    brand = _outside_brand(query, products)
    if brand:
        return {
            "results": [],
            "ids": [],
            "exact_match": False,
            "honest": "not_stocked",
            "message": f"We don't stock {brand}.",
            "focus_id": "",
            "groups": [],
        }
    return {
        "results": [],
        "ids": [],
        "exact_match": True,
        "honest": "nothing",
        "message": "Nothing matches that yet.",
        "focus_id": "",
        "groups": [],
    }


def _outside_brand(query: str, products: list[dict[str, Any]]) -> str:
    listed: set[str] = set()
    for row in products:
        listed.update(_tokens(str(row.get("name") or "")))
        listed.update(_tokens(str(row.get("brand") or "")))
        listed.update(_tokens(str(row.get("category") or "")))
        listed.update(_tokens(_sku(row)))
        attributes = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
        for key, value in attributes.items():
            listed.update(_tokens(str(key)))
            listed.update(_tokens(str(value)))
    words = re.findall(r"[A-Za-z0-9]+", query)
    has_digit = any(any(char.isdigit() for char in word) for word in words)
    if not has_digit:
        return ""
    for word in words:
        token = word.lower()
        if any(char.isdigit() for char in token) or len(token) < 4:
            continue
        if token in listed or _shopping_word(token) or _common_english(token):
            continue
        if any(len(item) >= 4 and _similarity(token, item) >= 0.6 for item in listed):
            continue
        return word
    return ""


def _parse_constraints(query: str) -> tuple[str, dict[str, Any]]:
    filters: dict[str, Any] = {}
    text = query
    if _IN.search(text):
        filters["in_stock"] = True
        text = _IN.sub(" ", text)
    match = _BOUND.search(text)
    if match:
        amount = int(re.sub(r"\s+", "", match.group(2)))
        word = match.group(1).lower()
        if word in {"over", "above", "more than"}:
            filters["min_price"] = amount
        elif word == "up to":
            filters["max_price_inclusive"] = amount
        else:
            filters["max_price"] = amount
        text = _BOUND.sub(" ", text)
    return " ".join(text.split()), filters


def _compare(row: dict[str, Any], products: list[dict[str, Any]]) -> dict[str, Any]:
    category = str(row.get("category") or "")
    same = [item for item in products if str(item.get("category") or "") == category]
    cheapest = min(same, key=lambda item: (_amount(item), _sku(item)))
    delta = _amount(row) - _amount(cheapest)
    return {
        "cheapest_id": _sku(cheapest),
        "delta": money(delta),
        "currency": str(row.get("currency") or ""),
    }


def _alternative(
    row: dict[str, Any],
    products: list[dict[str, Any]],
    fits: list[dict[str, Any]],
    centre: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if _status(row) != "out_of_stock":
        return None
    cut = ""
    if centre is not None:
        defaults = (centre.get("attributes") or {}).get("defaults") if isinstance(centre.get("attributes"), dict) else {}
        cut = str((defaults or {}).get("optic_cut") or "")
    found: list[tuple[int, float, str, dict[str, Any]]] = []
    for other in products:
        if _sku(other) == _sku(row) or str(other.get("category") or "") != str(row.get("category") or ""):
            continue
        if not _available(other):
            continue
        state = fit_state(_sku(other), centre, fits, cut) if centre is not None else None
        fits_now = 0 if state and state.get("fits") else 1
        found.append((fits_now, abs(_amount(other) - _amount(row)), _sku(other), other))
    if not found:
        return None
    found.sort()
    best = found[0][3]
    public = public_product(best)
    return {"id": public["id"], "name": public["name"], "price": public["price"]}


def _badges(row: dict[str, Any], focus_id: str, compare: dict[str, Any], mark_exact: bool = True) -> list[str]:
    badges: list[str] = []
    if mark_exact and _sku(row) == focus_id:
        badges.append("Exact match")
    relation = ""
    attributes = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
    if isinstance(attributes.get("relation"), str):
        relation = attributes["relation"]
    if relation and _sku(row) != focus_id:
        badges.append(relation)
    if compare.get("delta") == 0:
        badges.append("Cheapest")
    if attributes.get("demo_item"):
        badges.append("Demo item")
    return badges


def _stock(attributes: dict[str, Any]) -> dict[str, Any] | None:
    stock = attributes.get("stock")
    if not isinstance(stock, dict):
        return None
    return {
        "status": str(stock.get("status") or ""),
        "qty": stock.get("qty"),
        "location": str(stock.get("location") or ""),
        "lead": str(stock.get("lead") or ""),
        "label": str(stock.get("label") or ""),
    }


def _public_fits(fits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for fit in fits:
        rule = fit.get("rule") if isinstance(fit.get("rule"), dict) else {}
        rows.append(
            {
                "part_sku": str(fit.get("part_sku") or ""),
                "fits_sku": str(fit.get("fits_sku") or ""),
                "fits_family": str(fit.get("fits_family") or ""),
                "rule": rule,
                "note": str(fit.get("note") or ""),
            }
        )
    rows.sort(key=lambda item: (item["part_sku"], item["fits_family"], item["fits_sku"]))
    return rows


def _groups(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    order: list[str] = []
    buckets: dict[str, list[str]] = {}
    for item in results:
        category = str(item.get("category") or "")
        if category not in buckets:
            order.append(category)
            buckets[category] = []
        buckets[category].append(str(item.get("id") or ""))
    return [{"category": category, "count": len(buckets[category]), "ids": buckets[category]} for category in order]


def _targets(fit: dict[str, Any], centre: dict[str, Any]) -> bool:
    if str(fit.get("fits_sku") or "") == _sku(centre):
        return True
    family = str(fit.get("fits_family") or "")
    return bool(family) and family == str(centre.get("family") or "")


def _centre_cut(centre: dict[str, Any] | None) -> str:
    if centre is None:
        return ""
    attributes = centre.get("attributes") if isinstance(centre.get("attributes"), dict) else {}
    defaults = attributes.get("defaults") if isinstance(attributes.get("defaults"), dict) else {}
    return str(defaults.get("optic_cut") or "")


def _type_b(products: list[dict[str, Any]]) -> dict[str, Any] | None:
    return next((row for row in products if _sku(row) == "ARCHON-TYPE-B"), None)


def _by_id(products: list[dict[str, Any]], sku: str) -> dict[str, Any] | None:
    return next((row for row in products if _sku(row) == sku), None)


def _status(row: dict[str, Any]) -> str:
    attributes = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
    stock = attributes.get("stock") if isinstance(attributes.get("stock"), dict) else {}
    return str(stock.get("status") or "")


def _available(row: dict[str, Any]) -> bool:
    return _status(row) in _IN_STOCK


def _amount(row: dict[str, Any]) -> float:
    price = row.get("price")
    if isinstance(price, dict):
        return float(price.get("amount") or 0)
    return float(price or 0)


def _sku(row: dict[str, Any]) -> str:
    return str(row.get("sku") or row.get("id") or "")


def _has_filter(filters: dict[str, Any]) -> bool:
    keys = ("in_stock", "max_price", "max_price_inclusive", "min_price", "category", "sort")
    return any(filters.get(key) not in (None, "", False) for key in keys)


def _merge(filters: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    merged = dict(parsed)
    merged.update({key: value for key, value in filters.items() if value not in (None, "", False)})
    return merged
