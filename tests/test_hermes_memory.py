"""C7 Hermes. No database and no network.

Proves one agent cannot read another, one tenant cannot see another,
near-duplicates collapse, and deleting a tenant removes that agent's copy only.
The template heartbeat count is `seen`, and a new client recalls it.
"""

from __future__ import annotations

import asyncio
import importlib.util
import math
import os
import re
import subprocess
import sys
from pathlib import Path

import httpx
import pytest
import yaml
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))
sys.path.insert(0, str(ROOT))

from chassis.memory import MemoryClient  # noqa: E402
from hermes.service import DEDUPE_SCORE, create_app  # noqa: E402
from hermes.store import InMemoryStore  # noqa: E402

TEMPLATE = "template-secret-value"
TIGER = "tiger-secret-value"
WORKSPACE = "workspace-test-key"
TENANT_X = "11111111-1111-1111-1111-111111111111"
TENANT_Y = "22222222-2222-2222-2222-222222222222"


class StubEmbedder:
    """Fixed vectors so the 0.97 line is exact, with no model download."""

    def embed(self, text: str) -> list[float]:
        if text == "alpha":
            return [1.0, 0.0, 0.0, 0.0]
        if text == "alpha near":
            # Cosine with alpha is 0.98.
            return [0.98, math.sqrt(1.0 - 0.98 * 0.98), 0.0, 0.0]
        if text == "beta":
            return [0.0, 1.0, 0.0, 0.0]
        if text == "heartbeat":
            return [0.0, 0.0, 1.0, 0.0]
        if text == "unrelated":
            return [0.0, 0.0, 0.0, 1.0]
        raise AssertionError("unexpected text")


def _keys(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith("TANK_KEY_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TANK_KEY_TEMPLATE", TEMPLATE)
    monkeypatch.setenv("TANK_KEY_TIGER", TIGER)
    monkeypatch.setenv("TANK_API_KEY", WORKSPACE)


def _template_tenant() -> str:
    spec = importlib.util.spec_from_file_location(
        "c7_template_app",
        ROOT / "agents" / "_template" / "app.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return str(mod.HEARTBEAT_TENANT)


def _headers(key: str) -> dict[str, str]:
    return {"X-Tank-Key": key}


def _prove(store: object, monkeypatch: pytest.MonkeyPatch) -> None:
    _keys(monkeypatch)
    app = create_app(store, StubEmbedder())  # type: ignore[arg-type]
    heartbeat_tenant = _template_tenant()

    with TestClient(app) as client:
        assert client.get("/health").status_code == 200

        missing = client.post(
            "/memories",
            json={"tenant_id": TENANT_X, "text": "alpha", "kind": "fact", "source": "human"},
        )
        assert missing.status_code == 401
        assert TEMPLATE not in missing.text
        assert "alpha" not in missing.text

        denied = client.post(
            "/memories",
            headers=_headers(WORKSPACE),
            json={"tenant_id": TENANT_X, "text": "alpha", "kind": "fact", "source": "human"},
        )
        assert denied.status_code == 403

        created = client.post(
            "/memories",
            headers=_headers(TEMPLATE),
            json={
                "tenant_id": TENANT_X,
                "text": "alpha",
                "kind": "fact",
                "source": "https://a.example/1",
                "meta": {"page": 1, "keep": "yes"},
            },
        )
        assert created.status_code == 201
        created_body = created.json()
        assert created_body["deduped"] is False
        assert created_body["seen"] == 1
        memory_id = created_body["id"]

        other_agent = client.post(
            "/memories",
            headers=_headers(TEMPLATE),
            json={
                "tenant_id": TENANT_X,
                "text": "beta",
                "kind": "note",
                "source": "human",
                "agent": "tiger",
            },
        )
        assert other_agent.status_code == 403

        tiger_empty = client.post(
            "/recall",
            headers=_headers(TIGER),
            json={"tenant_id": TENANT_X, "query": "alpha"},
        )
        assert tiger_empty.status_code == 200
        assert tiger_empty.json()["memories"] == []

        other_tenant = client.post(
            "/recall",
            headers=_headers(TEMPLATE),
            json={"tenant_id": TENANT_Y, "query": "alpha"},
        )
        assert other_tenant.json()["memories"] == []

        same = client.post(
            "/recall",
            headers=_headers(TEMPLATE),
            json={"tenant_id": TENANT_X, "query": "alpha"},
        )
        hits = same.json()["memories"]
        assert len(hits) == 1
        assert hits[0]["id"] == memory_id
        assert hits[0]["text"] == "alpha"
        assert hits[0]["source"] == "https://a.example/1"
        assert hits[0]["score"] >= DEDUPE_SCORE

        smuggled = client.post(
            "/recall",
            headers=_headers(TEMPLATE),
            json={"tenant_id": TENANT_X, "query": "alpha", "collection": "mem_tiger"},
        )
        assert smuggled.status_code == 422

        deduped = client.post(
            "/memories",
            headers=_headers(TEMPLATE),
            json={
                "tenant_id": TENANT_X,
                "text": "alpha near",
                "kind": "fact",
                "source": "ledger:9",
                "meta": {"page": 2},
            },
        )
        assert deduped.status_code == 200
        assert deduped.json()["deduped"] is True
        assert deduped.json()["id"] == memory_id
        assert deduped.json()["seen"] == 2
        assert deduped.json()["created_at"] == created_body["created_at"]

        again = client.post(
            "/recall",
            headers=_headers(TEMPLATE),
            json={"tenant_id": TENANT_X, "query": "alpha"},
        ).json()["memories"]
        assert len(again) == 1
        assert again[0]["text"] == "alpha"
        assert again[0]["sources"] == ["https://a.example/1", "ledger:9"]
        assert again[0]["seen"] == 2
        assert again[0]["meta"] == {"page": 2, "keep": "yes"}

        kept = client.post(
            "/memories",
            headers=_headers(TEMPLATE),
            json={"tenant_id": TENANT_X, "text": "beta", "kind": "note", "source": "human"},
        )
        assert kept.status_code == 201
        assert kept.json()["deduped"] is False

        # Same words, other tenant: not a dedupe, and not visible to tenant X.
        other = client.post(
            "/memories",
            headers=_headers(TEMPLATE),
            json={"tenant_id": TENANT_Y, "text": "alpha", "kind": "fact", "source": "human"},
        )
        assert other.status_code == 201
        assert other.json()["id"] != memory_id

        # Tiger stores the same tenant. Template must not see it.
        tiger_saved = client.post(
            "/memories",
            headers=_headers(TIGER),
            json={"tenant_id": TENANT_X, "text": "alpha", "kind": "fact", "source": "file:a"},
        )
        assert tiger_saved.status_code == 201
        tiger_id = tiger_saved.json()["id"]

        template_view = client.post(
            "/recall",
            headers=_headers(TEMPLATE),
            json={"tenant_id": TENANT_X, "query": "alpha", "limit": 10},
        ).json()["memories"]
        assert tiger_id not in [row["id"] for row in template_view]
        assert all(row["tenant_id"] == TENANT_X for row in template_view)

        notes = client.post(
            "/recall",
            headers=_headers(TEMPLATE),
            json={"tenant_id": TENANT_X, "query": "beta", "kind": "note"},
        ).json()["memories"]
        assert len(notes) == 1
        assert notes[0]["kind"] == "note"

        facts = client.post(
            "/recall",
            headers=_headers(TEMPLATE),
            json={"tenant_id": TENANT_X, "query": "alpha", "kind": "fact"},
        ).json()["memories"]
        assert len(facts) == 1
        assert facts[0]["kind"] == "fact"

        workspace = client.post(
            "/recall",
            headers=_headers(WORKSPACE),
            json={"tenant_id": TENANT_X, "query": "alpha", "agent": "template"},
        )
        assert workspace.status_code == 200
        assert memory_id in [row["id"] for row in workspace.json()["memories"]]

        needs_agent = client.post(
            "/recall",
            headers=_headers(WORKSPACE),
            json={"tenant_id": TENANT_X, "query": "alpha"},
        )
        assert needs_agent.status_code == 400

        workspace_tiger = client.post(
            "/recall",
            headers=_headers(WORKSPACE),
            json={"tenant_id": TENANT_X, "query": "alpha", "agent": "tiger"},
        ).json()["memories"]
        assert [row["id"] for row in workspace_tiger] == [tiger_id]

        no_source = client.post(
            "/memories",
            headers=_headers(TEMPLATE),
            json={"tenant_id": TENANT_X, "text": "alpha", "kind": "fact"},
        )
        assert no_source.status_code == 422

        assert client.delete(f"/memories/{memory_id}", headers=_headers(WORKSPACE)).status_code == 403
        assert client.delete(f"/tenants/{TENANT_X}", headers=_headers(WORKSPACE)).status_code == 403
        assert client.delete(f"/memories/{memory_id}", headers=_headers(TIGER)).status_code == 404
        assert client.delete(f"/memories/{tiger_id}", headers=_headers(TEMPLATE)).status_code == 404

        wiped = client.delete(f"/tenants/{TENANT_X}", headers=_headers(TEMPLATE))
        assert wiped.status_code == 200
        assert wiped.json()["deleted"] == 2

        after = client.post(
            "/recall",
            headers=_headers(TEMPLATE),
            json={"tenant_id": TENANT_X, "query": "alpha", "limit": 10},
        ).json()["memories"]
        assert after == []

        still_y = client.post(
            "/recall",
            headers=_headers(TEMPLATE),
            json={"tenant_id": TENANT_Y, "query": "alpha"},
        ).json()["memories"]
        assert len(still_y) == 1

        still_tiger = client.post(
            "/recall",
            headers=_headers(TIGER),
            json={"tenant_id": TENANT_X, "query": "alpha"},
        ).json()["memories"]
        assert len(still_tiger) == 1
        assert still_tiger[0]["id"] == tiger_id

        # Template heartbeat. seen is the count. A new client is a restart.
        async def _heartbeat() -> None:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://hermes") as http:
                first = MemoryClient(
                    base_url="http://hermes",
                    api_key=TEMPLATE,
                    agent="template",
                    http=http,
                )
                await first.remember(heartbeat_tenant, "heartbeat", "heartbeat", "schedule")
                await first.remember(heartbeat_tenant, "heartbeat", "heartbeat", "schedule")
                second = MemoryClient(
                    base_url="http://hermes",
                    api_key=TEMPLATE,
                    agent="template",
                    http=http,
                )
                assert "template-secret-value" not in repr(second)
                found = await second.recall(heartbeat_tenant, "heartbeat")
                assert len(found) == 1
                assert found[0]["seen"] == 2
                assert found[0]["text"] == "heartbeat"
                assert found[0]["sources"] == ["schedule"]
                assert found[0]["tenant_id"] == heartbeat_tenant

        asyncio.run(_heartbeat())


def test_memory_walls_dedupe_and_template_heartbeat(monkeypatch: pytest.MonkeyPatch) -> None:
    _prove(InMemoryStore(), monkeypatch)


def test_qdrant_store_keeps_the_same_walls(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("qdrant_client")
    from qdrant_client import QdrantClient

    from hermes.qdrant_store import QdrantStore

    _prove(QdrantStore(QdrantClient(":memory:"), dim=4), monkeypatch)


def test_a_removed_agent_key_stops_matching(monkeypatch: pytest.MonkeyPatch) -> None:
    _keys(monkeypatch)
    app = create_app(InMemoryStore(), StubEmbedder())
    with TestClient(app) as client:
        ok = client.post(
            "/memories",
            headers=_headers(TEMPLATE),
            json={"tenant_id": TENANT_X, "text": "unrelated", "kind": "fact", "source": "human"},
        )
        assert ok.status_code == 201
        monkeypatch.delenv("TANK_KEY_TEMPLATE")
        gone = client.post(
            "/memories",
            headers=_headers(TEMPLATE),
            json={"tenant_id": TENANT_X, "text": "unrelated", "kind": "fact", "source": "human"},
        )
        assert gone.status_code == 401
        assert TEMPLATE not in gone.text


def test_blank_agent_key_is_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in list(os.environ):
        if name.startswith("TANK_KEY_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("TANK_KEY_TEMPLATE", "   ")
    monkeypatch.setenv("TANK_API_KEY", WORKSPACE)
    app = create_app(InMemoryStore(), StubEmbedder())
    with TestClient(app) as client:
        response = client.post(
            "/memories",
            headers=_headers("   "),
            json={"tenant_id": TENANT_X, "text": "unrelated", "kind": "fact", "source": "human"},
        )
        assert response.status_code == 401


def test_memory_client_refuses_to_call_without_a_key() -> None:
    async def check() -> None:
        client = MemoryClient(base_url="http://hermes", api_key="", agent="template")
        assert repr(client) == "MemoryClient(agent='template')"
        with pytest.raises(RuntimeError, match="tank key is not set"):
            await client.remember(TENANT_X, "alpha", "fact", "human")

    asyncio.run(check())


def test_memory_client_hides_transport_errors() -> None:
    class _Down:
        async def request(self, *_args: object, **_kwargs: object) -> None:
            raise httpx.ConnectError("down")

    async def check() -> None:
        client = MemoryClient(
            base_url="http://hermes",
            api_key=TEMPLATE,
            agent="template",
            http=_Down(),  # type: ignore[arg-type]
        )
        with pytest.raises(RuntimeError, match="hermes unreachable") as caught:
            await client.recall(TENANT_X, "alpha")
        assert TEMPLATE not in str(caught.value)

    asyncio.run(check())


def test_hermes_does_not_read_the_database() -> None:
    text = "\n".join(path.read_text() for path in (ROOT / "hermes").glob("*.py"))
    assert "asyncpg" not in text
    assert "agent_keys" not in text
    assert "DATABASE_URL" not in text
    assert "fastembed" in (ROOT / "hermes" / "embeddings.py").read_text()
    assert "BAAI/bge-small-en-v1.5" in (ROOT / "hermes" / "embeddings.py").read_text()
    service = (ROOT / "hermes" / "service.py").read_text()
    assert "qdrant" not in service
    assert "DEDUPE_SCORE = 0.97" in service


def test_hermes_joins_each_agent_corridor() -> None:
    data = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    services = data["services"]
    hermes = services["hermes"]
    assert set(hermes["networks"]) == {
        "default",
        "tervory-gw-template",
        "tervory-gw-tiger",
        "tervory-gw-market_lab",
    }
    assert "ports" not in hermes
    env = hermes["environment"]
    assert env["QDRANT_URL"] == "http://qdrant:6333"
    assert "DATABASE_URL" not in env
    assert "TANK_KEY_TEMPLATE" in env
    assert "TANK_KEY_TIGER" in env
    assert "TANK_KEY_MARKET_LAB" in env
    assert "TANK_API_KEY" in env
    qdrant_nets = services["qdrant"].get("networks") or []
    assert "tervory-gw-template" not in qdrant_nets
    for name in ("workspace", "redis", "litellm", "searxng", "tiger", "agent-roles"):
        nets = services[name].get("networks") or []
        assert "tervory-gw-template" not in nets
    assert "tervory-gw-template" in services["tank"]["networks"]
    assert "tervory-gw-template" in services["postgres"]["networks"]


def test_env_example_names_the_hermes_model() -> None:
    text = (ROOT / ".env.example").read_text()
    assert "HERMES_EMBED_MODEL=BAAI/bge-small-en-v1.5" in text
    assert "does not read the database" in text


def test_isolation_script_allows_hermes_and_still_blocks_everyone_else() -> None:
    script = ROOT / "agents" / "check_isolation.sh"
    text = script.read_text()
    subprocess.check_call(["sh", "-n", str(script)])
    loops = re.findall(r"for host in ([a-z0-9 _-]+); do", text)
    assert loops[0].split() == ["tank", "postgres", "hermes"]
    blocked = loops[1].split()
    assert "qdrant" in blocked
    assert "hermes" not in blocked
    assert "workspace" in blocked
    assert "redis" in blocked
    assert "litellm" in blocked
    assert "searxng" in blocked
    assert "tiger" in blocked
    assert "agent-other" in blocked
    assert 'has_part "$short" hermes' in text
    assert "http://hermes:8000/health" in text
    assert "gateway $net holds only this agent, tank, postgres, and hermes" in text
