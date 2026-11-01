"""Rig gold candidates from each part's compatibility list. No database and no network."""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "rig"))
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))

from rigbox.logic import search  # noqa: E402


def _load_gold():
    path = ROOT / "agents" / "rig" / "gold_sources.py"
    spec = importlib.util.spec_from_file_location("rig_room_gold_sources_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


candidates = _load_gold().candidates

CATALOGUES = ROOT / "tests" / "fixtures" / "rig_catalogues"
KEY = "room-key-for-gold"
FIELDS = {"skill_id", "input", "expected", "label_source", "label_family", "region", "public"}


def _publish_secrets() -> set[str]:
    found: set[str] = set()
    for path in CATALOGUES.glob("*/publish.json"):
        loaded = json.loads(path.read_text(encoding="utf-8"))
        for name in ("email", "webhook"):
            if loaded.get(name):
                found.add(str(loaded[name]))
        for row in loaded.get("keys") or []:
            if row.get("key"):
                found.add(str(row["key"]))
    return found


def _assert_labelled(rows: list[dict], region: str) -> None:
    by_source: dict[str, set[str]] = {}
    for row in rows:
        assert set(row) == FIELDS
        assert row["public"] is True
        assert row["region"] == region
        assert isinstance(row["input"], dict)
        assert isinstance(row["expected"], dict)
        catalogue, part = row["label_source"].split(":", 1)
        assert catalogue
        assert part
        assert row["label_family"] == f"fitment:{catalogue}:2026-10"
        assert catalogue != "customnation"
        assert (CATALOGUES / catalogue).is_dir()
        by_source.setdefault(row["label_source"], set()).add(row["skill_id"])
        if row["skill_id"] == "rig.search":
            assert row["input"]["q"] == part
            assert row["input"]["limit"] == 1
            assert row["expected"] == {"ids": [part]}
            assert search(row["input"])["ids"] == [part]
            assert all(item["tenant_id"] == row["input"]["tenant_id"] for item in row["input"]["products"])
        else:
            assert row["skill_id"] == "rig.fit_suggest"
            assert row["input"]["part_sku"] == part
            assert row["expected"]["fits"]
            assert all(fit["part_sku"] == part for fit in row["expected"]["fits"])
            exact = [fit for fit in row["expected"]["fits"] if fit["fits_sku"]]
            family = [fit for fit in row["expected"]["fits"] if fit["fits_family"]]
            assert row["expected"]["fits"] == exact + family
    assert all(skills == {"rig.search", "rig.fit_suggest"} for skills in by_source.values())


def test_each_part_list_labels_search_and_fit() -> None:
    us = candidates(limit=200, region="us-east", root=CATALOGUES)
    za = candidates(limit=200, region="za", root=CATALOGUES)
    assert us and za
    assert len(us) <= 200 and len(za) <= 200
    secrets = _publish_secrets()
    assert secrets
    blob = json.dumps(us + za)
    for secret in secrets:
        assert secret not in blob
    _assert_labelled(us, "us-east")
    _assert_labelled(za, "za")
    assert {row["label_source"].split(":", 1)[0] for row in us} == {"second"}
    assert {row["label_source"].split(":", 1)[0] for row in za} == {"example"}
    scope = next(row for row in za if row["label_source"] == "example:EXAMPLE-SCOPE-01" and row["skill_id"] == "rig.fit_suggest")
    assert [fit["fits_sku"] for fit in scope["expected"]["fits"]] == ["EXAMPLE-RIFLE-01", "EXAMPLE-RINGS-30"]
    rings = next(row for row in za if row["label_source"] == "example:EXAMPLE-RINGS-30" and row["skill_id"] == "rig.fit_suggest")
    assert rings["expected"]["fits"] == [
        {
            "part_sku": "EXAMPLE-RINGS-30",
            "fits_sku": None,
            "fits_family": "EXAMPLE-PLATFORM",
            "rule": {"rail": "picatinny"},
        }
    ]


def test_customnation_is_absent_and_za_catalogue_stays_off_us_east() -> None:
    """customnation is unmarked client data. example is public ZAR, so only za emits it."""
    example = json.loads((CATALOGUES / "example" / "publish.json").read_text(encoding="utf-8"))
    second = json.loads((CATALOGUES / "second" / "publish.json").read_text(encoding="utf-8"))
    custom = json.loads((CATALOGUES / "customnation" / "publish.json").read_text(encoding="utf-8"))
    assert example["gold"] == "public" and example["region"] == "za"
    assert second["gold"] == "public" and second["region"] == "us-east"
    assert custom.get("gold") != "public"
    assert custom.get("catalogue_kind") != "public"
    us = candidates(limit=200, region="us-east", root=CATALOGUES)
    za = candidates(limit=200, region="za", root=CATALOGUES)
    us_names = {row["label_source"].split(":", 1)[0] for row in us}
    za_names = {row["label_source"].split(":", 1)[0] for row in za}
    assert "customnation" not in us_names
    assert "customnation" not in za_names
    assert "example" not in us_names
    assert us_names == {"second"}
    assert za_names == {"example"}
    assert all(row["region"] == "us-east" for row in us)
    assert all(row["region"] == "za" for row in za)


def _write_catalogue(folder: Path, *, gold: str | None, kind: str | None, region: str | None, currency: str) -> None:
    folder.mkdir()
    publish: dict[str, object] = {"tenant_id": "44444444-4444-4444-8444-444444444444"}
    if gold is not None:
        publish["gold"] = gold
    if kind is not None:
        publish["catalogue_kind"] = kind
    if region is not None:
        publish["region"] = region
    (folder / "publish.json").write_text(json.dumps(publish), encoding="utf-8")
    (folder / "products.csv").write_text(
        "sku,name,brand,category,price,currency,image_url,active\n"
        f"PART-1,Part,Brand,part,10.00,{currency},https://example.com/a.jpg,yes\n"
        f"PART-2,Host,Brand,host,12.00,{currency},https://example.com/b.jpg,yes\n",
        encoding="utf-8",
    )
    (folder / "fits.csv").write_text("part_sku,fits_sku,fits_family\nPART-1,PART-2,\n", encoding="utf-8")


def test_limit_alternates_and_regions_fail_closed(tmp_path: Path) -> None:
    one = candidates(limit=1, region="us-east", root=CATALOGUES)
    assert len(one) == 1
    assert one[0]["skill_id"] == "rig.search"
    assert one[0]["label_source"].startswith("second:")
    two = candidates(limit=2, region="za", root=CATALOGUES)
    assert [row["skill_id"] for row in two] == ["rig.search", "rig.fit_suggest"]
    assert {row["region"] for row in two} == {"za"}
    assert two[0]["label_source"] == two[1]["label_source"]
    assert two[0]["label_source"].startswith("example:")
    assert candidates(limit=5, region="eu-west", root=CATALOGUES) == []
    assert candidates(limit=0, region="us-east", root=CATALOGUES) == []
    assert candidates(limit=5, region="us-east", root=tmp_path) == []
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "products.csv").write_text("sku,name\n,\n", encoding="utf-8")
    (broken / "fits.csv").write_text("part_sku,fits_sku,fits_family\nA,B,\n", encoding="utf-8")
    assert candidates(limit=5, region="us-east", root=tmp_path) == []
    # A valid sheet without the public marker, or without a known region, emits nothing.
    _write_catalogue(tmp_path / "unmarked", gold=None, kind=None, region="us-east", currency="USD")
    _write_catalogue(tmp_path / "client", gold="client", kind="public", region="us-east", currency="USD")
    _write_catalogue(tmp_path / "noregion", gold="public", kind=None, region=None, currency="USD")
    _write_catalogue(tmp_path / "unknownregion", gold="public", kind=None, region="eu-west", currency="USD")
    _write_catalogue(tmp_path / "zaroom", gold="public", kind=None, region="za", currency="ZAR")
    _write_catalogue(tmp_path / "kindonly", gold=None, kind="public", region="us-east", currency="USD")
    us_rows = candidates(limit=20, region="us-east", root=tmp_path)
    za_rows = candidates(limit=20, region="za", root=tmp_path)
    assert {row["label_source"].split(":", 1)[0] for row in us_rows} == {"kindonly"}
    assert {row["label_source"].split(":", 1)[0] for row in za_rows} == {"zaroom"}
    assert all(row["region"] == "za" for row in za_rows)


def _app():
    path = ROOT / "agents" / "rig" / "app.py"
    spec = importlib.util.spec_from_file_location("rig_gold_app", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["rig_gold_app"] = module
    spec.loader.exec_module(module)
    return module


def _call(module, path: str, headers: dict[str, str]) -> tuple[int, bytes]:
    sent: list[dict] = []
    route, _, query = path.partition("?")

    async def receive() -> dict:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict) -> None:
        sent.append(message)

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": route,
        "raw_path": route.encode(),
        "query_string": query.encode(),
        "headers": [[name.lower().encode(), value.encode()] for name, value in headers.items()],
        "client": ("127.0.0.1", 9),
        "server": ("test", 80),
    }

    import asyncio

    asyncio.run(module.app(scope, receive, send))
    body = b"".join(message.get("body", b"") for message in sent if message["type"] == "http.response.body")
    return int(sent[0]["status"]), body


def test_gold_route_accepts_only_the_room_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # Another room's gold_sources is already imported under that name in the full suite.
    foreign = types.ModuleType("gold_sources")

    def wrong(*_args: object, **_kwargs: object) -> list:
        raise AssertionError("wrong gold module")

    foreign.candidates = wrong
    monkeypatch.setitem(sys.modules, "gold_sources", foreign)
    monkeypatch.setenv("TANK_KEY", KEY)
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.setenv("CATALOGUE_DIR", str(CATALOGUES))
    module = _app()
    from http_routes import http_paths

    paths = http_paths(module.app.routes)
    assert "/gold/candidates" in paths
    missing = _call(module, "/gold/candidates?limit=2", {})
    assert missing[0] == 401
    wrong = _call(module, "/gold/candidates?limit=2", {"X-Tank-Key": "other-key"})
    assert wrong[0] == 401
    shopper = _call(module, "/gold/candidates?limit=2", {"X-Rig-Key": KEY})
    assert shopper[0] == 401
    ok = _call(module, "/gold/candidates?limit=2", {"X-Tank-Key": KEY})
    assert ok[0] == 200
    loaded = json.loads(ok[1])
    assert [row["skill_id"] for row in loaded] == ["rig.search", "rig.fit_suggest"]
    assert all(row["public"] is True and row["region"] == "us-east" for row in loaded)
    assert all(row["label_source"].startswith("second:") for row in loaded)
    assert all("customnation" not in row["label_source"] and not row["label_source"].startswith("example:") for row in loaded)
    odd = _call(module, "/gold/candidates?limit=2", {"X-Tank-Key": "clé-🔐"})
    assert odd[0] == 401
    monkeypatch.setenv("TANK_KEY", "")
    module_again = _app()
    assert _call(module_again, "/gold/candidates", {"X-Tank-Key": KEY})[0] == 401


def test_non_ascii_room_key_is_401_not_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TANK_KEY", KEY)
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.setenv("CATALOGUE_DIR", str(CATALOGUES))
    module = _app()
    for presented in ("café", "ключ", "room-key-🔑"):
        status, body = _call(module, "/gold/candidates", {"X-Tank-Key": presented})
        assert status == 401, body
        assert status != 500
