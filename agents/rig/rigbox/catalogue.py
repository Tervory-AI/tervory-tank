"""Read a brand's sheets and feeds into the same product and fit rows."""

from __future__ import annotations

import csv
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

_NAMESPACE = UUID("11111111-1111-4111-8111-111111111111")
_REQUIRED = ("sku", "name", "brand", "category", "price", "currency", "image_url", "active")


def tenant_id_for(slug: str, declared: str | None) -> str:
    if declared:
        return str(UUID(str(declared)))
    return str(uuid5(_NAMESPACE, f"rig:{slug}"))


def parse_products_csv(text: str) -> dict[str, Any]:
    return _parse_table(text, _product_row)


def parse_fits_csv(text: str) -> dict[str, Any]:
    return _parse_table(text, _fit_row)


def check_fit_refs(rows: list[dict[str, Any]], skus: set[str], families: set[str]) -> list[dict[str, Any]]:
    rejected: list[dict[str, Any]] = []
    for row in rows:
        if row["part_sku"] not in skus:
            rejected.append({"row": row["row"], "reason": "part_sku is not in this catalogue"})
            continue
        if row.get("fits_sku") and row["fits_sku"] not in skus:
            rejected.append({"row": row["row"], "reason": "fits_sku is not in this catalogue"})
        elif row.get("fits_family") and row["fits_family"] not in families:
            rejected.append({"row": row["row"], "reason": "fits_family is not on any product"})
    return rejected


def families_from(products: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for row in products:
        family = str(row.get("family") or "").strip()
        if not family:
            continue
        grouped.setdefault(family, [])
        sku = str(row.get("sku") or "")
        if sku and sku not in grouped[family]:
            grouped[family].append(sku)
    return {key: sorted(value) for key, value in grouped.items()}


def read_publish(text: str) -> dict[str, Any]:
    try:
        loaded = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("publish file is not JSON") from exc
    if not isinstance(loaded, dict):
        raise ValueError("publish file must be an object")
    return loaded


def map_shopify(body: Any, currency: str) -> dict[str, Any]:
    products = body.get("products") if isinstance(body, dict) else None
    if not isinstance(products, list):
        return {"rows": [], "rejected": [{"row": 0, "reason": "shopify feed has no products list"}]}
    rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, item in enumerate(products, start=1):
        if not isinstance(item, dict):
            rejected.append({"row": index, "reason": "product is not an object"})
            continue
        variants = item.get("variants") if isinstance(item.get("variants"), list) else []
        variant = next((entry for entry in variants if isinstance(entry, dict) and entry.get("sku")), None)
        images = item.get("images") if isinstance(item.get("images"), list) else []
        image = ""
        if images and isinstance(images[0], dict):
            image = str(images[0].get("src") or "")
        sku = str(variant.get("sku") or "") if variant else ""
        price = str(variant.get("price") or "") if variant else ""
        row, reason = _feed_row(
            sku=sku,
            name=str(item.get("title") or ""),
            brand=str(item.get("vendor") or ""),
            category=str(item.get("product_type") or ""),
            price=price,
            currency=currency,
            image_url=image,
            url=str(item.get("handle") or ""),
            gtin=str(variant.get("barcode") or "") if variant else "",
            active=str(item.get("status") or "active").lower() in {"active", "publish", "yes"},
        )
        if reason:
            rejected.append({"row": index, "reason": reason})
        else:
            rows.append(row)
    return {"rows": rows, "rejected": rejected}


def map_woocommerce(body: Any, currency: str) -> dict[str, Any]:
    items = body if isinstance(body, list) else None
    if items is None and isinstance(body, dict):
        items = body.get("products") if isinstance(body.get("products"), list) else None
    if not isinstance(items, list):
        return {"rows": [], "rejected": [{"row": 0, "reason": "woocommerce feed has no products list"}]}
    rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            rejected.append({"row": index, "reason": "product is not an object"})
            continue
        images = item.get("images") if isinstance(item.get("images"), list) else []
        image = str(images[0].get("src") or "") if images and isinstance(images[0], dict) else ""
        categories = item.get("categories") if isinstance(item.get("categories"), list) else []
        category = ""
        if categories and isinstance(categories[0], dict):
            category = str(categories[0].get("name") or "")
        brand = ""
        brands = item.get("brands") if isinstance(item.get("brands"), list) else []
        if brands and isinstance(brands[0], dict):
            brand = str(brands[0].get("name") or "")
        status = str(item.get("status") or "publish").lower()
        row, reason = _feed_row(
            sku=str(item.get("sku") or ""),
            name=str(item.get("name") or ""),
            brand=brand,
            category=category,
            price=str(item.get("price") or item.get("regular_price") or ""),
            currency=currency,
            image_url=image,
            url=str(item.get("permalink") or ""),
            gtin=str(item.get("global_unique_id") or item.get("gtin") or ""),
            active=status in {"publish", "active", "yes"},
        )
        if reason:
            rejected.append({"row": index, "reason": reason})
        else:
            rows.append(row)
    return {"rows": rows, "rejected": rejected}


def map_google_merchant(text: str) -> dict[str, Any]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return {"rows": [], "rejected": [{"row": 0, "reason": "merchant feed is not XML"}]}
    items = [element for element in root.iter() if _local(element.tag) == "item"]
    rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        fields = {_local(child.tag): (child.text or "").strip() for child in list(item)}
        amount, currency = _split_price(fields.get("price") or "")
        available = (fields.get("availability") or "in stock").lower()
        row, reason = _feed_row(
            sku=fields.get("id") or "",
            name=fields.get("title") or "",
            brand=fields.get("brand") or "",
            category=fields.get("product_type") or fields.get("google_product_category") or "",
            price=amount,
            currency=currency,
            image_url=fields.get("image_link") or "",
            url=fields.get("link") or "",
            gtin=fields.get("gtin") or "",
            active=available.startswith("in"),
        )
        if reason:
            rejected.append({"row": index, "reason": reason})
        else:
            rows.append(row)
    if not items:
        rejected.append({"row": 0, "reason": "merchant feed has no items"})
    return {"rows": rows, "rejected": rejected}


def price_patch(update: dict[str, Any]) -> dict[str, Any]:
    """Tiger may change price and availability. Fitment fields are dropped."""
    patched: dict[str, Any] = {}
    if "price" in update and update["price"] is not None and str(update["price"]) != "":
        patched["price"] = _money_text(update["price"])
    if "currency" in update and update["currency"]:
        patched["currency"] = str(update["currency"]).strip().upper()
    if "active" in update and update["active"] is not None:
        patched["active"] = _active_value(update["active"])
    return patched


def load_folder(folder: Path) -> dict[str, Any]:
    publish_path = folder / "publish.json"
    publish: dict[str, Any] = {}
    publish_error = ""
    if publish_path.is_file():
        try:
            publish = read_publish(publish_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            publish_error = str(exc)
    try:
        tenant_id = tenant_id_for(folder.name, str(publish.get("tenant_id") or "") or None)
    except ValueError:
        tenant_id = ""
        publish_error = publish_error or "tenant_id is not a uuid"
    products_path = folder / "products.csv"
    fits_path = folder / "fits.csv"
    products = parse_products_csv(products_path.read_text(encoding="utf-8")) if products_path.is_file() else {
        "rows": [],
        "rejected": [{"row": 0, "reason": "products.csv is missing"}],
    }
    fits = parse_fits_csv(fits_path.read_text(encoding="utf-8")) if fits_path.is_file() else {
        "rows": [],
        "rejected": [],
    }
    return {
        "slug": folder.name,
        "tenant_id": tenant_id,
        "publish": publish,
        "publish_error": publish_error,
        "products": products,
        "fits": fits,
    }


def _parse_table(text: str, reader) -> dict[str, Any]:
    handle = io.StringIO(text)
    try:
        parsed = csv.DictReader(handle)
        fieldnames = list(parsed.fieldnames or [])
    except csv.Error as exc:
        return {"rows": [], "rejected": [{"row": 1, "reason": f"could not read the sheet ({exc})"}]}
    if not fieldnames:
        return {"rows": [], "rejected": [{"row": 1, "reason": "the sheet has no header"}]}
    rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, raw in enumerate(parsed, start=2):
        try:
            rows.append(reader(raw, index))
        except ValueError as exc:
            rejected.append({"row": index, "reason": str(exc)})
    if rejected:
        return {"rows": [], "rejected": rejected}
    return {"rows": rows, "rejected": []}


def _product_row(raw: dict[str, str | None], index: int) -> dict[str, Any]:
    values = {key: (value or "").strip() for key, value in raw.items() if key}
    missing = [name for name in _REQUIRED if not values.get(name)]
    if missing:
        raise ValueError("missing " + ", ".join(missing))
    attributes: dict[str, Any] = {}
    if values.get("attributes"):
        try:
            loaded = json.loads(values["attributes"])
        except json.JSONDecodeError as exc:
            raise ValueError("attributes is not JSON") from exc
        if not isinstance(loaded, dict):
            raise ValueError("attributes must be an object")
        attributes = loaded
    return {
        "row": index,
        "sku": values["sku"],
        "gtin": values.get("gtin") or None,
        "name": values["name"],
        "brand": values["brand"],
        "category": values["category"],
        "price": _money_text(values["price"]),
        "currency": values["currency"].upper(),
        "image_url": values["image_url"],
        "url": values.get("product_url") or values.get("url") or "",
        "family": values.get("family") or "",
        "active": _active_value(values["active"]),
        "attributes": attributes,
    }


def _fit_row(raw: dict[str, str | None], index: int) -> dict[str, Any]:
    values = {key: (value or "").strip() for key, value in raw.items() if key}
    if not values.get("part_sku"):
        raise ValueError("missing part_sku")
    fits_sku = values.get("fits_sku") or ""
    fits_family = values.get("fits_family") or ""
    if bool(fits_sku) == bool(fits_family):
        raise ValueError("set fits_sku or fits_family, not both")
    rule: dict[str, Any] = {}
    if values.get("rule"):
        try:
            loaded = json.loads(values["rule"])
        except json.JSONDecodeError as exc:
            raise ValueError("rule is not JSON") from exc
        if not isinstance(loaded, dict):
            raise ValueError("rule must be an object")
        rule = loaded
    return {
        "row": index,
        "part_sku": values["part_sku"],
        "fits_sku": fits_sku or None,
        "fits_family": fits_family or None,
        "rule": rule,
        "note": values.get("note") or "",
        "source": "import",
        "approved": True,
        "confidence": 1,
    }


def _money_text(value: Any) -> str:
    text = str(value).strip().replace(" ", "")
    if not text:
        raise ValueError("price is missing")
    try:
        number = float(text)
    except ValueError as exc:
        raise ValueError("price is not a number") from exc
    if number < 0:
        raise ValueError("price is negative")
    return f"{number:.2f}"


def _active_value(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"yes", "true", "1", "active"}:
        return True
    if text in {"no", "false", "0", "inactive"}:
        return False
    raise ValueError("active must be yes or no")


def _feed_row(**fields: Any) -> tuple[dict[str, Any] | None, str]:
    try:
        if not fields["sku"] or not fields["name"] or not fields["brand"] or not fields["category"]:
            raise ValueError("missing sku, name, brand, or category")
        if not fields["image_url"]:
            raise ValueError("missing image_url")
        price = _money_text(fields["price"])
        if not fields["currency"]:
            raise ValueError("missing currency")
    except ValueError as exc:
        return None, str(exc)
    return (
        {
            "sku": fields["sku"],
            "gtin": fields.get("gtin") or None,
            "name": fields["name"],
            "brand": fields["brand"],
            "category": fields["category"],
            "price": price,
            "currency": str(fields["currency"]).upper(),
            "image_url": fields["image_url"],
            "url": fields.get("url") or "",
            "family": "",
            "active": bool(fields["active"]),
            "attributes": {},
        },
        "",
    )


def _split_price(value: str) -> tuple[str, str]:
    parts = value.split()
    if len(parts) >= 2:
        return parts[0], parts[1]
    return value, ""


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag
