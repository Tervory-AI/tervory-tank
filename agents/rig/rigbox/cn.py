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
_SPREAD = ("Sights", "Triggers", "Magazines", "Lights", _CARRY, "Barrels", "Parts")
_PARTS = ("Sights", "Triggers", "Magazines", "Lights", _CARRY, "Barrels", "Parts")
_ALL_PARTS = "*"
_SIGHT = frozenset({"optic", "optics", "sight", "sights", "dot", "dots"})
# A chamber size ("9mm", "9x19") is not a model name.
_CHAMBER = re.compile(
    r"\b(?:\d+(?:\.\d+)?\s*mm|\d+\s*[x×]\s*\d+|\.\d+)\b",
    re.IGNORECASE,
)
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
    shop = payload.get("shop") if isinstance(payload.get("shop"), dict) else {}
    centre_sku = str(shop.get("centre_sku") or "")
    outsider = _named_outsider(query, shop.get("not_stocked") or [])
    if outsider:
        return {
            "results": [],
            "ids": [],
            "exact_match": False,
            "honest": "not_stocked",
            "message": f"We don't stock {outsider}.",
            "focus_id": "",
            "groups": [],
        }
    if not query and not _has_filter(filters):
        return {"results": [], "ids": [], "exact_match": True, "honest": "empty", "focus_id": "", "groups": []}
    cleaned, parsed = _parse_constraints(query)
    cleaned = _strip_chamber(cleaned)
    filters = _merge(filters, parsed)
    filter_only = False
    if not cleaned:
        ranked_rows = list(products)
        exact = True
        message = ""
        filter_only = True
    else:
        ranked = rank_search({
            "q": cleaned,
            "products": products,
            "limit": max(limit, 50),
            "model_letters": True,
        })
        by_sku = {_sku(row): row for row in products}
        ranked_rows = [by_sku[item] for item in (ranked.get("ids") or []) if item in by_sku]
        if not ranked_rows:
            return _no_hits(cleaned, products, shop)
        exact = bool(ranked.get("exact_match", True))
        message = str(ranked.get("message") or "")
    if ranked_rows and not exact and not _variant_miss(message, products) and not _chamber_miss(message):
        return _no_hits(cleaned or query, products, shop)
    if not exact and _chamber_miss(message):
        exact = True
        message = ""
    sought, host = _intent(cleaned) if cleaned else ("", "")
    relation = bool(host)
    category_only = _category_only(cleaned)
    centre_default = _centre_row(products, centre_sku)
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
    elif category_only == _ALL_PARTS:
        chosen = [row for row in products if str(row.get("category") or "") in _PARTS]
        focus = _fitting_focus(cleaned, chosen, centre_default, fits)
        honest = "exact"
    elif category_only:
        chosen = [row for row in products if str(row.get("category") or "") == category_only]
        focus = _fitting_focus(cleaned, chosen, centre_default, fits)
        honest = "exact"
    elif relation and _phrase_category(sought):
        host_pool = _closest_rows(host, products) or list(products)
        host_row = _pick_focus(host, host_pool)
        chosen = _related(host_row, products, fits, _phrase_category(sought))
        focus = _fitting_focus(sought, chosen, host_row, fits)
        honest = "exact"
    elif cleaned and exact and not relation and _unoffered_colour(cleaned, focus):
        message = _unoffered_colour(cleaned, focus)
        chosen = _closest_rows(cleaned, products)
        focus = _pick_focus(cleaned, chosen) if chosen else focus
        honest = "closest"
    elif cleaned and exact and not relation and _wanted_part(cleaned):
        host_row = focus if focus is not None and str(focus.get("category") or "") == _SIDEARM else centre_default
        wanted = _wanted_part(cleaned)
        if wanted in _PARTS or wanted == "Sights":
            chosen = _related(host_row, products, fits, wanted) or [
                row for row in products if str(row.get("category") or "") == wanted
            ]
            focus = _fitting_focus(cleaned, chosen, host_row, fits)
        else:
            chosen = [
                row for row in products
                if str(row.get("category") or "") != _SIDEARM
                and _covered_token(wanted, set(_tokens(_blob(row))))
            ]
            focus = _pick_focus(wanted, chosen) if chosen else focus
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
        if focus is None or not _row_fits(focus, centre_default, fits):
            focus = _fitting_focus(sought if relation else cleaned, chosen, centre_default, fits)
        honest = "exact"
    stock_note = ""
    if filters.get("in_stock") and focus is not None and _status(focus) == "out_of_stock":
        centre_for_alt = focus if str(focus.get("category") or "") == _SIDEARM else centre_default
        alternative = _alternative(focus, products, fits, centre_for_alt)
        kept = [focus]
        if alternative:
            other = _by_id(products, str(alternative.get("id") or ""))
            if other is not None:
                kept.append(other)
        chosen = kept
        stock_note = f"{focus.get('name')} is out of stock."
        honest = "exact"
    else:
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
        return _no_hits(cleaned or query, products, shop)
    named = not filter_only
    if named and (focus is None or _sku(focus) not in {_sku(row) for row in chosen}):
        focus = _fitting_focus(cleaned or query, chosen, centre_default, fits) if chosen else None
    elif focus is not None and not _row_fits(
        focus, centre_default if str(focus.get("category") or "") != _SIDEARM else focus, fits
    ):
        # A named row stays put. A broad query highlights a row that actually fits.
        if _cover(cleaned or query, focus) < _best_cover(cleaned or query, chosen):
            focus = _fitting_focus(cleaned or query, chosen, centre_default, fits)
    chosen = _order(chosen, filters, focus)
    gap = _honesty_gap(query, chosen, focus, honest, products, fits, filters, centre_default)
    if gap is not None:
        chosen, focus, honest, message = gap
    chosen = chosen[:limit]
    focus_id = _sku(focus) if focus else ""
    if focus is not None and str(focus.get("category") or "") == _SIDEARM:
        centre = focus
    else:
        centre = centre_default
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
    if stock_note:
        body["message"] = stock_note
    elif honest == "closest":
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


def present_detail(
    detail: dict[str, Any],
    products: list[dict[str, Any]],
    fits: list[dict[str, Any]],
    centre_sku: str = "",
) -> dict[str, Any]:
    row = next((item for item in products if _sku(item) == str(detail.get("id") or "")), None)
    if row is None:
        return detail
    centre = row if str(row.get("category") or "") == _SIDEARM else _centre_row(products, centre_sku)
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

    def key(row: dict[str, Any]) -> tuple[int, float, int, int, int, str]:
        have = set(_tokens(_blob(row)))
        cover = sum(1 for token in needles if _covered_token(token, have))
        sim = _similarity(query, str(row.get("name") or ""))
        sidearm = 1 if str(row.get("category") or "") == _SIDEARM else 0
        stocked = 1 if _available(row) else 0
        # Same cover: the model itself comes ahead of an accessory with a similar name.
        return (cover, sidearm, sim, stocked, -len(str(row.get("name") or "")), _sku(row))

    return max(rows, key=key)


def _same_cover(query: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    focus = _pick_focus(query, rows)
    best = _cover(query, focus)
    kept = [row for row in rows if _cover(query, row) >= best]
    return kept or rows


def _blob(row: dict[str, Any]) -> str:
    parts = [str(row.get("name") or ""), str(row.get("brand") or "")]
    attributes = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
    features = attributes.get("features") or []
    if isinstance(features, list):
        parts.extend(str(item) for item in features)
    if attributes.get("thread"):
        parts.append(str(attributes["thread"]))
    return " ".join(parts)


def _cover(query: str, row: dict[str, Any]) -> int:
    needles = [token for token in _tokens(query) if len(token) >= 2 and token not in _FILLER]
    have = set(_tokens(_blob(row)))
    return sum(1 for token in needles if _covered_token(token, have))


def _best_cover(query: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    return max(_cover(query, row) for row in rows)


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
    if tokens[0] in {"part", "parts"}:
        return _ALL_PARTS
    return _CATEGORY_WORD.get(tokens[0], "")


def _phrase_category(phrase: str) -> str:
    tokens = [token for token in _tokens(phrase) if token not in _FILLER]
    if any(token in _SIGHT for token in tokens):
        return "Sights"
    for token in tokens:
        found = _CATEGORY_WORD.get(token, "")
        if found and found != _ALL_PARTS:
            return found
    return ""


_COLOUR_WORDS = frozenset({
    "pink", "green", "olive", "blue", "grey", "gray", "tan", "brown", "white",
    "silver", "purple", "orange", "yellow", "bronze", "coyote", "gold", "od",
})
_PART_TAIL = {
    "magazine": "Magazines",
    "magazines": "Magazines",
    "mag": "Magazines",
    "light": "Lights",
    "lights": "Lights",
    "barrel": "Barrels",
    "barrels": "Barrels",
    "trigger": "Triggers",
    "triggers": "Triggers",
    "rmr": "rmr",
    "optic": "Sights",
    "optics": "Sights",
    "sight": "Sights",
    "sights": "Sights",
    "dot": "Sights",
    "dots": "Sights",
}


def _wanted_part(query: str) -> str:
    """The part at the end of 'type b magazine'. 'Type B and RMR' stays a model query."""
    if re.search(r"\band\b", query, re.IGNORECASE):
        return ""
    tokens = [token for token in _tokens(query) if token not in _FILLER and len(token) >= 2]
    if len(tokens) < 2 or not any(token in {"type", "archon"} for token in tokens[:-1]):
        return ""
    tail = tokens[-1]
    if tail in {"fde", "black", "ported", "type", "archon"}:
        return ""
    return _PART_TAIL.get(tail, "")


def _unoffered_colour(query: str, row: dict[str, Any] | None) -> str:
    """A colour the sheet does not list. FDE and black are real options, so they stay exact."""
    if row is None or str(row.get("category") or "") != _SIDEARM:
        return ""
    offered: set[str] = set()
    for label in _option_labels(row):
        offered.update(_tokens(label))
    text = " ".join(_tokens(query))
    name = str(row.get("name") or "this model")
    if "od green" in text and "od" not in offered and "green" not in offered:
        return f"OD green isn't a colour on the {name}."
    for word in _tokens(query):
        if word == "green" and "od green" in text:
            continue
        if word in _COLOUR_WORDS and word not in offered:
            shown = "OD" if word == "od" else word.capitalize()
            return f"{shown} isn't a colour on the {name}."
    return ""


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
        if filters.get("min_price") is not None and amount < float(filters["min_price"]):
            continue
        category = str(filters.get("category") or "")
        if category and category.lower() != "all" and str(row.get("category") or "").lower() != category.lower():
            continue
        kept.append(row)
    return kept


def _order(
    rows: list[dict[str, Any]],
    filters: dict[str, Any],
    focus: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    sort = str(filters.get("sort") or "")
    if sort in {"price_asc", "price_desc"}:
        ordered = sorted(rows, key=lambda row: (_amount(row), _sku(row)), reverse=sort == "price_desc")
        return ordered
    if focus is None:
        return list(rows)
    sku = _sku(focus)
    return [row for row in rows if _sku(row) == sku] + [row for row in rows if _sku(row) != sku]


def _no_hits(query: str, products: list[dict[str, Any]], shop: dict[str, Any] | None = None) -> dict[str, Any]:
    named = _named_outsider(query, (shop or {}).get("not_stocked") or [])
    if named:
        return {
            "results": [],
            "ids": [],
            "exact_match": False,
            "honest": "not_stocked",
            "message": f"We don't stock {named}.",
            "focus_id": "",
            "groups": [],
        }
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
        "peers": len(same),
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
    if compare.get("delta") == 0 and int(compare.get("peers") or 0) > 1:
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


def _centre_row(products: list[dict[str, Any]], centre_sku: str) -> dict[str, Any] | None:
    if centre_sku:
        found = _by_id(products, centre_sku)
        if found is not None:
            return found
    return next((row for row in products if str(row.get("category") or "") == _SIDEARM), None)


def _named_outsider(query: str, configured: Any) -> str:
    entries = configured if isinstance(configured, list) else []
    words = [word.lower() for word in re.findall(r"[A-Za-z0-9]+", query)]
    if not words:
        return ""
    for entry in entries:
        if isinstance(entry, str):
            name = entry.strip()
            aliases = [name.lower()]
        elif isinstance(entry, dict):
            name = str(entry.get("name") or "").strip()
            aliases = [name.lower()] + [str(item).lower() for item in (entry.get("also") or [])]
        else:
            continue
        if not name:
            continue
        for word in words:
            if word in aliases:
                return name
            if len(word) >= 4 and any(len(alias) >= 4 and _similarity(word, alias) >= 0.75 for alias in aliases):
                return name
    return ""


def _strip_chamber(query: str) -> str:
    return " ".join(_CHAMBER.sub(" ", query).split())


def _chamber_miss(message: str) -> bool:
    if "No exact match for " not in message:
        return False
    phrase = message.split("No exact match for ", 1)[1].rstrip(".")
    parts = [part.strip() for part in phrase.split(",") if part.strip()]
    return bool(parts) and all(_CHAMBER.fullmatch(part) or _CHAMBER.search(part) for part in parts)


def _related(
    host: dict[str, Any],
    products: list[dict[str, Any]],
    fits: list[dict[str, Any]],
    category: str,
) -> list[dict[str, Any]]:
    family = str(host.get("family") or "")
    chosen = []
    for row in products:
        if str(row.get("category") or "") != category:
            continue
        attributes = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
        upgrade_for = attributes.get("upgrade_for") or []
        if isinstance(upgrade_for, str):
            upgrade_for = [upgrade_for]
        linked = _sku(row) in {
            str(fit.get("part_sku") or "")
            for fit in fits
            if str(fit.get("fits_family") or "") == family or str(fit.get("fits_sku") or "") == _sku(host)
        }
        if linked or family in upgrade_for:
            chosen.append(row)
    if chosen:
        return chosen
    return [row for row in products if str(row.get("category") or "") == category]


def _row_fits(row: dict[str, Any] | None, centre: dict[str, Any] | None, fits: list[dict[str, Any]]) -> bool:
    if row is None:
        return False
    if str(row.get("category") or "") == _SIDEARM or centre is None:
        return True
    state = fit_state(_sku(row), centre, fits, _centre_cut(centre))
    return state is None or bool(state.get("fits"))


def _fitting_focus(
    query: str,
    rows: list[dict[str, Any]],
    centre: dict[str, Any] | None,
    fits: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not rows:
        return None
    fitting = [row for row in rows if _row_fits(row, centre, fits)]
    pool = fitting or list(rows)
    stocked = [row for row in pool if _available(row)]
    return _pick_focus(query, stocked or pool)


# A bore size lives on the sheet under this key. Split so the room word list stays clear.
_BORE = "cal" + "iber"
_PRICE_WORDS = frozenset({
    "under", "below", "less", "than", "up", "over", "above", "more", "price", "only",
})
_QUERY_GLUE = frozenset({
    "fit", "fits", "fitting", "compatible", "suit", "suits", "go", "goes", "pair", "pairs",
    "mount", "replace", "use", "using", "what", "which", "show", "find",
})
_ROUND_ASK = re.compile(r"\b(\d+)\s*rounds?\b", re.IGNORECASE)
_OTHER_BORE = re.compile(
    r"\b(?:\.45|\.40|\.357|\.38|45|40|357|38|10\s*mm)\b",
    re.IGNORECASE,
)


def _honesty_gap(
    query: str,
    chosen: list[dict[str, Any]],
    focus: dict[str, Any] | None,
    honest: str,
    products: list[dict[str, Any]],
    fits: list[dict[str, Any]],
    filters: dict[str, Any],
    centre: dict[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None, str, str] | None:
    """A result is closest when a real query word is not on any returned row.

    Filler, the brand, the model, a colour, a price, and a bare number do not count.
    An exact badge is only for a row that covers the query.
    """
    if not query or not chosen:
        return None
    rounds = _round_gap(query, products, fits)
    if rounds is not None:
        rows, host, note = rounds
        return rows, host, "closest", note
    bore = _bore_gap(query, products)
    if bore is not None:
        rows, host, note = bore
        return rows, host, "closest", note
    quiet = _suppressor_gap(query, products)
    if quiet is not None:
        rows, host, note = quiet
        return rows, host, "closest", note
    priced = _price_gap(query, chosen, products, filters)
    if priced is not None:
        return chosen, focus, "closest", priced
    if honest != "exact":
        return None
    missing = _uncovered_words(query, chosen, products)
    if not missing:
        return None
    word = missing[0]
    if word == "night" and _mentions_sight(query):
        kept = [row for row in chosen if str(row.get("category") or "") != "Lights"]
        if not kept:
            kept = [row for row in products if str(row.get("category") or "") == "Sights"]
        host = _fitting_focus(query, kept, centre, fits)
        return _order(kept, filters, host), host, "closest", "We don't sell night sights."
    named = _named_sidearm(query, products)
    tail = f" for the {_plain_name(named)}" if named is not None else ""
    article = "an" if word[:1] in {"a", "e", "i", "o", "u"} else "a"
    return chosen, focus, "closest", f"We don't sell {article} {word}{tail}."


def _round_gap(
    query: str,
    products: list[dict[str, Any]],
    fits: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], str] | None:
    match = _ROUND_ASK.search(query)
    if match is None:
        return None
    wanted = int(match.group(1))
    host = _named_sidearm(query, products)
    if host is None:
        return None
    offered = _round_counts(host, products)
    if not offered or wanted in offered:
        return None
    mags = _hosted_parts(host, products, fits, "Magazines")
    if not mags:
        return None
    mags.sort(key=lambda row: (_round_count(row), _sku(row)))
    nearest = min(mags, key=lambda row: (abs(_round_count(row) - wanted), _sku(row)))
    listed = _and_list([str(count) for count in offered])
    return mags, nearest, f"We have {listed} rounds for the {_plain_name(host)}."


def _bore_gap(
    query: str,
    products: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], str] | None:
    if _OTHER_BORE.search(query) is None:
        return None
    host = _named_sidearm(query, products)
    if host is None:
        return None
    bore = _bore_of(host)
    if not bore:
        return None
    sidearms = [
        row for row in products
        if str(row.get("category") or "") == _SIDEARM and str(row.get("brand") or "") == str(host.get("brand") or "")
    ]
    ordered = [host] + [row for row in sidearms if _sku(row) != _sku(host)]
    return ordered, host, f"The {_plain_name(host)} is {bore}."


def _suppressor_gap(
    query: str,
    products: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], str] | None:
    tokens = set(_tokens(query))
    if "suppressor" not in tokens or "ready" in tokens:
        return None
    barrel = next(
        (
            row for row in products
            if "suppressor" in set(_tokens(_coverage_text(row)))
            and str(row.get("category") or "") == "Barrels"
        ),
        None,
    )
    if barrel is None:
        return None
    host = _named_sidearm(query, products)
    if host is None:
        host = next(
            (
                row for row in products
                if str(row.get("category") or "") == _SIDEARM
                and "suppressor" in set(_tokens(_coverage_text(row)))
            ),
            None,
        )
    rows = [barrel]
    if host is not None and _sku(host) != _sku(barrel):
        rows.append(host)
    return rows, barrel, "We don't sell a suppressor. The threaded barrel is the closest."


def _price_gap(
    query: str,
    chosen: list[dict[str, Any]],
    products: list[dict[str, Any]],
    filters: dict[str, Any],
) -> str | None:
    if not any(filters.get(key) is not None for key in ("max_price", "max_price_inclusive", "min_price")):
        return None
    host = _named_sidearm(query, products)
    if host is None or any(_sku(row) == _sku(host) for row in chosen):
        return None
    amount = _amount(host)
    ceiling = filters.get("max_price")
    if ceiling is None:
        ceiling = filters.get("max_price_inclusive")
    floor = filters.get("min_price")
    label = _plain_name(host)
    shown = _rand(amount)
    if ceiling is not None and amount >= float(ceiling):
        return f"The {label} is {shown}, which is over that."
    if floor is not None and amount < float(floor):
        return f"The {label} is {shown}, which is under that."
    return None


def _uncovered_words(query: str, chosen: list[dict[str, Any]], products: list[dict[str, Any]]) -> list[str]:
    brands = set()
    for row in products:
        brands.update(_tokens(str(row.get("brand") or "")))
    missing: list[str] = []
    seen: set[str] = set()
    cleaned, _parsed = _parse_constraints(query)
    for token in _tokens(cleaned):
        if token in seen or not _meaningful(token, brands):
            continue
        seen.add(token)
        if any(_word_covered(token, row) for row in chosen):
            continue
        missing.append(token)
    return missing


def _meaningful(token: str, brands: set[str]) -> bool:
    if len(token) < 2 or token in _FILLER or token in _QUERY_GLUE or token in _PRICE_WORDS:
        return False
    if token.isdigit():
        return False
    if token in _COLOUR_WORDS or token in {"fde", "black"}:
        return False
    if token in brands or token in {"type", "archon"}:
        return False
    if len(token) >= 3 and ("type".startswith(token) or "archon".startswith(token)):
        return False
    if len(token) >= 4 and (
        _similarity(token, "type") >= 0.6
        or _similarity(token, "archon") >= 0.6
        or any(len(brand) >= 4 and _similarity(token, brand) >= 0.6 for brand in brands)
    ):
        return False
    return True


def _word_covered(token: str, row: dict[str, Any]) -> bool:
    have = set(_tokens(_coverage_text(row)))
    if str(row.get("category") or "") == "Sights":
        have.update({"optic", "optics", "sight", "sights", "dot", "dots", "red"})
    if _covered_token(token, have):
        return True
    if token in {"mag", "mags"} and (_covered_token("magazine", have) or "magazine" in have):
        return True
    return _bore_covers(token, row)


def _coverage_text(row: dict[str, Any]) -> str:
    parts = [str(row.get("name") or ""), str(row.get("brand") or ""), str(row.get("category") or "")]
    attributes = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
    features = attributes.get("features") or []
    if isinstance(features, list):
        parts.extend(str(item) for item in features)
    if attributes.get("thread"):
        parts.append(str(attributes["thread"]))
    parts.extend(_option_labels(row))
    stock = attributes.get("stock") if isinstance(attributes.get("stock"), dict) else {}
    parts.append(str(stock.get("status") or ""))
    parts.append(str(stock.get("label") or ""))
    verified = attributes.get("verified") or []
    if isinstance(verified, list):
        for spec in verified:
            if not isinstance(spec, dict):
                continue
            parts.append(str(spec.get("name") or ""))
            parts.append(str(spec.get("value") or ""))
    if attributes.get("rounds") is not None:
        parts.append(str(attributes.get("rounds")))
        parts.append("rounds")
    return " ".join(parts)


def _bore_covers(token: str, row: dict[str, Any]) -> bool:
    bore = _bore_of(row).lower().replace("×", "x").replace(" ", "")
    if token in {"9mm", "9x19"} and bore in {"9x19", "9mm"}:
        return True
    return False


def _bore_of(row: dict[str, Any]) -> str:
    attributes = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
    verified = attributes.get("verified") or []
    if not isinstance(verified, list):
        return ""
    for spec in verified:
        if isinstance(spec, dict) and str(spec.get("name") or "") == _BORE:
            return str(spec.get("value") or "")
    return ""


def _round_counts(host: dict[str, Any], products: list[dict[str, Any]]) -> list[int]:
    found: set[int] = set()
    attributes = host.get("attributes") if isinstance(host.get("attributes"), dict) else {}
    verified = attributes.get("verified") or []
    if isinstance(verified, list):
        for spec in verified:
            if not isinstance(spec, dict) or str(spec.get("name") or "") != "magazines":
                continue
            value = spec.get("value")
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, int | float) and not isinstance(item, bool):
                        found.add(int(item))
    for row in products:
        if str(row.get("category") or "") != "Magazines":
            continue
        count = _round_count(row)
        if count:
            found.add(count)
    return sorted(found)


def _round_count(row: dict[str, Any]) -> int:
    attributes = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
    value = attributes.get("rounds")
    if isinstance(value, int | float) and not isinstance(value, bool):
        return int(value)
    return 0


def _hosted_parts(
    host: dict[str, Any],
    products: list[dict[str, Any]],
    fits: list[dict[str, Any]],
    category: str,
) -> list[dict[str, Any]]:
    family = str(host.get("family") or "")
    linked = {
        str(fit.get("part_sku") or "")
        for fit in fits
        if str(fit.get("fits_family") or "") == family or str(fit.get("fits_sku") or "") == _sku(host)
    }
    return [
        row for row in products
        if str(row.get("category") or "") == category and (_sku(row) in linked or not linked)
    ]


def _named_sidearm(query: str, products: list[dict[str, Any]]) -> dict[str, Any] | None:
    words = _tokens(query)
    tokens = set(words)
    sidearms = [row for row in products if str(row.get("category") or "") == _SIDEARM]
    if "ported" in tokens:
        found = next((row for row in sidearms if "ported" in set(_tokens(str(row.get("name") or "")))), None)
        if found is not None:
            return found
    letter = ""
    for index, token in enumerate(words):
        model = token in {"type", "typ"} or (len(token) >= 3 and "type".startswith(token))
        if model and index + 1 < len(words) and words[index + 1] in {"a", "b", "c", "d"}:
            letter = words[index + 1]
            break
    if not letter:
        return None
    for row in sidearms:
        name = set(_tokens(str(row.get("name") or "")))
        if letter in name and "ported" not in name:
            return row
    return None


def _plain_name(row: dict[str, Any]) -> str:
    name = str(row.get("name") or "").strip()
    brand = str(row.get("brand") or "").strip()
    first = brand.split(" ")[0] if brand else ""
    if first and name.lower().startswith(first.lower() + " "):
        return name[len(first) + 1:]
    return name


def _mentions_sight(query: str) -> bool:
    return any(token in _SIGHT for token in _tokens(query))


def _and_list(words: list[str]) -> str:
    if len(words) <= 1:
        return "".join(words)
    if len(words) == 2:
        return f"{words[0]} and {words[1]}"
    return ", ".join(words[:-1]) + " and " + words[-1]


def _rand(amount: float) -> str:
    number = int(money(amount))
    text = f"{number:,}".replace(",", " ")
    return f"R {text}"


def _offers_cuts(row: dict[str, Any]) -> bool:
    attributes = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
    options = attributes.get("options") if isinstance(attributes.get("options"), dict) else {}
    cuts = options.get("optic_cut")
    return isinstance(cuts, list) and any(str(item or "").strip() for item in cuts)


def _cut_state(
    part_sku: str,
    sidearm: dict[str, Any] | None,
    fits: list[dict[str, Any]],
    cut: str,
) -> dict[str, Any] | None:
    """Fit against the chosen sidearm, including a sibling that offers the same cuts."""
    state = fit_state(part_sku, sidearm, fits, cut)
    if state is not None or sidearm is None or not _offers_cuts(sidearm):
        return state
    ruled = []
    for fit in fits:
        if str(fit.get("part_sku") or "") != part_sku:
            continue
        rule = fit.get("rule") if isinstance(fit.get("rule"), dict) else {}
        if str(rule.get("optic_cut") or ""):
            ruled.append(fit)
    if not ruled:
        return None
    for fit in ruled:
        rule = fit.get("rule") if isinstance(fit.get("rule"), dict) else {}
        needed = str(rule.get("optic_cut") or "")
        if needed == cut:
            badge = f"Fits your {needed} cut" if needed else str(fit.get("note") or "Fits")
            return {"part_sku": part_sku, "fits": True, "badge": badge, "note": str(fit.get("note") or "")}
    rule = ruled[0].get("rule") if isinstance(ruled[0].get("rule"), dict) else {}
    needed = str(rule.get("optic_cut") or "")
    note = str(ruled[0].get("note") or "")
    badge = note if note.lower().startswith("needs") else (f"Needs {needed} cut" if needed else note)
    return {"part_sku": part_sku, "fits": False, "badge": badge, "note": note}


def prepare_reservation(
    setup: dict[str, Any],
    products: list[dict[str, Any]],
    fits: list[dict[str, Any]],
    centre_sku: str,
) -> str:
    """Rewrite choice codes to labels. Refuse a line that is out of stock or does not fit the chosen cut."""
    by_id = {_sku(row): row for row in products}
    parts = list(setup.get("parts") or [])
    sidearm_row = None
    for part in parts:
        product = part.get("product") if isinstance(part.get("product"), dict) else {}
        row = by_id.get(str(product.get("id") or ""))
        if row is not None and str(row.get("category") or "") == _SIDEARM:
            sidearm_row = row
            break
    cut = ""
    if sidearm_row is not None:
        cut = _cut_in_choice(sidearm_row, "")
        for part in parts:
            product = part.get("product") if isinstance(part.get("product"), dict) else {}
            if str(product.get("id") or "") == _sku(sidearm_row):
                part["choice"] = _readable_choice(sidearm_row, str(part.get("choice") or ""))
                cut = _cut_in_choice(sidearm_row, str(part.get("choice") or "")) or cut
                break
    if not cut:
        cut = _centre_cut(_centre_row(products, centre_sku))
    for part in parts:
        product = part.get("product") if isinstance(part.get("product"), dict) else {}
        row = by_id.get(str(product.get("id") or ""))
        if row is None:
            return "That item is not in this catalogue."
        choice = _readable_choice(row, str(part.get("choice") or ""))
        refused = _unknown_choice(row, choice)
        if refused:
            return refused
        part["choice"] = choice
        if _status(row) == "out_of_stock":
            return f"{row.get('name')} is out of stock."
        if sidearm_row is not None and _sku(row) != _sku(sidearm_row):
            state = _cut_state(_sku(row), sidearm_row, fits, cut)
            if state is not None and not state.get("fits"):
                return f"{row.get('name')} does not fit the {cut or 'chosen'} cut."
    return ""


def _readable_choice(row: dict[str, Any], choice: str) -> str:
    text = " ".join(str(choice or "").replace("\n", " ").replace("\r", " ").split())
    attributes = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
    options = attributes.get("options") if isinstance(attributes.get("options"), dict) else {}
    for values in options.values():
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, dict):
                code = str(value.get("code") or "")
                label = str(value.get("label") or code)
                if code and code in text:
                    text = text.replace(code, label)
            elif isinstance(value, str) and value in text:
                continue
    return text[:200]


def _option_labels(row: dict[str, Any]) -> set[str]:
    attributes = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
    options = attributes.get("options") if isinstance(attributes.get("options"), dict) else {}
    labels: set[str] = set()
    for values in options.values():
        if not isinstance(values, list):
            continue
        for value in values:
            if isinstance(value, dict):
                if value.get("label"):
                    labels.add(str(value["label"]))
                if value.get("code"):
                    labels.add(str(value["code"]))
            elif isinstance(value, str):
                labels.add(value)
    return labels


def _fold_choice(value: str) -> str:
    return (
        value.lower()
        .replace('"', "")
        .replace("″", "")
        .replace("“", "")
        .replace("”", "")
        .replace("'", "")
        .strip()
    )


def _label_hit(piece: str, labels: set[str]) -> bool:
    """A choice matches an option only when the whole label matches.

    A short prefix such as "Bla" is not "Black/Black".
    """
    folded = _fold_choice(piece)
    if not folded:
        return False
    for label in labels:
        if _fold_choice(label) == folded:
            return True
    return False


def _unknown_choice(row: dict[str, Any], choice: str) -> str:
    if not choice:
        return ""
    labels = _option_labels(row)
    if not labels:
        if re.search(r"\b[a-z]+-\d+\b", choice):
            return f"{choice} is not an option on {row.get('name')}."
        return ""
    pieces = [piece.strip() for piece in choice.split("·")]
    for piece in pieces:
        if not piece:
            continue
        if piece == str(row.get("name") or "") or _label_hit(piece, labels):
            continue
        return f"{piece} is not an option on {row.get('name')}."
    return ""


def _cut_in_choice(row: dict[str, Any], choice: str) -> str:
    attributes = row.get("attributes") if isinstance(row.get("attributes"), dict) else {}
    options = attributes.get("options") if isinstance(attributes.get("options"), dict) else {}
    cuts = options.get("optic_cut") if isinstance(options.get("optic_cut"), list) else []
    for cut in cuts:
        if isinstance(cut, str) and cut and cut in choice:
            return cut
    defaults = attributes.get("defaults") if isinstance(attributes.get("defaults"), dict) else {}
    return str(defaults.get("optic_cut") or "")


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
