"""Model files for one catalogue folder.

A part's file is catalogues/<slug>/models/<sku>.glb. If that file is absent,
the part is reported as needing a model file. No mesh is created in its place.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from rigbox.catalogue import load_folder
from rigbox.gltf_read import parse_glb
from rigbox.logic import fitting_parts, public_product

_SKU = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_MEASURED = "not checked"


def safe_sku(sku: str) -> str:
    text = str(sku or "").strip()
    if _SKU.fullmatch(text) is None:
        return ""
    return text


def model_file(folder: Path, sku: str) -> Path | None:
    """The .glb for this sku, or None. The path cannot leave models/."""
    safe = safe_sku(sku)
    if not safe:
        return None
    root = (folder / "models").resolve()
    path = (root / f"{safe}.glb").resolve()
    if path.parent != root or not path.is_file():
        return None
    return path


def inspect_sku(folder: Path, sku: str) -> dict[str, Any]:
    safe = safe_sku(sku)
    report = _missing(sku, f"models/{safe}.glb" if safe else None)
    path = model_file(folder, sku)
    if path is None:
        return report
    try:
        parsed = parse_glb(path.read_bytes())
    except (OSError, ValueError, UnicodeError):
        report["reason"] = "The file is not a glb."
        report["checks"] = {
            "file": "not a glb",
            "mounts": "none in the file",
            "materials": "none in the file",
            "measured": _MEASURED,
        }
        return report
    present = {
        "sku": sku,
        "present": True,
        "reason": None,
        "file": f"models/{safe}.glb",
        "mounts": parsed["mounts"],
        "materials": parsed["materials"],
        "polycount": parsed["polycount"],
        "extent_m": parsed["extent_m"],
        "clearance_mm": parsed["clearance_mm"],
        "attach": parsed["attach"],
        "pbr": parsed["pbr"],
        "unit": parsed["unit"],
        "measured": _MEASURED,
        "checks": {
            "file": "present",
            "mounts": "present" if parsed["mounts"] else "none in the file",
            "materials": "present" if parsed["materials"] else "none in the file",
            "measured": _MEASURED,
        },
    }
    return present


def folder_for_tenant(root: Path, tenant_id: str) -> Path | None:
    if not root.is_dir():
        return None
    wanted = str(tenant_id)
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        loaded = load_folder(child)
        if str(loaded.get("tenant_id") or "") == wanted:
            return child
    return None


def index_folder(folder: Path) -> list[dict[str, Any]]:
    loaded = load_folder(folder)
    rows = [row for row in loaded["products"]["rows"] if row.get("active", True)]
    return [inspect_sku(folder, str(row.get("sku") or "")) for row in rows]


def house_view(folder: Path) -> dict[str, Any]:
    """The sample catalogue, with a model report for every sku. Safe to embed in the page."""
    loaded = load_folder(folder)
    products = [row for row in loaded["products"]["rows"] if row.get("active", True)]
    fits = [row for row in loaded["fits"]["rows"]]
    assets = {str(row.get("sku") or ""): inspect_sku(folder, str(row.get("sku") or "")) for row in products}
    centres: list[dict[str, Any]] = []
    public_rows: list[dict[str, Any]] = []
    for row in products:
        public = public_product(row)
        public["family"] = str(row.get("family") or "")
        public_rows.append(public)
        if fitting_parts(row, products, fits):
            centres.append(public)
    return {
        "measured": _MEASURED,
        "centres": centres,
        "products": public_rows,
        "fits": [
            {
                "part_sku": str(row.get("part_sku") or ""),
                "fits_sku": row.get("fits_sku") or "",
                "fits_family": row.get("fits_family") or "",
                "rule": row.get("rule") or {},
                "source": str(row.get("source") or "import"),
                "approved": bool(row.get("approved", True)),
            }
            for row in fits
        ],
        "assets": assets,
    }


def _missing(sku: str, file_name: str | None) -> dict[str, Any]:
    return {
        "sku": sku,
        "present": False,
        "reason": "needs a model file",
        "file": file_name,
        "mounts": [],
        "materials": [],
        "polycount": None,
        "extent_m": None,
        "clearance_mm": None,
        "attach": None,
        "pbr": False,
        "unit": "m",
        "measured": _MEASURED,
        "checks": {
            "file": "missing",
            "mounts": "none in the file",
            "materials": "none in the file",
            "measured": _MEASURED,
        },
    }
