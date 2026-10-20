"""Fit answers from catalogue rows. The model cannot add a part."""

from __future__ import annotations

import json
from typing import Any


def supported_fits(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Exact product fits first, then families the catalogue already names.

    A row is kept only when the part and its target are in the product list.
    ``part_sku`` keeps that part's own list. ``focus_sku`` asks what fits one
    product: an exact row, then a family that product belongs to.
    """
    products = [row for row in _rows(payload.get("products")) if _active(row)]
    known = {_sku(row) for row in products if _sku(row)}
    families: dict[str, list[str]] = {}
    for row in products:
        family = str(row.get("family") or "").strip()
        sku = _sku(row)
        if not family or not sku:
            continue
        members = families.setdefault(family, [])
        if sku not in members:
            members.append(sku)
    part = str(payload.get("part_sku") or "").strip()
    focus = "" if part else str(payload.get("focus_sku") or "").strip()
    seen: set[str] = set()
    exact: list[dict[str, Any]] = []
    family_rows: list[dict[str, Any]] = []
    for raw in _rows(payload.get("fits")):
        labelled = _label(raw, known, families)
        if labelled is None:
            continue
        if part and labelled["part_sku"] != part:
            continue
        if focus:
            if labelled["fits_sku"]:
                if labelled["fits_sku"] != focus:
                    continue
            elif focus not in families.get(labelled["fits_family"] or "", []):
                continue
        key = json.dumps(labelled, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        if labelled["fits_sku"]:
            exact.append(labelled)
        else:
            family_rows.append(labelled)
    exact.sort(key=lambda row: (row["part_sku"], row["fits_sku"] or ""))
    family_rows.sort(key=lambda row: (row["part_sku"], row["fits_family"] or ""))
    return exact + family_rows


def one_sentence(text: str) -> str:
    """The first sentence only. A JSON reply is not an explanation."""
    cleaned = " ".join(str(text or "").split())
    if not cleaned or cleaned[0] in "{[":
        return ""
    for index, char in enumerate(cleaned):
        if char in ".!?":
            return cleaned[: index + 1]
    return cleaned


def _label(
    raw: dict[str, Any],
    known: set[str],
    families: dict[str, list[str]],
) -> dict[str, Any] | None:
    part = str(raw.get("part_sku") or "").strip()
    fits_sku = str(raw.get("fits_sku") or "").strip()
    fits_family = str(raw.get("fits_family") or "").strip()
    if not part or part not in known:
        return None
    if bool(fits_sku) == bool(fits_family):
        return None
    if fits_sku and fits_sku not in known:
        return None
    if fits_family and fits_family not in families:
        return None
    rule = raw.get("rule") if isinstance(raw.get("rule"), dict) else {}
    return {
        "part_sku": part,
        "fits_sku": fits_sku or None,
        "fits_family": fits_family or None,
        "rule": dict(rule),
    }


def _rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def _sku(row: dict[str, Any]) -> str:
    return str(row.get("sku") or row.get("id") or "").strip()


def _active(row: dict[str, Any]) -> bool:
    return bool(row.get("active", True))
