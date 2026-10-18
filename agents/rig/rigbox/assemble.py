"""Place catalogue parts on the mounts named in their model files.

A part with no model file is listed and not drawn. This module does not
invent a mesh, a mount, or a clearance box.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from rigbox.gltf_read import multiply
from rigbox.logic import money

_SLUG = re.compile(r"[^a-z0-9]+")


def role_for(category: str) -> str:
    """The mount role is the category, so a new catalogue does not need new code."""
    slug = _SLUG.sub("-", str(category or "").strip().lower()).strip("-")
    return slug or "part"


def assemble(centre: dict[str, Any], parts: list[dict[str, Any]], assets: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Snap each chosen part to a free mount. Overlap uses clearance boxes from the files only."""
    centre_sku = str(centre.get("sku") or centre.get("id") or "")
    host = assets.get(centre_sku) or {}
    lines: list[dict[str, Any]] = [_line(centre, "host", host, placed=bool(host.get("present")), reason=_host_reason(host))]
    used: set[str] = set()
    boxes: list[list[list[float]]] = []
    host_box = _host_box(host)
    if host_box is not None:
        boxes.append(host_box)
    for part in parts:
        lines.append(_place(part, host, assets.get(str(part.get("sku") or "")) or {}, used, boxes))
    currency = str(centre.get("currency") or "")
    if isinstance(centre.get("price"), dict):
        currency = str(centre["price"].get("currency") or currency)
    total = sum((_amount(line["price"]) for line in lines), Decimal("0"))
    missing = [line["sku"] for line in lines if line["reason"] == "needs a model file"]
    return {
        "product_id": centre_sku,
        "lines": lines,
        "missing": missing,
        "total": {"amount": money(total), "currency": currency, "indicative": True},
        "measured": "not checked",
    }


def _place(
    part: dict[str, Any],
    host: dict[str, Any],
    asset: dict[str, Any],
    used: set[str],
    boxes: list[list[list[float]]],
) -> dict[str, Any]:
    role = role_for(str(part.get("category") or ""))
    if not asset.get("present"):
        return _line(part, role, asset, placed=False, reason="needs a model file")
    if not host.get("present"):
        return _line(part, role, asset, placed=False, reason="The centre has no model file, so this part is not drawn.")
    mount = _free_mount(host, role, used)
    if mount is None:
        return _line(part, role, asset, placed=False, reason="No mount in the model for this part.")
    matrix = _snap(mount, asset.get("attach"))
    clearance = asset.get("clearance_mm") or mount.get("clearance_mm")
    box = _box_at(matrix, clearance, host.get("unit") or "m") if clearance else None
    if box is not None:
        for other in boxes:
            if _overlaps(box, other):
                return _line(part, role, asset, placed=False, reason="It overlaps a part already placed.")
        boxes.append(box)
    used.add(str(mount.get("name") or role))
    line = _line(part, role, asset, placed=True, reason=None)
    line["mount"] = str(mount.get("name") or role)
    line["matrix"] = matrix
    if box is None:
        line["collision"] = "No clearance box in the file, so overlap was not checked."
    else:
        line["collision"] = "checked"
    return line


def _host_reason(host: dict[str, Any]) -> str | None:
    if host.get("present"):
        return None
    return "needs a model file"


def _free_mount(host: dict[str, Any], role: str, used: set[str]) -> dict[str, Any] | None:
    for mount in host.get("mounts") or []:
        if str(mount.get("role") or "") != role:
            continue
        name = str(mount.get("name") or role)
        if name in used:
            continue
        return mount
    return None


def _snap(mount: dict[str, Any], attach: dict[str, Any] | None) -> list[float]:
    matrix = list(mount.get("matrix") or _identity())
    if isinstance(attach, dict) and isinstance(attach.get("matrix"), list):
        matrix = multiply(matrix, _rigid_inverse([float(item) for item in attach["matrix"]]))
    return [round(float(item), 6) for item in matrix]


def _box_at(matrix: list[float], size: Any, unit: str) -> list[list[float]] | None:
    if not isinstance(size, list) or len(size) != 3:
        return None
    try:
        dimensions = [float(item) for item in size]
    except (TypeError, ValueError):
        return None
    if any(item <= 0 for item in dimensions):
        return None
    scale = 1000.0 if unit != "mm" else 1.0
    center = [matrix[12] * scale, matrix[13] * scale, matrix[14] * scale]
    half = [item / 2.0 for item in dimensions]
    return [
        [center[axis] - half[axis] for axis in range(3)],
        [center[axis] + half[axis] for axis in range(3)],
    ]


def _host_box(host: dict[str, Any]) -> list[list[float]] | None:
    if not host.get("present"):
        return None
    return _box_at(_identity(), host.get("clearance_mm"), host.get("unit") or "m")


def _overlaps(left: list[list[float]], right: list[list[float]]) -> bool:
    # Touching faces are not an overlap. The gap is well under a millimetre.
    gap = 0.05
    return all(left[0][axis] < right[1][axis] - gap and right[0][axis] < left[1][axis] - gap for axis in range(3))


def _line(
    product: dict[str, Any],
    role: str,
    asset: dict[str, Any],
    *,
    placed: bool,
    reason: str | None,
) -> dict[str, Any]:
    price = product.get("price")
    if isinstance(price, dict):
        amount = price.get("amount")
        currency = str(price.get("currency") or product.get("currency") or "")
    else:
        amount = price
        currency = str(product.get("currency") or "")
    body: dict[str, Any] = {
        "sku": str(product.get("sku") or product.get("id") or ""),
        "name": str(product.get("name") or ""),
        "role": role,
        "price": {"amount": money(amount or 0), "currency": currency, "indicative": True},
        "placed": placed,
        "file": asset.get("file"),
        "mount": None,
        "reason": reason,
    }
    return body


def _amount(price: dict[str, Any]) -> Decimal:
    return Decimal(str(price.get("amount") or 0))


def _rigid_inverse(matrix: list[float]) -> list[float]:
    inverse = [
        matrix[0], matrix[4], matrix[8], 0.0,
        matrix[1], matrix[5], matrix[9], 0.0,
        matrix[2], matrix[6], matrix[10], 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]
    tx, ty, tz = matrix[12], matrix[13], matrix[14]
    inverse[12] = -(inverse[0] * tx + inverse[4] * ty + inverse[8] * tz)
    inverse[13] = -(inverse[1] * tx + inverse[5] * ty + inverse[9] * tz)
    inverse[14] = -(inverse[2] * tx + inverse[6] * ty + inverse[10] * tz)
    return inverse


def _identity() -> list[float]:
    return [1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 1.0]
