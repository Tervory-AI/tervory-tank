"""R5 model loader and R6 build. No database and no network.

A catalogue part with no .glb stays missing. These tests never treat a
synthetic file as a measured product.
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rigbox.assemble import assemble  # noqa: E402
from rigbox.gltf_read import parse_glb  # noqa: E402
from rigbox.models import house_view, inspect_sku, model_file  # noqa: E402
from rigbox.page_route import builder_document  # noqa: E402
from rigbox.service import Service  # noqa: E402
from rigbox.store import MemoryStore  # noqa: E402

CATALOGUE = ROOT / "catalogues" / "customnation"
PAGE = ROOT / "rigbox" / "page"
TENANT = "33333333-3333-4333-8333-333333333333"


def _pack(document: dict, blob: bytes = b"") -> bytes:
    body = json.dumps(document, separators=(",", ":")).encode("utf-8")
    body += b" " * ((4 - len(body) % 4) % 4)
    chunks = struct.pack("<I", len(body)) + b"JSON" + body
    if blob:
        blob += b"\x00" * ((4 - len(blob) % 4) % 4)
        chunks += struct.pack("<II", len(blob), 0x004E4942) + blob
    return struct.pack("<4sII", b"glTF", 2, 12 + len(chunks)) + chunks


def _triangle_glb() -> bytes:
    positions = struct.pack("<9f", 0, 0, 0, 0.1, 0, 0, 0, 0.05, 0)
    indices = struct.pack("<3H", 0, 1, 2)
    blob = positions + indices + b"\x00\x00"
    document = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [
            {"name": "body", "mesh": 0, "children": [1]},
            {
                "name": "mount/optics",
                "translation": [0, 0.1, 0],
                "extras": {"mount": {"role": "optics", "clearance_mm": [40, 30, 20]}},
            },
        ],
        "meshes": [
            {
                "primitives": [
                    {
                        "attributes": {"POSITION": 0},
                        "indices": 1,
                        "material": 0,
                    }
                ]
            }
        ],
        "materials": [
            {
                "name": "steel",
                "pbrMetallicRoughness": {
                    "baseColorFactor": [0.7, 0.7, 0.7, 1],
                    "metallicFactor": 0.8,
                    "roughnessFactor": 0.3,
                },
            }
        ],
        "accessors": [
            {
                "bufferView": 0,
                "componentType": 5126,
                "count": 3,
                "type": "VEC3",
                "min": [0, 0, 0],
                "max": [0.1, 0.05, 0],
            },
            {"bufferView": 1, "componentType": 5123, "count": 3, "type": "SCALAR"},
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": 0, "byteLength": 36},
            {"buffer": 0, "byteOffset": 36, "byteLength": 6},
        ],
        "buffers": [{"byteLength": len(blob)}],
    }
    return _pack(document, blob)


def test_sample_catalogue_has_no_model_files() -> None:
    view = house_view(CATALOGUE)
    skus = [row["id"] for row in view["products"]]
    assert len(skus) == 18
    missing = []
    for sku in skus:
        report = view["assets"][sku]
        assert report["present"] is False
        assert report["reason"] == "needs a model file"
        assert report["mounts"] == []
        assert report["polycount"] is None
        assert report["extent_m"] is None
        assert report["measured"] == "not checked"
        assert model_file(CATALOGUE, sku) is None
        missing.append(sku)
    assert missing == [
        "STI-P-9",
        "STI-C2-9",
        "STI-XC-9",
        "TRIJ-RMR-T2",
        "HOL-507C-X2",
        "DAW-FO-FRONT",
        "TEN8-REAR",
        "CHEELY-E2",
        "CHEELY-C2",
        "ATLAS-FLAT",
        "REDD-TRIGGER",
        "SAF-ALS-FULL",
        "TENICOR-VELO",
        "MAG-17",
        "MAG-20",
        "MAG-16",
        "SF-X300U",
        "SL-TLR1",
    ]
    assert view["measured"] == "not checked"
    assert model_file(CATALOGUE, "../secrets") is None


def test_loader_reads_a_real_glb_and_rejects_a_fake_one(tmp_path: Path) -> None:
    folder = tmp_path / "brand"
    (folder / "models").mkdir(parents=True)
    (folder / "models" / "OPT-1.glb").write_bytes(_triangle_glb())
    (folder / "models" / "BAD.glb").write_bytes(b"not a model")
    good = inspect_sku(folder, "OPT-1")
    assert good["present"] is True
    assert good["polycount"] == 1
    assert good["pbr"] is True
    assert good["materials"][0]["name"] == "steel"
    assert good["mounts"][0]["role"] == "optics"
    assert good["mounts"][0]["translation_m"][1] == pytest.approx(0.1)
    assert good["mounts"][0]["clearance_mm"] == [40, 30, 20]
    assert good["extent_m"]["max"][0] == pytest.approx(0.1)
    assert good["measured"] == "not checked"
    bad = inspect_sku(folder, "BAD")
    assert bad["present"] is False
    assert bad["reason"] == "The file is not a glb."
    assert bad["polycount"] is None
    missing = inspect_sku(folder, "NO-FILE")
    assert missing["reason"] == "needs a model file"
    assert "positions" not in missing


def test_parts_snap_to_mounts_and_overlap_is_refused() -> None:
    host = _product("HOST", "Centre", "Pistols")
    optic = _product("OPT", "Dot", "Optics")
    light = _product("LIGHT", "Lamp", "Lights")
    assets = {
        "HOST": _asset(True, [_mount("optics", 0, 0.1, 0), _mount("lights", 0, 0.1, 0.01)]),
        "OPT": _asset(True, [], clearance=[40, 30, 20]),
        "LIGHT": _asset(True, [], clearance=[40, 30, 20]),
    }
    blocked = assemble(host, [optic, light], assets)
    by_sku = {line["sku"]: line for line in blocked["lines"]}
    assert by_sku["OPT"]["placed"] is True
    assert by_sku["OPT"]["mount"] == "mount/optics"
    assert by_sku["LIGHT"]["placed"] is False
    assert by_sku["LIGHT"]["reason"] == "It overlaps a part already placed."
    assets["HOST"]["mounts"][1] = _mount("lights", 0.2, 0, 0)
    clear = assemble(host, [optic, light], assets)
    placed = {line["sku"]: line for line in clear["lines"]}
    assert placed["LIGHT"]["placed"] is True
    assert placed["LIGHT"]["matrix"][12] == pytest.approx(0.2)
    assert clear["measured"] == "not checked"


def test_a_missing_file_is_not_drawn() -> None:
    host = _product("STI-P-9", "Staccato P", "Pistols")
    optic = _product("TRIJ-RMR-T2", "Trijicon RMR Type 2", "Optics")
    scene = assemble(
        host,
        [optic],
        {
            "STI-P-9": _asset(False, []),
            "TRIJ-RMR-T2": _asset(False, []),
        },
    )
    assert [line["reason"] for line in scene["lines"]] == ["needs a model file", "needs a model file"]
    assert all(line["placed"] is False for line in scene["lines"])
    assert scene["missing"] == ["STI-P-9", "TRIJ-RMR-T2"]
    assert scene["total"]["indicative"] is True
    assert scene["measured"] == "not checked"


def test_builder_page_names_the_sample_and_does_not_invent_a_pass() -> None:
    html = builder_document()
    assert "Staccato P" in html
    assert "Parts that fit" in html
    assert "No model file yet" in html
    assert "needs a model file" in html
    assert "Size against the real product has not been checked." in html
    assert "within 2 mm" not in html
    assert "within 2mm" not in html
    for banned in ("liability", "warranty", "disclaimer", "add-on", "upgrade"):
        assert banned not in html.lower()
    script = (PAGE / "builder.js").read_text(encoding="utf-8")
    assert "needs a model file" in script
    assert "within 2 mm" not in script
    search = (PAGE / "index.html").read_text(encoding="utf-8")
    assert 'id="q"' in search
    assert "Build this" in search
    assert "Example" not in search


@pytest.mark.asyncio
async def test_quote_stores_the_exact_build_and_refuses_a_part_that_does_not_fit(tmp_path: Path) -> None:
    folder = tmp_path / "customnation"
    (folder / "models").mkdir(parents=True)
    (folder / "products.csv").write_text("sku\n", encoding="utf-8")
    (folder / "fits.csv").write_text("part_sku\n", encoding="utf-8")
    (folder / "publish.json").write_text(json.dumps({"tenant_id": TENANT}), encoding="utf-8")
    (folder / "models" / "HOST.glb").write_bytes(_triangle_glb())
    store = MemoryStore()
    await store.upsert_product(TENANT, _product("HOST", "Centre", "Pistols"))
    await store.upsert_product(TENANT, _product("OPT", "Dot", "Optics"))
    await store.upsert_product(TENANT, _product("OTHER", "Other", "Cases"))
    await store.upsert_fit(
        TENANT,
        {"part_sku": "OPT", "fits_sku": "HOST", "fits_family": None, "source": "import", "approved": True, "rule": {}},
    )
    # The triangle file's mount role is optics, which is the Dot's category.
    # Point the loader at this temp folder by matching the tenant id.
    publish = folder / "publish.json"
    assert publish.is_file()
    service = Service(store, catalogue_root=tmp_path)
    scene = await service.scene(TENANT, {"product_id": "HOST", "part_skus": ["OPT", "OTHER"]})
    by_sku = {line["sku"]: line for line in scene["lines"]}
    assert by_sku["HOST"]["placed"] is True
    assert by_sku["HOST"]["reason"] is None
    assert by_sku["OPT"]["placed"] is False
    assert by_sku["OPT"]["reason"] == "needs a model file"
    assert scene["refused"] == [{"sku": "OTHER", "reason": "That part is not listed as fitting this product."}]
    assert scene["measured"] == "not checked"
    stored = await service.quote(
        TENANT,
        {
            "build": {"product_id": "HOST", "part_skus": ["OPT"]},
            "contact": {"name": "Ada", "email": "ada@example.com"},
        },
    )
    assert stored["request_id"].startswith("req_")
    quote = store.quotes[-1]
    assert quote["payload"]["kind"] == "build"
    assert quote["payload"]["build"]["product_id"] == "HOST"
    assert [line["sku"] for line in quote["payload"]["build"]["lines"]] == ["HOST", "OPT"]


def _product(sku: str, name: str, category: str) -> dict:
    return {
        "sku": sku,
        "name": name,
        "brand": "Sample",
        "category": category,
        "price": "100.00",
        "currency": "ZAR",
        "active": True,
        "family": "",
        "attributes": {},
    }


def _asset(present: bool, mounts: list[dict], clearance: list[float] | None = None) -> dict:
    return {
        "present": present,
        "file": "models/file.glb" if present else None,
        "mounts": mounts,
        "clearance_mm": clearance,
        "attach": None,
        "unit": "m",
    }


def _mount(role: str, x: float, y: float, z: float) -> dict:
    matrix = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, x, y, z, 1]
    return {
        "role": role,
        "name": f"mount/{role}",
        "translation_m": [x, y, z],
        "matrix": matrix,
        "clearance_mm": [40, 30, 20],
    }
