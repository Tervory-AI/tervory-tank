"""BF2: a page load does not move a model, and a bad name never reaches LiteLLM.

No database and no network. Policy reads stay on the tenant in the request.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import pytest
import yaml
from fastapi import HTTPException
from starlette.requests import Request

import graduate
import main

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 15, tzinfo=timezone.utc)
TENANT = uuid.UUID("00000000-0000-0000-0000-0000000000aa")
OTHER = uuid.UUID("00000000-0000-0000-0000-0000000000bb")


def _request(path: str) -> Request:
    return Request({
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    })


class _Conn:
    def __init__(self, row: dict | None = None, rows: list | None = None, ranks: list | None = None) -> None:
        self.row = row
        self.rows = rows
        self.ranks = ranks or []
        self.queries: list[tuple[str, tuple]] = []
        self.executes: list[tuple] = []

    async def fetchrow(self, sql: str, *args: object) -> dict | None:
        self.queries.append((sql, args))
        if "FROM tank.policy" in sql:
            return self.row
        return {"rejected": 0, "judged": 0}

    async def fetch(self, sql: str, *args: object) -> list:
        self.queries.append((sql, args))
        if "FROM tank.policy p" in sql or "tenant_id = $1 OR tenant_id IS NULL" in sql:
            return list(self.rows or [])
        if "FROM tank.graduation_rank" in sql:
            return list(self.ranks)
        return []

    async def fetchval(self, sql: str, *args: object) -> object:
        self.queries.append((sql, args))
        if "tank.controls" in sql:
            return False  # Fixture has paid work enabled.
        raise AssertionError(f"unexpected scalar query: {sql}")

    async def execute(self, *args: object) -> str:
        self.executes.append(args)
        return "UPDATE 1"

    def transaction(self) -> "_Conn":
        return self

    async def __aenter__(self) -> "_Conn":
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _Pool:
    def __init__(self, conn: _Conn) -> None:
        self.conn = conn

    def acquire(self) -> _Conn:
        return self.conn


def _policy_row(**overrides: object) -> dict:
    row = {
        "task_type": "tier0.answer",
        "model": "luna",
        "priority": "standard",
        "rung": 1,
        "max_tokens_out": 32,
        "system_prompt": None,
        "cache_scope": "none",
        "candidate_model": "haiku",
        "shadow_rate": 1,
        "previous_model": None,
        "eval_threshold": 0.97,
        "min_shadow_samples": 30,
        "max_reject_rate": 0.05,
        "auto_promote": True,
        "field_floors": {},
        "semantic_cache": False,
        "promoted_at": None,
        "number_tolerance": 0.01,
        "n": 40,
        "agreement": 0.99,
        "cand_cost": 0.01,
        "prim_cost": 0.05,
        "calls_30d": 100,
        "cost_30d": 12.5,
        "cache_hits": 7,
    }
    row.update(overrides)
    return row


def _rank_rows() -> list[dict]:
    return [
        {
            "task_type": "tier0.answer",
            "candidate": "haiku",
            "kind": "model",
            "status": "shadow",
            "shadow_n": 88,
            "shadow_agreement": 0.91,
            "cost_per_call": 0.02,
            "price_usd": 0.004,
        },
        {
            "task_type": "tier0.answer",
            "candidate": "sol",
            "kind": "model",
            "status": "shadow",
            "shadow_n": 77,
            "shadow_agreement": 0.5,
            "cost_per_call": 0.03,
            "price_usd": 0.01,
        },
    ]


def _ladder_numbers(row: dict) -> list:
    found: list = []
    for step in row["ladder"]["steps"]:
        found.extend([step["samples"], step["agreement"], step["cost_per_call"]])
    return found


def _move_policy(candidate: str) -> dict:
    return {
        "task_type": "base.extract",
        "model": "luna",
        "candidate_model": candidate,
        "previous_model": None,
        "rung": 1,
        "eval_threshold": 0.97,
        "min_shadow_samples": 30,
        "max_reject_rate": 0.05,
        "auto_promote": True,
        "field_floors": {},
        "semantic_cache": False,
        "promoted_at": None,
        "number_tolerance": 0.01,
        "shadow_rate": 1,
    }


class _Gateway:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("LiteLLM was called")


class _Answer:
    status_code = 200
    headers = {"content-type": "application/json", "x-litellm-response-cost": "0"}
    text = "ok"

    def json(self) -> dict:
        return {"choices": [{"message": {"content": "ok"}}], "usage": {}}


class _OkGateway:
    calls: list[str] = []

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    async def __aenter__(self) -> "_OkGateway":
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def post(self, _url: str, **kwargs: object) -> _Answer:
        body = kwargs.get("json")
        assert isinstance(body, dict)
        _OkGateway.calls.append(str(body.get("model")))
        return _Answer()


# ---------- key ----------

@pytest.mark.asyncio
async def test_an_empty_key_never_matches_an_empty_header(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "_pool", None)
    monkeypatch.setattr(main, "TANK_API_KEY", "")
    with pytest.raises(HTTPException) as caught:
        await main.require_key(_request("/v1/policy"), "")
    assert caught.value.status_code == 401
    monkeypatch.setattr(main, "TANK_API_KEY", "   ")
    with pytest.raises(HTTPException) as blank:
        await main.require_key(_request("/v1/policy"), "   ")
    assert blank.value.status_code == 401
    monkeypatch.setattr(main, "TANK_API_KEY", "test")
    assert await main.require_key(_request("/health"), "test") is None


@pytest.mark.asyncio
async def test_startup_refuses_an_empty_key(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("pool opened")

    monkeypatch.setattr(main.asyncpg, "create_pool", boom)
    for value in ("", "   "):
        monkeypatch.setenv("TANK_API_KEY", value)
        with pytest.raises(RuntimeError, match="TANK_API_KEY is empty"):
            await main._startup()


# ---------- names LiteLLM cannot call ----------

@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["skill:base.extract@2.0.0", "cache:semantic", "cache:other", " skill:base.extract@1.0.0 "])
async def test_put_policy_refuses_skill_and_cache_names(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    def boom() -> None:
        raise AssertionError("policy was written")

    monkeypatch.setattr(main, "pool", boom)
    body = main.PolicyRow(task_type="tier0.answer", model=name)
    with pytest.raises(HTTPException) as caught:
        await main.put_policy("tier0.answer", body)
    assert caught.value.status_code == 400
    assert caught.value.detail == graduate.ROUTER_BLOCK


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["skill:base.extract", "cache:semantic"])
async def test_rollback_refuses_a_name_litellm_cannot_call(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    conn = _Conn(row={"model": "luna", "previous_model": name})
    monkeypatch.setattr(main, "pool", lambda: _Pool(conn))
    with pytest.raises(HTTPException) as caught:
        await main.rollback("tier0.answer", main.PromoteBody())
    assert caught.value.status_code == 400
    assert caught.value.detail == graduate.ROUTER_BLOCK
    assert conn.executes == []


@pytest.mark.asyncio
async def test_rollback_still_writes_a_real_model(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _Conn(row={"model": "haiku", "previous_model": "luna"})
    monkeypatch.setattr(main, "pool", lambda: _Pool(conn))
    result = await main.rollback("tier0.answer", main.PromoteBody(by="founder"))
    assert result["model"] == "luna"
    assert conn.executes


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["skill:base.extract", "cache:semantic"])
async def test_promote_refuses_a_name_litellm_cannot_call(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    conn = _Conn(row=_move_policy(name))
    monkeypatch.setattr(main, "pool", lambda: _Pool(conn))
    with pytest.raises(HTTPException) as caught:
        await main.promote("base.extract", main.PromoteBody(by="founder"))
    assert caught.value.status_code == (409 if name.startswith("skill:") else 400)
    assert caught.value.detail == ("a code candidate looks like skill:id@version" if name.startswith("skill:") else graduate.ROUTER_BLOCK)
    assert conn.executes == []


def test_a_dropped_promotion_can_restore_a_pinned_skill() -> None:
    policy = {
        "task_type": "base.extract",
        "model": "luna",
        "candidate_model": None,
        "previous_model": "skill:base.extract@2.0.0",
        "promoted_at": NOW - timedelta(days=1),
    }
    move = graduate.rollback_if_dropped(policy, graduate.Evidence(live_agreement=0.2), NOW)
    assert move.action == "rollback"
    assert move.policy["model"] == "skill:base.extract@2.0.0"
    assert move.policy["rung"] == 3
    cache = {**policy, "previous_model": "cache:semantic"}
    held = graduate.rollback_if_dropped(cache, graduate.Evidence(rejected=4, judged=10), NOW)
    assert held.action == "hold"
    assert held.policy["model"] == "luna"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["skill:base.extract", "cache:semantic", "cache:other"])
async def test_run_route_does_not_call_litellm(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.delenv("TANK_PROVIDER_ALLOW", raising=False)
    conn = _Conn(row=_policy_row(model=name, system_prompt=None, cache_scope="none"))
    monkeypatch.setattr(main, "pool", lambda: _Pool(conn))
    monkeypatch.setattr(main, "_redis", None)
    monkeypatch.setattr(main.httpx, "AsyncClient", _Gateway)
    req = main.RouteRequest(tenant_id=TENANT, messages=[main.Message(role="user", content="Hello")])
    with pytest.raises(HTTPException) as caught:
        await main.run_route(req)
    assert caught.value.status_code == 400
    assert caught.value.detail == graduate.ROUTER_BLOCK
    assert conn.executes == []


@pytest.mark.asyncio
async def test_run_route_still_calls_litellm_for_a_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.delenv("TANK_PROVIDER_ALLOW", raising=False)
    conn = _Conn(row=_policy_row(model="luna", candidate_model=None, shadow_rate=0))
    monkeypatch.setattr(main, "pool", lambda: _Pool(conn))
    monkeypatch.setattr(main, "_redis", None)
    _OkGateway.calls = []
    monkeypatch.setattr(main.httpx, "AsyncClient", _OkGateway)
    req = main.RouteRequest(tenant_id=TENANT, messages=[main.Message(role="user", content="Hello")])
    response = await main.run_route(req)
    assert response.content == "ok"
    assert _OkGateway.calls == ["luna"]


# ---------- one tenant ----------

@pytest.mark.asyncio
async def test_policy_returns_one_tenant_and_the_platform_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _Conn(rows=[
        {"task_type": "tier0.answer", "tenant_id": TENANT, "system_prompt": "mine"},
        {"task_type": "tier0.answer", "tenant_id": None, "system_prompt": "platform"},
        {"task_type": "zenas.draft", "tenant_id": OTHER, "system_prompt": "theirs"},
    ])
    monkeypatch.setattr(main, "pool", lambda: _Pool(conn))
    rows = await main.list_policy(TENANT)
    prompts = {row["system_prompt"] for row in rows}
    assert prompts == {"mine", "platform"}
    sql, args = conn.queries[0]
    assert "tenant_id = $1" in sql
    assert "tenant_id IS NULL" in sql
    assert args == (TENANT,)


@pytest.mark.asyncio
async def test_graduation_read_does_not_move_a_model(monkeypatch: pytest.MonkeyPatch) -> None:
    async def explode() -> None:
        raise AssertionError("page load moved a model")

    conn = _Conn(rows=[_policy_row()], ranks=_rank_rows())
    monkeypatch.setattr(main, "_move_all", explode)
    monkeypatch.setattr(main, "pool", lambda: _Pool(conn))
    rows = await main.graduation()
    assert rows[0]["model"] == "luna"
    assert rows[0]["calls_30d"] == 0
    assert rows[0]["cost_30d"] is None
    assert rows[0]["cache_hits"] == 0
    assert rows[0]["n"] == 0
    assert rows[0]["agreement"] is None
    assert rows[0]["eligible"] is False
    numbers = _ladder_numbers(rows[0])
    assert 88 not in numbers
    assert 77 not in numbers
    assert 0.91 not in numbers
    assert 0.02 not in numbers
    sql, args = conn.queries[0]
    assert "($1::uuid IS NOT NULL AND s.tenant_id = $1) OR $2::bool" in sql
    assert "($1::uuid IS NULL OR s.tenant_id = $1)" not in sql
    assert args == (None, False)
    assert all("UPDATE" not in query[0] for query in conn.queries)


@pytest.mark.asyncio
async def test_graduation_totals_for_one_tenant_are_not_mixed(monkeypatch: pytest.MonkeyPatch) -> None:
    conn = _Conn(rows=[_policy_row()], ranks=_rank_rows())
    monkeypatch.setattr(main, "pool", lambda: _Pool(conn))
    rows = await main.graduation(tenant_id=TENANT)
    sql, args = conn.queries[0]
    assert "($1::uuid IS NOT NULL AND s.tenant_id = $1) OR $2::bool" in sql
    assert "l.tenant_id = $1" in sql
    assert args == (TENANT, False)
    assert rows[0]["calls_30d"] == 100
    assert rows[0]["n"] == 40
    assert rows[0]["agreement"] == 0.99
    assert rows[0]["eligible"] is True
    numbers = _ladder_numbers(rows[0])
    assert 88 not in numbers
    assert 77 not in numbers
    assert 0.91 not in numbers
    assert 0.02 not in numbers
    assert 40 in numbers


@pytest.mark.asyncio
async def test_a_founder_still_receives_platform_totals(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TANK_API_KEY", "test")
    monkeypatch.setenv("TERVORY_ADMIN_USER_IDS", "user_founder")
    conn = _Conn(rows=[_policy_row()], ranks=_rank_rows())
    monkeypatch.setattr(main, "pool", lambda: _Pool(conn))
    rows = await main.graduation(x_tank_key="test", x_tervory_admin="user_founder")
    assert rows[0]["calls_30d"] == 100
    assert rows[0]["cost_30d"] == 12.5
    assert rows[0]["cache_hits"] == 7
    assert rows[0]["n"] == 40
    assert rows[0]["eligible"] is True
    assert 88 in _ladder_numbers(rows[0])
    _sql, args = conn.queries[0]
    assert args == (None, True)


# ---------- seed ----------

def test_rule_card_is_seeded_on_a_model_with_a_fallback() -> None:
    schema = (ROOT / "tank" / "schema.sql").read_text(encoding="utf-8")
    assert "('zenas.rule_card', 1, 'luna'," in schema
    assert "('zenas.rule_card', 1, 'astra'," not in schema
    assert "2026-10-15-zenas-rule-card-fallback" in schema
    assert "model = 'astra'" in schema
    config = yaml.safe_load((ROOT / "litellm" / "config.yaml").read_text(encoding="utf-8"))
    covered = {name.strip() for item in config["litellm_settings"]["fallbacks"] for name in item}
    assert "luna" in covered
    assert "astra" not in covered
