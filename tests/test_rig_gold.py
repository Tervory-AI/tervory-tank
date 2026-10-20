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

CATALOGUES = ROOT / "agents" / "rig" / "catalogues"
KEY = "room-key-for-gold"
FIELDS = {"skill_id", "input", "expected", "label_source", "region", "public"}


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


def test_each_part_list_labels_search_and_fit() -> None:
    rows = candidates(limit=200, region="us-east", root=CATALOGUES)
    assert rows
    assert len(rows) <= 200
    secrets = _publish_secrets()
    assert secrets
    blob = json.dumps(rows)
    for secret in secrets:
        assert secret not in blob
    by_source: dict[str, set[str]] = {}
    for row in rows:
        assert set(row) == FIELDS
        assert row["public"] is True
        assert row["region"] == "us-east"
        assert isinstance(row["input"], dict)
        assert isinstance(row["expected"], dict)
        catalogue, part = row["label_source"].split(":", 1)
        assert catalogue
        assert part
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
    scope = next(row for row in rows if row["label_source"] == "example:EXAMPLE-SCOPE-01" and row["skill_id"] == "rig.fit_suggest")
    assert [fit["fits_sku"] for fit in scope["expected"]["fits"]] == ["EXAMPLE-RIFLE-01", "EXAMPLE-RINGS-30"]
    rings = next(row for row in rows if row["label_source"] == "example:EXAMPLE-RINGS-30" and row["skill_id"] == "rig.fit_suggest")
    assert rings["expected"]["fits"] == [
        {
            "part_sku": "EXAMPLE-RINGS-30",
            "fits_sku": None,
            "fits_family": "EXAMPLE-PLATFORM",
            "rule": {"rail": "picatinny"},
        }
    ]


def test_limit_alternates_and_regions_fail_closed(tmp_path: Path) -> None:
    one = candidates(limit=1, region="us-east", root=CATALOGUES)
    assert len(one) == 1
    assert one[0]["skill_id"] == "rig.search"
    two = candidates(limit=2, region="za", root=CATALOGUES)
    assert [row["skill_id"] for row in two] == ["rig.search", "rig.fit_suggest"]
    assert {row["region"] for row in two} == {"za"}
    assert two[0]["label_source"] == two[1]["label_source"]
    assert candidates(limit=5, region="eu-west", root=CATALOGUES) == []
    assert candidates(limit=0, region="us-east", root=CATALOGUES) == []
    assert candidates(limit=5, region="us-east", root=tmp_path) == []
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "products.csv").write_text("sku,name\n,\n", encoding="utf-8")
    (broken / "fits.csv").write_text("part_sku,fits_sku,fits_family\nA,B,\n", encoding="utf-8")
    assert candidates(limit=5, region="us-east", root=tmp_path) == []


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
    paths = {getattr(route, "path", None) for route in module.app.routes}
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
    assert all(row["public"] is True for row in loaded)
    monkeypatch.setenv("TANK_KEY", "")
    module_again = _app()
    assert _call(module_again, "/gold/candidates", {"X-Tank-Key": KEY})[0] == 401
