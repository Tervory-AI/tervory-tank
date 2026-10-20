"""Public gold candidates from catalogue compatibility lists.

Each part that has its own compatibility list labels ``rig.search`` and
``rig.fit_suggest``. The list is catalogue data shipped with the room.
Publish keys, shopper mail, and webhooks are not copied.

A folder is emitted only when its publish file marks it ``gold: public``
(or ``catalogue_kind: public``) and names a region this server is running
(``us-east`` or ``za``). A missing marker or a missing or unknown region
skips the folder. A catalogue from the other region is skipped too.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rigbox.catalogue import families_from, load_folder

MAX_CANDIDATES = 200
_REGIONS = {"us-east", "za"}
# A public catalogue with no observed_on is the sealed fixture set. Its family
# month does not follow the clock. A published observed_on, as_of, or updated
# date replaces it, so two months are two families.
SEALED_CATALOGUE_MONTH = "2026-10"


def candidates(limit: int = 200, *, region: str = "us-east", root: Path | None = None) -> list[dict[str, Any]]:
    """Up to ``limit`` candidates, search and fit alternating, stable by catalogue and part."""
    if region not in _REGIONS or limit <= 0:
        return []
    cap = min(limit, MAX_CANDIDATES)
    folder = root or Path(__file__).resolve().parent / "catalogues"
    if not folder.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(item for item in folder.iterdir() if item.is_dir() and not item.name.startswith(".")):
        for search_row, fit_row in _pairs(path, region):
            rows.append(search_row)
            rows.append(fit_row)
            if len(rows) >= cap:
                return rows[:cap]
    return rows[:cap]


def _month(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    text = value.isoformat() if hasattr(value, "isoformat") else str(value).strip()
    if len(text) < 7 or text[4] != "-" or not (text[:4].isdigit() and text[5:7].isdigit()):
        return None
    if not 1 <= int(text[5:7]) <= 12:
        return None
    return text[:7]


def _catalogue_month(publish: dict[str, Any]) -> str:
    for key in ("observed_on", "as_of", "updated"):
        month = _month(publish.get(key))
        if month:
            return month
    return SEALED_CATALOGUE_MONTH


def _family(slug: str, publish: dict[str, Any]) -> str:
    family = f"fitment:{slug}:{_catalogue_month(publish)}"
    if publish.get("synthetic") is True:
        return family.replace(":", "-synthetic:", 1)
    return family


def _marked_public(publish: dict[str, Any]) -> bool:
    """The room marks a non-client catalogue. Anything else is skipped."""
    if "gold" in publish:
        return publish.get("gold") == "public"
    return publish.get("catalogue_kind") == "public"


def _catalogue_region(publish: dict[str, Any]) -> str:
    raw = publish.get("region")
    if not isinstance(raw, str):
        return ""
    region = raw.strip().lower()
    if region not in _REGIONS:
        return ""
    return region


def _pairs(path: Path, region: str) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    try:
        loaded = load_folder(path)
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    publish = loaded.get("publish")
    if not isinstance(publish, dict) or not _marked_public(publish):
        return []
    catalogue_region = _catalogue_region(publish)
    if catalogue_region != region:
        return []
    if loaded["products"]["rejected"] or loaded["fits"]["rejected"] or not loaded["tenant_id"]:
        return []
    products = [row for row in loaded["products"]["rows"] if row.get("active")]
    by_sku = {str(row["sku"]): row for row in products}
    families = families_from(products)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for fit in loaded["fits"]["rows"]:
        labelled = _label_fit(fit, by_sku, families)
        if labelled is None:
            continue
        grouped.setdefault(labelled["part_sku"], []).append(labelled)
    tenant = str(loaded["tenant_id"])
    slim = [_product(row, tenant) for row in products]
    catalogue_fits = [_copy_fit(row) for part in grouped for row in grouped[part]]
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for part in sorted(grouped):
        compatibility = _ordered(grouped[part])
        source = f"{loaded['slug']}:{part}"
        common = {
            "label_source": source,
            "label_family": _family(str(loaded["slug"]), publish),
            "region": catalogue_region,
            "public": True,
        }
        pairs.append(
            (
                {
                    **common,
                    "skill_id": "rig.search",
                    "input": {"q": part, "limit": 1, "tenant_id": tenant, "products": slim},
                    "expected": {"ids": [part]},
                },
                {
                    **common,
                    "skill_id": "rig.fit_suggest",
                    "input": {"part_sku": part, "products": slim, "fits": list(catalogue_fits)},
                    "expected": {"fits": compatibility},
                },
            )
        )
    return pairs


def _label_fit(
    fit: dict[str, Any],
    products: dict[str, dict[str, Any]],
    families: dict[str, list[str]],
) -> dict[str, Any] | None:
    """One supported row from the part's own list. Exact sku or a known family."""
    part = str(fit.get("part_sku") or "")
    fits_sku = fit.get("fits_sku") or None
    fits_family = fit.get("fits_family") or None
    if part not in products:
        return None
    if bool(fits_sku) == bool(fits_family):
        return None
    if fits_sku and str(fits_sku) not in products:
        return None
    if fits_family and str(fits_family) not in families:
        return None
    rule = fit.get("rule") if isinstance(fit.get("rule"), dict) else {}
    return {
        "part_sku": part,
        "fits_sku": str(fits_sku) if fits_sku else None,
        "fits_family": str(fits_family) if fits_family else None,
        "rule": rule,
    }


def _ordered(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Exact product fits first, then the catalogue's known families."""
    seen: set[str] = set()
    exact: list[dict[str, Any]] = []
    family: list[dict[str, Any]] = []
    for row in rows:
        key = json.dumps(row, sort_keys=True, default=str)
        if key in seen:
            continue
        seen.add(key)
        if row.get("fits_sku"):
            exact.append(_copy_fit(row))
        else:
            family.append(_copy_fit(row))
    exact.sort(key=lambda row: str(row.get("fits_sku") or ""))
    family.sort(key=lambda row: str(row.get("fits_family") or ""))
    return exact + family


def _copy_fit(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "part_sku": row["part_sku"],
        "fits_sku": row["fits_sku"],
        "fits_family": row["fits_family"],
        "rule": dict(row["rule"]),
    }


def _product(row: dict[str, Any], tenant_id: str) -> dict[str, Any]:
    return {
        "tenant_id": tenant_id,
        "id": str(row["sku"]),
        "sku": str(row["sku"]),
        "name": str(row.get("name") or ""),
        "brand": str(row.get("brand") or ""),
        "category": str(row.get("category") or ""),
        "price": row.get("price"),
        "currency": str(row.get("currency") or ""),
        "image_url": str(row.get("image_url") or ""),
        "attributes": row.get("attributes") if isinstance(row.get("attributes"), dict) else {},
        "active": True,
        "family": str(row.get("family") or ""),
    }
