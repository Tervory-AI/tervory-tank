"""Label families group a rule, a truth, and a month. Spot checks follow the family."""
from __future__ import annotations

import importlib.util
import json
import secrets
import sys
import uuid
from pathlib import Path
from zipfile import ZipFile

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import gold  # noqa: E402
from agents.zenas.gold_sources import case_candidate, statute_candidate  # noqa: E402
from test_zenas_gold_sources import case, section  # noqa: E402


def _room(path: Path) -> None:
    text = str(path)
    if text not in sys.path:
        sys.path.insert(0, text)


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_nine_of_ten_agreements_release_the_family():
    """#184 releases a family once 9 of its 10 spot checks agree."""
    assert gold.source_verdict(["checked"] * 9 + ["rejected"]) == "passed"
    assert gold.source_verdict(["checked"] * 10) == "passed"
    assert gold.source_verdict(["checked"] * 8 + ["rejected", "rejected"]) == "review"
    assert gold.source_verdict(["checked"] * 9 + ["candidate"]) == "pending"


def test_zenas_months_are_separate_families_and_holdout_stays_untrained():
    september = case_candidate(dict(case(), as_at="2026-09-30", doc_date="2024-01-01"), "us-east")
    october = case_candidate(dict(case(), as_at="2026-10-01", doc_date="2024-01-01"), "us-east")
    assert september["label_family"] == "converted:courtlistener:2026-09"
    assert october["label_family"] == "converted:courtlistener:2026-10"
    held = case_candidate(dict(case(holdout=True), as_at="2026-10-02"), "us-east")
    assert held["holdout"] is True
    assert held["label_family"] == october["label_family"]
    assert held["label_source"].startswith("held_out:")
    planted = case_candidate(dict(case(), synthetic=True), "us-east")
    assert planted["label_family"] == "converted-synthetic:courtlistener:2026-10"
    undated = dict(case())
    undated.pop("as_at")
    assert case_candidate(undated, "us-east") is None

    early = statute_candidate(dict(section(), known_from="2026-08-01"), "us-east")
    later = statute_candidate(dict(section(), known_from="2026-11-01", effective_from="2020-01-01"), "us-east")
    assert early["label_family"] == "statute_section:govinfo-uscode:2026-08"
    assert later["label_family"] == "statute_section:govinfo-uscode:2026-11"
    za = case_candidate(dict(case("za"), as_at="2026-09-01"), "za")
    assert za["label_family"] == "converted:saflii:2026-09"


def test_radix_family_is_per_skill_and_ignores_month(tmp_path, monkeypatch):
    _room(ROOT / "agents" / "radix")
    gold_sources = _load("radix_label_families", ROOT / "agents" / "radix" / "gold_sources.py")
    monkeypatch.setattr(gold_sources, "FIXTURES", tmp_path)
    monkeypatch.setattr(gold_sources, "SKILLS", ("scan.secrets",))
    monkeypatch.setenv("TANK_REGION", "us-east")
    (tmp_path / "scan.secrets.json").write_text(json.dumps([
        {"name": "january", "observed_on": "2026-01-04", "input": {"files": [{"path": "a.py", "text": "print(1)\n"}]}, "expected": {"critical": 0}},
        {"name": "february", "observed_on": "2026-02-04", "synthetic": True, "input": {"files": [{"path": "b.py", "text": "print(2)\n"}]}, "expected": {"critical": 0}},
    ]), encoding="utf-8")
    rows = gold_sources.candidates()
    assert [row["label_family"] for row in rows] == [
        "radix:fixture:v1:scan.secrets",
        "radix-synthetic:fixture:v1:scan.secrets",
    ]
    assert all("2026-0" not in row["label_family"] for row in rows)


def test_tiger_structured_matches_split_by_month(tmp_path):
    tiger = _load("tiger_label_families", ROOT / "agents" / "tiger" / "gold_sources.py")
    agree = '<p>$9.00</p><script type="application/ld+json">{"@type":"Product","offers":{"price":"9.00","datePublished":"2026-03-04"}}</script>'
    quiet = "<p>$9.00</p><p>$8.00</p>"
    pages = [
        ("jan", "2026-01-15", agree, "9.00"),
        ("feb", "2026-02-15", agree, "9.00"),
        ("sealed", None, agree, "9.00"),
        ("undated", None, '<p>$9.00</p><script type="application/ld+json">{"@type":"Product","offers":{"price":"9.00"}}</script>', "9.00"),
        ("plain", "2026-04-01", quiet, "9.00"),
    ]
    bundle = tmp_path / "pages.zip"
    manifest = []
    with ZipFile(bundle, "w") as archive:
        for name, observed, html, price in pages:
            row = {
                "id": name, "url": "https://example.test/" + name, "split": "build",
                "conflict": False, "unreadable": False, "expected_price": price, "currency": "USD",
            }
            if observed:
                row["observed_on"] = observed
            manifest.append(row)
            archive.writestr(name + ".html", html)
            archive.writestr(name + ".png", b"\x89PNG\r\n\x1a\n")
        archive.writestr("manifest.json", json.dumps(manifest))
    rows = tiger.candidates(limit=20, corpus=bundle)
    families = {row["input"]["url"].rsplit("/", 1)[-1]: row["label_family"] for row in rows}
    assert families["jan"] == "jsonld-match:2026-01"
    assert families["feb"] == "jsonld-match:2026-02"
    assert families["sealed"] == "jsonld-match:2026-03"
    assert families["undated"] == "jsonld-match:2026-10"
    assert families["plain"] == "auto:price-gold-109"
    assert len({row["label_family"] for row in rows}) == 5
    planted = dict(manifest[0], id="planted", synthetic=True, observed_on="2026-01-15")
    assert "synthetic" in tiger._family(planted, agree, True)


def test_rig_families_follow_the_approved_database_content():
    import asyncio
    from test_rig_gold import candidates, uploaded
    from rigbox.store import MemoryStore
    async def check():
        store = MemoryStore()
        tenant = str(uuid.uuid4())
        await uploaded(store, tenant)
        rows = await candidates(store, tenant)
        assert rows[0]['label_family'] == rows[1]['label_family']
        assert rows == await candidates(store, tenant)
        await store.upsert_fit(tenant, dict(part_sku='PART-1', fits_sku='BASE-1', rule={'mount': 'new'}, approved=True))
        assert rows[0]['label_family'] != (await candidates(store, tenant))[0]['label_family']
    asyncio.run(check())


def test_tisan_approval_months_are_separate_families(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.setenv("TANK_KEY", "room-key")
    gold_sources = _load("tisan_label_families", ROOT / "agents" / "tisan" / "gold_sources.py")
    assert gold_sources.page_family("2026-09-30T00:00:00+00:00") == "founder-approved-page:2026-09"
    assert gold_sources.page_family("2026-10-01") == "founder-approved-page:2026-10"
    assert gold_sources.page_family("2026-10-01", synthetic=True) == "founder-approved-page-synthetic:2026-10"
    assert gold_sources.page_family(None) is None
    tenant = gold_sources.PLATFORM_TENANT
    frame = {"node": {"id": "2:11"}, "text": "Example", "visual": [
        {"frameId": f"2:{width}", "width": width, "height": 900, "tokens": {"ink": "#001840"},
         "elements": [{"nodeId": "2:12", "text": "Example", "box": {"x": 1, "y": 2, "width": 3, "height": 4}}]}
        for width in (375, 1440)]}
    page = {"html": "<h1>Example</h1>", "structure": {"nodes": [{"tag": "h1", "text": "Example"}]}}
    approvals = []
    for page_id, approved_at, synthetic in (
        ("september", "2026-09-02T00:00:00+00:00", False),
        ("october", "2026-10-02T00:00:00+00:00", True),
    ):
        (tmp_path / "readings" / tenant).mkdir(parents=True, exist_ok=True)
        (tmp_path / "builds" / tenant).mkdir(parents=True, exist_ok=True)
        (tmp_path / "reviews" / tenant).mkdir(parents=True, exist_ok=True)
        (tmp_path / "readings" / tenant / f"{page_id}.json").write_text(json.dumps(frame), encoding="utf-8")
        (tmp_path / "builds" / tenant / f"{page_id}.json").write_text(json.dumps(page), encoding="utf-8")
        review = {
            "tenant_id": tenant, "region": "us-east", "public": True, "synthetic": synthetic,
            "figma_file_id": "f" * 22, "figma_frame_id": "2:11",
            "frame_path": f"{page_id}.json", "built_page_path": f"{page_id}.json",
        }
        (tmp_path / "reviews" / tenant / f"{page_id}.json").write_text(json.dumps(review), encoding="utf-8")
        saved = gold_sources.snapshot(tmp_path, tenant, page_id)
        approvals.append({
            "tenant_id": uuid.UUID(tenant), "page_id": page_id, "approved_at": approved_at,
            "figma_file_id": saved["figma_file_id"], "figma_frame_id": saved["figma_frame_id"],
            "frame_hash": saved["frame_hash"], "built_page_path": saved["built_page_path"],
            "page_hash": saved["page_hash"],
        })

    class Pool:
        def acquire(self):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def execute(self, *args):
            return None

        async def fetch(self, sql, owner):
            assert "tenant_id=$1" in sql
            return [row for row in approvals if row["tenant_id"] == owner]

    app = FastAPI()
    app.state.pool = Pool()
    gold_sources.mount(app)
    client = TestClient(app)
    rows = client.get("/gold/candidates", headers={"X-Tank-Key": "room-key"}).json()
    assert {row["label_family"] for row in rows} == {
        "founder-approved-page:2026-09",
        "founder-approved-page-synthetic:2026-10",
    }
    assert len(rows) == 4
    assert client.get("/gold/candidates", headers={"X-Tank-Key": "other-room"}).status_code == 401


PLATFORM = "00000000-0000-0000-0000-000000000001"
OTHER_TENANT = "11111111-1111-4111-8111-111111111111"


def _series(tenant: str = PLATFORM, source: str = "public-prices", ref: str = "east", engine: str = "ffl") -> dict:
    return {
        "id": f"{tenant}:{source}:{ref}",
        "tenant_id": tenant,
        "source": source,
        "ref": ref,
        "unit": "index",
        "engine": engine,
    }


def _stored(series_id: str, rows: list[dict]) -> list[dict]:
    return [
        {
            "series_id": series_id,
            "date": row["date"],
            "value": row["value"],
            "fetched_at": row.get("fetched_at") or f"{row['date']}T00:00:00+00:00",
        }
        for row in rows
    ]


def _spike() -> list[dict]:
    """Six flat months, a jump the live rule calls a surge, then a fall."""
    rows = [{"date": f"2025-{month:02d}-01", "value": 10} for month in range(1, 7)]
    rows.append({"date": "2025-07-01", "value": 40})
    rows.append({"date": "2025-07-15", "value": 8})
    rows.append({"date": "2025-08-15", "value": 8})
    rows.append({"date": "2025-08-20", "value": 9})
    return rows


def test_market_lab_labels_the_later_move_not_the_live_rule():
    _room(ROOT / "agents" / "market_lab")
    from core.pure import series_fetch, shift_detect, surge_detect

    lab = _load("market_lab_label_families", ROOT / "agents" / "market_lab" / "gold_sources.py")
    assert lab.WINDOW_DAYS == 28
    assert lab.PCT_THRESHOLD == 0.25
    assert "public-feeds.jsonl" not in (ROOT / "agents" / "market_lab" / "gold_sources.py").read_text(encoding="utf-8")
    assert "agent_market_lab.series" in lab.SERIES_SQL
    assert "agent_market_lab.points" in lab.POINTS_SQL
    assert "agent_market_lab.predictions" in lab.PREDICTIONS_SQL
    assert "tenant_id = $1" in lab.SERIES_SQL

    too_soon = [{"date": "2025-01-01", "value": 10}, {"date": "2025-01-28", "value": 1}]
    early = _series()
    assert [row["skill_id"] for row in lab.candidates([early], _stored(early["id"], too_soon), region="us-east")] == [
        "market.series_fetch", "market.series_fetch",
    ]
    opened_points = [{"date": "2025-02-01", "value": 10}, {"date": "2025-03-01", "value": 10}]
    opened = lab.candidates([early], _stored(early["id"], opened_points), region="us-east")
    assert {row["skill_id"] for row in opened} == {"market.surge_detect", "market.shift_detect", "market.series_fetch"}
    assert {row["label_family"] for row in opened if row["skill_id"] == "market.surge_detect"} == {
        "later-value:public-prices:2025-02",
    }
    assert all("2025-03-01" not in row["label_source"] or row["skill_id"] == "market.series_fetch" for row in opened)

    own = _series()
    foreign = _series(tenant=OTHER_TENANT)
    upload = _series(source="upload", ref="notes")
    points = _stored(own["id"], _spike()) + _stored(foreign["id"], _spike()) + _stored(upload["id"], _spike())
    prediction = {
        "id": "11111111-1111-4111-8111-111111111112",
        "tenant_id": PLATFORM,
        "made_at": "2025-07-01T00:00:00+00:00",
        "metric_series_id": own["id"],
        "comparator": "gt",
        "target": 30,
        "resolve_by": "2025-08-01T00:00:00+00:00",
        "outcome": "hit",
    }
    labelled = lab.candidates([foreign, upload, own], points, [prediction], region="us-east")
    surge = [row for row in labelled if row["skill_id"] == "market.surge_detect"]
    shift = [row for row in labelled if row["skill_id"] == "market.shift_detect"]
    assert surge
    assert all(OTHER_TENANT not in row["label_source"] and "upload" not in row["label_family"] for row in labelled)
    assert {row["label_family"] for row in surge} >= {
        "later-value:public-prices:2025-01", "later-value:public-prices:2025-07",
    }
    assert all("2025-08" not in row["label_family"] for row in surge + shift)
    assert all("2025-08-20" not in row["label_source"] for row in surge + shift)
    july = next(row for row in surge if row["label_source"].endswith("2025-07-01"))
    live = surge_detect({"points": july["input"]["points"]})
    assert any(event["kind"] == "surge" and event["date"] == "2025-07-01" for event in live["events"])
    assert july["expected"]["outcome"] == "no surge"
    assert july["expected"]["prediction_agrees"] is False
    assert all(point["date"] <= "2025-07-01" for point in july["input"]["points"])
    july_shift = next(row for row in shift if row["label_source"].endswith("2025-07-01"))
    assert shift_detect({"areas": july_shift["input"]["areas"]})["events"][0]["kind"] == "bottleneck"
    assert july_shift["expected"]["outcome"] == "saturating"
    fetched = next(row for row in labelled if row["skill_id"] == "market.series_fetch" and row["label_source"].endswith("2025-07-01"))
    assert fetched["label_family"] == "official-match:public-prices:2025-07"
    assert fetched["expected"] == series_fetch(fetched["input"])
    planted = _series(engine="synthetic")
    synthetic_rows = lab.candidates([planted], _stored(planted["id"], opened_points), region="us-east")
    assert synthetic_rows
    assert all("synthetic" in row["label_family"] for row in synthetic_rows)


class _GoldConn:
    def __init__(self, series: list[dict], points: list[dict], predictions: list[dict]) -> None:
        self.series = series
        self.points = points
        self.predictions = predictions
        self.queries: list[tuple[str, tuple]] = []

    async def fetch(self, sql: str, *args: object) -> list[dict]:
        self.queries.append((sql, args))
        tenant = str(args[0])
        if "agent_market_lab.predictions" in sql:
            return [row for row in self.predictions if str(row["tenant_id"]) == tenant]
        if "agent_market_lab.points" in sql:
            owned = {row["id"] for row in self.series if str(row["tenant_id"]) == tenant}
            return [row for row in self.points if row["series_id"] in owned]
        if "agent_market_lab.series" in sql:
            return [row for row in self.series if str(row["tenant_id"]) == tenant]
        raise AssertionError(sql)

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_market_lab_rejects_a_wrong_room_key(monkeypatch):
    _room(ROOT / "agents" / "_chassis")
    _room(ROOT / "agents" / "market_lab")
    lab = _load("market_lab_label_route", ROOT / "agents" / "market_lab" / "gold_sources.py")
    monkeypatch.setenv("TANK_REGION", "us-east")
    key = secrets.token_hex(24)
    monkeypatch.setenv("TANK_KEY", key)
    own = _series()
    foreign = _series(tenant=OTHER_TENANT)
    conn = _GoldConn(
        [own, foreign],
        _stored(own["id"], [{"date": "2025-09-01", "value": 3}, {"date": "2025-10-01", "value": 3}])
        + _stored(foreign["id"], [{"date": "2025-09-01", "value": 99}, {"date": "2025-10-01", "value": 99}]),
        [],
    )
    available = {"database": True}

    async def connect() -> _GoldConn:
        if not available["database"]:
            raise OSError("database unavailable")
        return conn

    monkeypatch.setattr(lab, "_connect", connect)
    monkeypatch.setitem(sys.modules, "gold_sources", lab)
    app = _load("market_lab_label_app", ROOT / "agents" / "market_lab" / "app.py").app
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/gold/candidates")).status_code == 401
        assert (await client.get("/gold/candidates", headers={"X-Tank-Key": "other-room-key"})).status_code == 401
        assert (await client.get("/gold/candidates", headers={"X-Tank-Key": "workspace-key"})).status_code == 401
        assert conn.queries == []
        response = await client.get("/gold/candidates?limit=5", headers={"X-Tank-Key": key})
        assert response.status_code == 200
        body = response.json()
        assert body and body[0]["label_family"] == "later-value:public-prices:2025-09"
        assert body[0]["expected"]["outcome"] == "no surge"
        assert body[0]["public"] is True and body[0]["region"] == "us-east"
        assert all("99" not in json.dumps(row) for row in body)
        assert conn.queries and all(str(args[0]) == PLATFORM for _sql, args in conn.queries)
        for limit in ("0", "-1", "201", "no"):
            assert (await client.get("/gold/candidates?limit=" + limit, headers={"X-Tank-Key": key})).status_code == 422
        available["database"] = False
        assert (await client.get("/gold/candidates", headers={"X-Tank-Key": key})).status_code == 503
        monkeypatch.delenv("TANK_KEY")
        assert (await client.get("/gold/candidates", headers={"X-Tank-Key": key})).status_code == 401


def test_market_lab_image_copies_the_gold_module():
    text = (ROOT / "agents" / "market_lab" / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY market_lab/gold_sources.py /app/gold_sources.py" in text


def test_training_room_list_already_includes_market_lab():
    import training
    assert "market_lab" in training.ROOMS
