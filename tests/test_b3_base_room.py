"""B3: Base runs in its own room. A sample batch matches the pre-move records."""

from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml
from fastapi import HTTPException
from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "agents" / "_chassis"))
sys.path.insert(0, str(ROOT / "agents" / "base"))

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

from pipeline import (  # noqa: E402
    BASE_CORE,
    Outcome,
    enrich_one,
    enrich_queued,
    is_account_error,
    order_states,
    prepare_batch,
    result_line,
    state_of,
)

FIXTURE = ROOT / "tests" / "fixtures" / "b3-sample-batch.json"
SCHEMA = (ROOT / "tank" / "schema.sql").read_text(encoding="utf-8")


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module

REFS = {skill_id: f"{skill_id}@1.0.0" for skill_id in [*BASE_CORE, "ffl.ingest", "ffl.profile"]}
RAW = [
    {
        "name": "Acme Guns",
        "city": "Austin",
        "state": "TX",
        "phone": "512-555-0100",
        "address": "1 Main St",
        "zip": "78701",
    },
    {
        "name": "Acme Guns",
        "city": "Austin",
        "state": "TX",
        "phone": "512-555-0199",
        "address": "2 Main St",
        "zip": "78701",
        "website": "https://acme.example",
    },
]
IDS = [
    "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1",
    "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2",
]


class SkillFailure(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


def _scripted(skill_id: str, payload: dict) -> dict:
    base = {"_skill": REFS[skill_id], "_ms": 3, "_cost_usd": 0.0}
    if skill_id == "base.normalize":
        name = str(payload.get("name") or "")
        return {
            **base,
            "fields": {
                "name": {"value": name, "source": "input", "confidence": 90},
                "name_key": {"value": name.lower(), "source": "input", "confidence": 90},
                "city": {"value": payload.get("city"), "source": "input", "confidence": 90},
                "state": {"value": str(payload.get("state") or "").upper(), "source": "input", "confidence": 95},
                "phone": {"value": payload.get("phone"), "source": "input", "confidence": 80},
                "street": {"value": payload.get("address"), "source": "input", "confidence": 80},
                "zip": {"value": payload.get("zip"), "source": "input", "confidence": 90},
            },
        }
    if skill_id == "base.resolve":
        fields = (payload.get("record") or {}).get("fields") or {}
        name_key = (fields.get("name_key") or {}).get("value")
        match = next((row for row in payload.get("registry") or [] if row.get("name_key") == name_key), None)
        if match:
            return {**base, "match": {"id": match["id"]}, "verdict": "duplicate", "score": 92}
        return {**base, "match": None, "verdict": "new", "score": 0}
    if skill_id == "base.find_site":
        if payload.get("website"):
            site = {"value": payload["website"], "source": "input", "confidence": 100}
        else:
            site = {"value": "https://acme.example", "source": "search", "confidence": 70}
        body = {**base, "website": site}
        if site["source"] == "search":
            body["evidence"] = "listed"
        return body
    if skill_id == "base.scrape_site":
        return {
            **base,
            "emails": ["a@acme.example"],
            "phones": ["512-555-0100"],
            "socials": {"facebook": "https://facebook.com/acme"},
            "pages": ["https://acme.example"],
            "text": "Acme Guns sells rifles in Austin. " * 3,
            "via": "tiger",
        }
    if skill_id == "base.extract":
        if payload.get("fail") == "account":
            raise SkillFailure("credit balance too low")
        if payload.get("fail") == "blip":
            raise SkillFailure("timeout")
        return {
            **base,
            "_cost_usd": 0.002,
            "confidence": 80,
            "categories": ["retail"],
            "services": ["sales"],
            "description": "A shop",
            "people": [{"name": "Ada"}],
        }
    if skill_id == "base.contacts":
        return {
            **base,
            "confidence": 75,
            "domain": "acme.example",
            "domain_accepts_mail": True,
            "generic_emails": ["a@acme.example"],
            "personal_emails": [],
            "email_pattern": "{first}@acme.example",
            "contacts": [{"name": "Ada"}],
            "decision_maker": {"name": "Ada", "role": "owner"},
        }
    if skill_id == "base.socials":
        return {
            **base,
            "count": 1,
            "profiles": [{"site": "facebook"}],
            "presence": "thin",
            "confidence": 85,
        }
    if skill_id == "base.business_data":
        return {
            **base,
            "_cost_usd": 0.003,
            "confidence": 60,
            "size_band": "1-5",
            "revenue_band": "under 1m",
            "business_model": "retail",
            "naics": "451110",
            "naics_label": "Sporting goods",
            "basis": "site",
        }
    if skill_id == "base.verify":
        return {**base, "confidence": 82, "tier": "ready", "flags": ["thin_social"], "layers": ["site"], "checks": {"name": True}}
    if skill_id == "ffl.ingest":
        return {
            **base,
            "record": dict(payload),
            "engine": {"licence_number": "1-23-456-78-9A-12345", "licence_type": "01"},
        }
    if skill_id == "ffl.profile":
        return {
            **base,
            "licence_number": "1-23-456-78-9A-12345",
            "licence_type": "01",
            "licence_type_label": "Dealer",
            "segment": "retail",
            "lapsed": False,
        }
    raise AssertionError(skill_id)


async def _call(skill_id: str, payload: dict) -> dict:
    return _scripted(skill_id, payload)


def _public(outcome: Outcome) -> dict:
    return {
        "status": outcome.status,
        "profile": outcome.profile,
        "passes": outcome.passes,
        "confidence": outcome.confidence,
        "error": outcome.error,
    }


async def _sample() -> dict:
    inputs, engine_rows, registry, prep_cost = await prepare_batch(RAW, IDS, None, None, _call)
    pairs = await enrich_queued(
        [0, 1], IDS, inputs, engine_rows, registry, False, None, _call, lambda: False, 4, REFS
    )
    spent = prep_cost + sum(item.cost_usd for _, item in pairs if item is not None and item.status == "done")
    done = [item for _, item in pairs if item is not None and item.status == "done"]
    ready = sum(1 for item in done if item.confidence >= 80)
    engine_in = {"licence_number": "1-23-456-78-9A-12345", "licence_type": "01"}
    engine_outcome = await enrich_one(inputs[0], engine_in, [], "ffl", _call, REFS)
    return {
        "records": [_public(item) for _, item in pairs if item is not None],
        "result": result_line(len(done), ready, 0, spent),
        "engine_record": _public(engine_outcome),
    }


def test_sample_batch_matches_the_pre_move_records() -> None:
    """The pass order, merges, and confidence are the ones Tank wrote before the move."""
    got = asyncio.run(_sample())
    assert FIXTURE.is_file(), "missing tests/fixtures/b3-sample-batch.json"
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert got == expected
    first, second = got["records"]
    assert first["status"] == "done" and second["status"] == "done"
    assert first["confidence"] == 82
    assert first["profile"]["registry_match"]["value"] == IDS[1]
    assert second["profile"]["registry_match"]["value"] == IDS[0]
    assert first["profile"]["website"]["source"] == "search"
    assert second["profile"]["website"]["source"] == "input"
    assert second["profile"]["phone"]["value"] == "512-555-0100"
    assert first["passes"]["2c"]["cost_usd"] == 0.002
    assert first["passes"]["5"]["cost_usd"] == 0.003
    assert got["result"] == "2 enriched (2 ready), 0 failed, model spend $0.0100"
    assert got["engine_record"]["profile"]["registry_match"]["value"] == "1-23-456-78-9A-12345"
    assert got["engine_record"]["profile"]["ffl_licence_type_label"]["value"] == "Dealer"
    assert got["engine_record"]["passes"]["6"]["segment"] == "retail"


def test_split_by_state_is_smallest_first_and_a_blocked_account_stays_queued() -> None:
    groups = {"TX": [{}, {}], "CA": [{}], "??": []}
    assert [state for state, _rows in order_states(groups)] == ["??", "CA", "TX"]

    async def check() -> None:
        assert await state_of({"premise_state": "California"}, "ffl", _call) == "CA"
        assert await state_of({}, None, _call) == "??"

        async def blip(skill_id: str, payload: dict) -> dict:
            if skill_id == "base.extract":
                raise SkillFailure("timeout")
            return await _call(skill_id, payload)

        skipped = await enrich_one(RAW[0], None, [], None, blip, REFS)
        assert skipped.status == "done"
        assert skipped.passes["2c"]["skill"] == "base.extract@1.0.0"
        assert skipped.passes["2c"]["skipped"].startswith("model call failed:")

        async def blocked(skill_id: str, payload: dict) -> dict:
            if skill_id == "base.business_data":
                raise SkillFailure("credit balance too low")
            return await _call(skill_id, payload)

        held = await enrich_one(RAW[0], None, [], None, blocked, REFS)
        assert held.status == "queued"
        assert held.profile == {}
        assert is_account_error(SkillFailure("billing"))

    asyncio.run(check())


def _create_columns(sql: str, qualified: str) -> list[str]:
    match = re.search(rf"CREATE TABLE IF NOT EXISTS {re.escape(qualified)} \((.*?)\n\);", sql, re.S)
    assert match, qualified
    names = []
    for line in match.group(1).splitlines():
        part = line.strip().strip(",")
        if not part or part.startswith("--"):
            continue
        names.append(part.split()[0])
    return names


def test_schema_copies_records_once_and_leaves_the_old_table_read_only() -> None:
    assert _create_columns(SCHEMA, "base.records") == _create_columns(SCHEMA, "agent_base.records")
    assert "event = 'base.records.copy'" in SCHEMA
    assert "RAISE NOTICE 'B3 copied % rows from base.records to agent_base.records'" in SCHEMA
    assert "base.records is read-only" in SCHEMA
    assert "CREATE TRIGGER base_records_readonly" in SCHEMA
    assert "IF NOT EXISTS (SELECT 1 FROM agent_base.migration_log WHERE event = 'base.records.copy')" in SCHEMA
    assert "FROM tank.tasks" in SCHEMA and "task_type = 'base.enrich'" in SCHEMA


def test_room_is_wired_and_client_queries_are_tenant_scoped() -> None:
    compose = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    corridor = "tervory-gw-base"
    assert "external" not in compose["networks"][corridor]
    assert compose["networks"][corridor]["name"] == corridor
    for name in ("tank", "postgres", "hermes", "tiger", "searxng"):
        assert corridor in services[name]["networks"]
    for name in ("redis", "qdrant", "litellm", "workspace", "agent-roles"):
        assert corridor not in (services[name].get("networks") or [])
    assert services["tank"]["environment"]["TANK_KEY_BASE"] == "${TANK_KEY_BASE:-}"
    assert services["hermes"]["environment"]["TANK_KEY_BASE"] == "${TANK_KEY_BASE:-}"
    assert services["tank"]["environment"]["BASE_AGENT_URL"] == "http://agent-base:8000"
    assert "AGENT_DB_PASSWORD_BASE" in services["agent-roles"]["environment"]
    assert corridor not in services["agent-roles"]["networks"]

    box = yaml.safe_load((ROOT / "agents" / "base" / "docker-compose.yml").read_text(encoding="utf-8"))
    service = box["services"]["agent-base"]
    assert box["networks"]["gw"]["external"] is True
    assert box["networks"]["gw"]["name"] == corridor
    assert service["networks"] == ["gw"]
    assert service["mem_limit"] == "512m"
    assert service["cpus"] in (0.5, "0.5")
    assert service["environment"]["DATABASE_URL"].startswith("postgresql://agent_base:")
    assert "POSTGRES_PASSWORD" not in service["environment"]
    assert "POSTGRES_USER" not in service["environment"]
    assert service["environment"]["TANK_KEY"] == "${TANK_KEY_BASE:-}"
    assert service["environment"]["TIGER_URL"] == "http://tiger:3000"
    assert service["environment"]["SEARXNG_URL"] == "http://searxng:8080"
    assert service["environment"]["HERMES_URL"] == "http://hermes:8000"

    example = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "TANK_KEY_BASE=" in example
    assert "AGENT_DB_PASSWORD_BASE=" in example

    script = (ROOT / "agents" / "check_isolation.sh").read_text(encoding="utf-8")
    subprocess.check_call(["sh", "-n", str(ROOT / "agents" / "check_isolation.sh")])
    assert 'if [ "$base_corridor" -eq 1 ] && [ "$host" = "tiger" ]' in script
    assert 'if [ "$base_corridor" -eq 1 ] && [ "$host" = "searxng" ]' in script
    assert '[ "$net" = "tervory-gw-base" ] && has_part "$short" tiger' in script
    assert '[ "$net" = "tervory-gw-base" ] && has_part "$short" searxng' in script
    assert '[ "$net" = "tervory-gw-tiger" ] && has_part "$short" tiger' in script
    assert "gateway $net holds only this agent, tank, postgres, hermes, tiger, and searxng" in script

    for folder in (ROOT / "agents" / "_chassis", ROOT / "agents" / "base"):
        path = str(folder)
        if path in sys.path:
            sys.path.remove(path)
        sys.path.insert(0, path)
    room = _load("base_room_mod", ROOT / "agents" / "base" / "room.py")
    base_app = _load("base_room_app", ROOT / "agents" / "base" / "app.py")

    for statement in (room.SQL_RECORDS_BY_TENANT, room.SQL_BATCHES_BY_TENANT, room.SQL_RETRY, room.SQL_REQUEUE_TASKS):
        assert "tenant_id=$1" in statement
    image = (ROOT / "agents" / "base" / "Dockerfile").read_text(encoding="utf-8")
    assert "pipeline.py" in image and "room.py" in image and "app.py" in image

    paths = {getattr(route, "path", "") for route in base_app.app.routes}
    for path in ("/v1/base/run", "/v1/base/retry", "/v1/base/rerun", "/v1/base/batches", "/v1/base/engines", "/v1/base/records", "/health"):
        assert path in paths
    assert base_app.app.state.handlers.keys() == {"ping"}


def test_tank_proxies_base_and_does_not_keep_the_worker() -> None:
    import main as tank

    source = (ROOT / "tank" / "main.py").read_text(encoding="utf-8")
    assert "_base_worker" not in source
    assert "_enrich_one" not in source
    assert "UPDATE base.records" not in source
    assert "http://agent-base:8000" in source

    class FakeHttp:
        def __init__(self) -> None:
            self.calls: list[tuple] = []

        async def request(self, method, url, **kwargs):
            self.calls.append((method, url, kwargs))
            return type("Resp", (), {"status_code": 202, "content": b'{"records":2}', "headers": {"content-type": "application/json"}})()

    fake = FakeHttp()
    tank._http = fake

    async def receive():
        return {"type": "http.request", "body": b'{"batch":"demo"}', "more_body": False}

    request = Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/v1/base/run",
            "raw_path": b"/v1/base/run",
            "query_string": b"tenant_id=abc",
            "headers": [(b"content-type", b"application/json"), (b"x-tank-key", b"secret-key")],
            "client": ("127.0.0.1", 9),
            "server": ("tank", 80),
        },
        receive,
    )

    async def check() -> None:
        response = await tank.base_proxy("run", request)
        assert response.status_code == 202
        assert response.body == b'{"records":2}'
        method, url, kwargs = fake.calls[0]
        assert method == "POST"
        assert url == "http://agent-base:8000/v1/base/run"
        assert kwargs["content"] == b'{"batch":"demo"}'
        assert "x-tank-key" not in {key.lower() for key in kwargs["headers"]}
        assert "secret-key" not in repr(kwargs)
        with pytest.raises(HTTPException) as caught:
            await tank.base_proxy("nope", request)
        assert caught.value.status_code == 404

    asyncio.run(check())
