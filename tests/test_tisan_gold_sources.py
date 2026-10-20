"""Founder approval, current content hashes and tenant scoping at the room boundary."""
import importlib.util
import json
import os
from pathlib import Path
import secrets
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tisan_gold", ROOT / "agents/tisan/gold_sources.py")
gold = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gold)
TENANT = gold.PLATFORM_TENANT


class Pool:
    def __init__(self):
        self.rows = []

    def acquire(self):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass

    async def execute(self, sql, *args):
        assert "INSERT INTO agent_tisan.page_approvals" in sql
        fields = ["tenant_id", "page_id", "figma_file_id", "figma_frame_id", "frame_hash", "built_page_path", "page_hash", "approved_by"]
        row = dict(zip(fields, args))
        self.rows = [r for r in self.rows if (r["tenant_id"], r["page_id"]) != (row["tenant_id"], row["page_id"])] + [row]

    async def fetch(self, sql, tenant):
        assert "WHERE tenant_id=$1" in sql
        return [row for row in self.rows if row["tenant_id"] == tenant]


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "founder-user")
    key = secrets.token_hex(24)
    monkeypatch.setenv("TANK_KEY", key)
    frame = tmp_path / "readings" / TENANT / "frame.json"
    page = tmp_path / "builds" / TENANT / "page.json"
    reference = tmp_path / "reviews" / TENANT / "example.json"
    for path in (frame, page, reference):
        path.parent.mkdir(parents=True, exist_ok=True)
    frame.write_text(json.dumps({"node": {"id": "2:11"}, "text": "Example"}))
    page.write_text(json.dumps({"html": "<h1>Example</h1>", "structure": {"nodes": [{"tag": "h1", "text": "Example"}]}}))
    reference.write_text(json.dumps({"tenant_id": TENANT, "region": "us-east", "public": False,
        "figma_file_id": "f" * 22, "figma_frame_id": "2:11", "frame_path": "frame.json", "built_page_path": "page.json"}))
    app = FastAPI()
    app.state.pool = Pool()
    gold.mount(app)
    return TestClient(app), {"X-Tank-Key": key, "X-Tervory-Admin": "founder-user"}, tmp_path


def approve(client, headers):
    page = client.get(f"/gold/pages?tenant_id={TENANT}", headers=headers).json()[0]
    return client.post("/gold/approve", headers=headers, json={k: page[k] for k in ("tenant_id", "page_id", "frame_hash", "page_hash")})


def test_approval_creates_both_candidates_and_preserves_truth(setup):
    client, headers, _ = setup
    assert client.get("/gold/candidates", headers=headers).json() == []
    assert approve(client, headers).status_code == 200
    rows = client.get("/gold/candidates", headers=headers).json()
    assert [r["skill_id"] for r in rows] == ["tisan.figma", "tisan.scaffold"]
    assert rows[0]["input"]["text"] == "Example"
    assert rows[0]["expected"]["nodes"][0]["tag"] == "h1"
    assert rows[0]["public"] is False
    assert set(rows[0]) == {"skill_id", "input", "expected", "label_source", "region", "public"}
    assert "founder-user" not in json.dumps(rows)
    assert len(client.get("/gold/candidates?limit=1", headers=headers).json()) == 1


@pytest.mark.parametrize("folder", ["readings", "builds"])
def test_changed_frame_or_page_drops_out_and_stale_review_cannot_approve(setup, folder):
    client, headers, root = setup
    row = client.get(f"/gold/pages?tenant_id={TENANT}", headers=headers).json()[0]
    assert approve(client, headers).status_code == 200
    path = root / folder / TENANT / ("frame.json" if folder == "readings" else "page.json")
    content = json.loads(path.read_text())
    content["changed"] = True
    path.write_text(json.dumps(content))
    assert client.get("/gold/candidates", headers=headers).json() == []
    assert client.post("/gold/approve", headers=headers, json={k: row[k] for k in ("tenant_id", "page_id", "frame_hash", "page_hash")}).status_code == 409
    assert approve(client, headers).status_code == 200
    assert len(client.get("/gold/candidates", headers=headers).json()) == 2


def test_non_founder_and_wrong_key_cannot_approve(setup):
    client, headers, _ = setup
    row = client.get(f"/gold/pages?tenant_id={TENANT}", headers=headers).json()[0]
    body = {k: row[k] for k in ("tenant_id", "page_id", "frame_hash", "page_hash")}
    for bad in ({}, {**headers, "X-Tervory-Admin": "customer"}, {**headers, "X-Tank-Key": secrets.token_hex(24)}):
        assert client.post("/gold/approve", headers=bad, json=body).status_code in (401, 404)
    assert client.get("/gold/candidates").status_code == 401
    assert client.get("/gold/candidates", headers=headers).json() == []


def test_tenant_region_and_limits(setup, monkeypatch):
    client, headers, _ = setup
    assert approve(client, headers).status_code == 200
    other = str(uuid.uuid4())
    assert client.get(f"/gold/candidates?tenant_id={other}", headers=headers).json() == []
    monkeypatch.setenv("GOLD_AUTO_MAX", "1")
    assert len(client.get("/gold/candidates", headers=headers).json()) == 1
    for limit in (0, -1, 201):
        assert client.get(f"/gold/candidates?limit={limit}", headers=headers).status_code == 422
    monkeypatch.setenv("TANK_REGION", "za")
    assert client.get("/gold/candidates", headers=headers).json() == []


@pytest.mark.asyncio
async def test_schema_additive_and_idempotent():
    url = os.environ.get("POOL_SCHEMA_DATABASE_URL")
    if not url:
        pytest.skip("Postgres test requires CI database")
    import asyncpg
    conn = await asyncpg.connect(url)
    transaction = conn.transaction()
    await transaction.start()
    try:
        await conn.execute("CREATE SCHEMA IF NOT EXISTS agent_tisan")
        await conn.execute(gold.SCHEMA)
        await conn.execute(gold.SCHEMA)
        columns = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_schema='agent_tisan' AND table_name='page_approvals'")
        assert {r["column_name"] for r in columns} >= {"tenant_id", "figma_file_id", "figma_frame_id", "frame_hash", "built_page_path", "page_hash", "approved_by", "approved_at"}
    finally:
        await transaction.rollback()
        await conn.close()


def test_scaffold_review_saves_built_page_without_approval(tmp_path):
    spec = importlib.util.spec_from_file_location("tisan_review", ROOT / "agents/tisan/review_store.py")
    store = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(store)
    project = tmp_path / "project"
    html = project / ".next/server/app/index.html"
    html.parent.mkdir(parents=True)
    html.write_text("<h1>Example</h1><script>doNotInclude()</script>")
    file_id = "f" * 22
    reading = tmp_path / "readings" / TENANT / file_id / "2-11.json"
    reading.parent.mkdir(parents=True)
    reading.write_text('{"node":{"id":"2:11"}}')
    (tmp_path / "builds" / TENANT / "example").mkdir(parents=True)
    store.save(tmp_path, project, TENANT, "example", 1, {"file_key": file_id, "node_id": "2:11"})
    row = gold.snapshot(tmp_path, TENANT, "example-home")
    assert row["page_structure"]["nodes"] == [{"tag": "h1", "attrs": {}, "children": [{"text": "Example"}]}]
    assert row["public"] is False
    assert "approval" not in row
    # A new build replaces this page's review reference, invalidating its old approval.
    old_approval = dict(row)
    html.write_text("<h1>Updated page</h1>")
    store.save(tmp_path, project, TENANT, "example", 2, {"file_key": file_id, "node_id": "2:11"})
    updated = gold.snapshot(tmp_path, TENANT, "example-home")
    assert not gold.matches(updated, old_approval)
    assert len(list((tmp_path / "reviews" / TENANT).glob("*.json"))) == 1


def test_approved_structure_keeps_dom_hierarchy():
    spec = importlib.util.spec_from_file_location("tisan_review_tree", ROOT / "agents/tisan/review_store.py")
    store = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(store)
    parser = store.Structure()
    parser.feed('<main><section><h1>Title</h1><p>Copy</p></section><footer>End</footer></main>')
    main = parser.nodes[0]
    assert [node["tag"] for node in main["children"]] == ["section", "footer"]
    assert [node["tag"] for node in main["children"][0]["children"]] == ["h1", "p"]
