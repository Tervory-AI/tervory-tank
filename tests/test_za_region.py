"""South Africa region: own stack, and Tank refuses the other region's tenants.

No database, no network, no model. The compose file is checked as YAML.
A foreign home region returns before any write. An identifier in a za prompt
is refused for every provider that is not running in South Africa.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import uuid
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "postgresql://x:y@localhost/z")
os.environ.setdefault("LITELLM_MASTER_KEY", "test")
os.environ.setdefault("TANK_API_KEY", "test")

import pytest
import yaml
from fastapi import HTTPException

import main

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = (ROOT / "docker-compose.za.yml").read_text(encoding="utf-8")
ZA_CONFIG = yaml.safe_load((ROOT / "litellm" / "config.za.yaml").read_text(encoding="utf-8"))
US_CONFIG = yaml.safe_load((ROOT / "litellm" / "config.yaml").read_text(encoding="utf-8"))
SA_ID = "8001015009087"
TENANT = "11111111-1111-1111-1111-111111111111"


def _parsed() -> dict:
    return yaml.safe_load(COMPOSE)


ROOM_COMPOSE = (ROOT / "agents" / "zenas" / "docker-compose.za.yml").read_text(encoding="utf-8")
MODEL_KEY = re.compile(r"(ANTHROPIC|OPENAI|GEMINI|XAI|DEEPSEEK|MISTRAL|MOONSHOT|OPENROUTER|PERPLEXITY)_API_KEY")


def test_za_compose_is_a_tank_stack_with_its_own_stores() -> None:
    data = _parsed()
    assert set(data["services"]) == {
        "postgres", "redis", "qdrant", "hermes", "litellm", "tank", "agent-roles",
        "r2-backup-za",
    }
    assert not data["services"]["r2-backup-za"].get("profiles")
    for name, service in data["services"].items():
        assert service["environment"]["TANK_REGION"] == "za", name
    assert data["networks"]["default"]["name"] == "tervory-za"
    assert data["networks"]["tervory-gw-zenas"]["name"] == "tervory-gw-zenas"
    assert "external" not in data["networks"]["default"]
    assert "external" not in data["networks"]["tervory-gw-zenas"]
    assert set(data["volumes"]) == {"za_pgdata", "za_redisdata", "za_qdrantdata", "za_backups", "za_r2_backup_spool", "za_litellm_chatgpt_token"}
    assert "tervory-gw-zenas" in data["services"]["postgres"]["networks"]
    assert "tervory-gw-zenas" in data["services"]["tank"]["networks"]
    assert "tervory-gw-zenas" in data["services"]["hermes"]["networks"]
    assert data["services"]["tank"]["environment"]["ZENAS_AGENT_URL"] == "http://agent-zenas:8000"
    assert "/app/config.za.yaml" in data["services"]["litellm"]["command"]
    assert "za.tervory.com" in COMPOSE
    for service in data["services"].values():
        assert "ports" not in service


def test_model_keys_reach_only_litellm_in_za() -> None:
    for name, service in _parsed()["services"].items():
        keys = [k for k in service["environment"] if MODEL_KEY.search(k)]
        assert not keys or name == "litellm", (name, keys)
    assert not MODEL_KEY.search(ROOM_COMPOSE)


def test_za_zenas_room_is_its_own_resource_on_the_corridor() -> None:
    room = yaml.safe_load(ROOM_COMPOSE)
    assert set(room["services"]) == {"agent-zenas", "pool-loader"}
    assert room["networks"]["gw"] == {"external": True, "name": "tervory-gw-zenas"}
    # Contracts are assembled inside agent-zenas; no Docassemble network or resource.
    assert set(room["networks"]) == {"gw"}
    for name, service in room["services"].items():
        assert service["environment"]["TANK_REGION"] == "za", name
        assert service["networks"] == ["gw"], name
        assert "ports" not in service, name
        assert "env_file" not in service, name
        for banned in ("POSTGRES_PASSWORD", "POSTGRES_USER", "LITELLM_MASTER_KEY", "TANK_API_KEY", "QDRANT_API_KEY"):
            assert banned not in service["environment"], (name, banned)
    agent = room["services"]["agent-zenas"]["environment"]
    assert agent["TANK_KEY"] == "${TANK_KEY:-}"
    assert agent["DATABASE_URL"].startswith("postgresql://agent_zenas:")
    loader = room["services"]["pool-loader"]
    assert loader["volumes"] == ["za_agent_data:/data"]
    assert "load" in loader["profiles"]
    lowered = ROOM_COMPOSE.lower()
    assert "us-east" not in lowered and "boston" not in lowered


def test_za_compose_names_no_us_host_and_does_not_replicate() -> None:
    lowered = COMPOSE.lower()
    assert "us-east" not in lowered
    assert "boston" not in lowered
    assert "app.tervory.com" not in lowered
    assert "api.tervory.com" not in COMPOSE
    assert "replicaof" not in lowered
    assert "wal_level" not in lowered
    assert "primary_conninfo" not in lowered
    assert "external: true" not in lowered
    addresses = set(re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", COMPOSE))
    assert addresses <= {"127.0.0.1"}
    for banned in ("workspace", "searxng", "agent-base", "agent-tiger", "agent-rig"):
        assert banned not in lowered


def test_za_roster_matches_the_funded_models_and_has_no_sa_model_yet() -> None:
    za_names = [item["model_name"] for item in ZA_CONFIG["model_list"]]
    us_names = [item["model_name"] for item in US_CONFIG["model_list"]]
    assert za_names == us_names
    assert "za-local" not in za_names
    raw = (ROOT / "litellm" / "config.za.yaml").read_text(encoding="utf-8")
    assert "model_name: za-local" in raw
    assert "hosted_in: za" in raw
    for item in ZA_CONFIG["model_list"]:
        # MODELS-3: the public Hugging Face router is the only api_base; it is not SA hosting.
        assert item["litellm_params"].get("api_base") in (None, "https://router.huggingface.co/v1"), item["model_name"]
        assert "hosted_in" not in (item.get("model_info") or {}), item["model_name"]
    assert main.sa_hosted_models() == frozenset()


def test_za_litellm_gets_the_deepseek_and_moonshot_keys_like_boston() -> None:
    """MODELS-1: same key names as the Boston LiteLLM service, and still only on LiteLLM."""
    za_env = _parsed()["services"]["litellm"]["environment"]
    boston = yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    boston_env = boston["services"]["litellm"]["environment"]
    for key in ("DEEPSEEK_API_KEY", "MOONSHOT_API_KEY"):
        assert za_env[key] == boston_env[key] == "${" + key + ":-}"


def test_home_region_refusal_both_ways() -> None:
    assert main.home_region_refusal("za", "us-east") == main.ZA_HOME_MESSAGE
    assert main.home_region_refusal("us-east", "za") == main.US_HOME_MESSAGE
    assert main.home_region_refusal("us", "us-east") is None
    assert main.home_region_refusal("za", "za") is None
    assert main.normalize_home(None) == ""
    assert main.normalize_home("") == ""
    for box in ("us-east", "za"):
        for home in (None, "", "   ", "eu"):
            assert main.home_region_refusal(home, box) == main.HOME_REQUIRED


def test_za_refuses_an_identifier_for_a_non_sa_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ZA_HOSTED_MODELS", raising=False)
    monkeypatch.delenv("TANK_PROVIDER_ALLOW", raising=False)
    text = f"The ID {SA_ID} is on the form."
    refusal = main.model_call_refusal(text, "luna", box="za", tenant_id=TENANT)
    assert refusal == main.IDENTIFIER_REFUSAL
    assert SA_ID not in (refusal or "")
    assert main.model_call_refusal(text, None, box="za", tenant_id=TENANT) == main.IDENTIFIER_REFUSAL
    masked = "The ID [SA_ID_1] is on the form."
    assert main.model_call_refusal(masked, "luna", box="za", tenant_id=TENANT) is None
    assert main.model_call_refusal(text, "luna", box="us-east", tenant_id=TENANT) is None
    phone = "Call +27 82 123 4567 tomorrow."
    assert main.model_call_refusal(phone, "haiku", box="za", tenant_id=TENANT) == main.IDENTIFIER_REFUSAL
    # The task name alone is not a pool read. A client draft is not either.
    assert main.model_call_refusal(text, "luna", box="za", tenant_id=TENANT, task_type="zenas.case_facts") == main.IDENTIFIER_REFUSAL
    assert main.model_call_refusal(text, None, box="za", tenant_id=TENANT, task_type="zenas.case_facts") == main.IDENTIFIER_REFUSAL
    assert main.model_call_refusal(phone, "luna", box="za", tenant_id=TENANT, task_type="zenas.case_facts") == main.IDENTIFIER_REFUSAL
    assert main.model_call_refusal(text, "luna", box="za", tenant_id=TENANT, task_type="zenas.draft") == main.IDENTIFIER_REFUSAL
    assert main.model_call_refusal(text, "luna", box="za", tenant_id=TENANT, task_type="zenas.review") == main.IDENTIFIER_REFUSAL
    assert SA_ID not in str(main.model_call_refusal(text, "luna", box="za", tenant_id=TENANT, task_type="zenas.draft") or "")


def test_sa_hosted_model_may_see_an_identifier_and_the_allow_list_can_narrow_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZA_HOSTED_MODELS", "za-local")
    monkeypatch.delenv("TANK_PROVIDER_ALLOW", raising=False)
    text = f"ID {SA_ID}"
    assert main.model_call_refusal(text, None, box="za", tenant_id=TENANT) is None
    assert main.model_call_refusal(text, "za-local", box="za", tenant_id=TENANT) is None
    assert main.model_call_refusal(text, "luna", box="za", tenant_id=TENANT) == main.IDENTIFIER_REFUSAL
    monkeypatch.setenv("TANK_PROVIDER_ALLOW", '{"' + TENANT + '":["luna"]}')
    assert main.model_call_refusal(text, "za-local", box="za", tenant_id=TENANT) == main.IDENTIFIER_REFUSAL
    assert main.model_call_refusal("No identifier here.", "luna", box="za", tenant_id=TENANT) is None
    assert main.model_call_refusal("No identifier here.", "haiku", box="za", tenant_id=TENANT) == main.ALLOW_REFUSAL
    # The allow-list, not a provider ban, is what keeps a tenant off DeepSeek and Kimi.
    assert main.model_call_refusal("No identifier here.", "deepseek-flash", box="za", tenant_id=TENANT) == main.ALLOW_REFUSAL
    assert main.model_call_refusal("No identifier here.", "kimi", box="za", tenant_id=TENANT) == main.ALLOW_REFUSAL
    assert main.model_call_refusal("No identifier here.", "deepseek/chat", box="za", tenant_id=TENANT) == main.ALLOW_REFUSAL
    identified = f"ID {SA_ID}"
    # Without a proven pool read the identifier rule answers first.
    assert (
        main.model_call_refusal(identified, "haiku", box="za", tenant_id=TENANT, task_type="zenas.case_facts")
        == main.IDENTIFIER_REFUSAL
    )
    assert (
        main.model_call_refusal(identified, "luna", box="za", tenant_id=TENANT, task_type="zenas.case_facts")
        == main.IDENTIFIER_REFUSAL
    )
    proven = dict(task_type="zenas.case_facts", caller="zenas", pool_read=True)
    assert main.model_call_refusal(identified, "luna", box="za", tenant_id=TENANT, **proven) is None
    assert main.model_call_refusal(identified, "haiku", box="za", tenant_id=TENANT, **proven) == main.ALLOW_REFUSAL
    assert (
        main.model_call_refusal(identified, "deepseek/chat", box="za", tenant_id=TENANT, **proven)
        == main.ALLOW_REFUSAL
    )
    assert (
        main.model_call_refusal(identified, "luna", box="za", tenant_id=TENANT, caller="tiger", pool_read=True, task_type="zenas.case_facts")
        == main.IDENTIFIER_REFUSAL
    )
    assert (
        main.model_call_refusal(identified, "luna", box="za", tenant_id=TENANT, caller=None, pool_read=True, task_type="zenas.case_facts")
        == main.IDENTIFIER_REFUSAL
    )
    assert (
        main.model_call_refusal(
            identified, "luna", box="za", tenant_id=TENANT, caller="zenas", pool_read=True,
            task_type="zenas.case_facts", skill="zenas.case_facts@1.0.0",
        )
        == main.IDENTIFIER_REFUSAL
    )


def test_pure_code_detect_is_not_a_model_refusal() -> None:
    text = f"The ID {SA_ID} is on the form."
    found = main.pii_module().detect(text)
    assert found["matches"]
    assert "[SA_ID_1]" in found["text"]
    assert SA_ID not in found["text"]


class _Explode:
    def acquire(self) -> None:
        raise AssertionError("this region must not touch the database")


@pytest.mark.asyncio
async def test_us_east_stores_nothing_for_a_za_home_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.setattr(main, "pool", lambda: _Explode())
    monkeypatch.setattr(main, "_http", _Transport())
    monkeypatch.setattr(main.httpx, "AsyncClient", _Provider)
    req = main.RouteRequest(
        tenant_id=uuid.uuid4(),
        home_region="za",
        messages=[main.Message(role="user", content=f"Draft around ID {SA_ID}.")],
    )
    with pytest.raises(HTTPException) as caught:
        await main.run_route(req)
    assert caught.value.status_code == 403
    assert caught.value.detail == main.ZA_HOME_MESSAGE
    assert SA_ID not in str(caught.value.detail)


@pytest.mark.asyncio
async def test_za_stores_nothing_for_a_us_home_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TANK_REGION", "za")
    monkeypatch.setattr(main, "pool", lambda: _Explode())
    monkeypatch.setattr(main, "_http", _Transport())
    monkeypatch.setattr(main.httpx, "AsyncClient", _Provider)
    req = main.RouteRequest(
        tenant_id=uuid.uuid4(),
        home_region="us-east",
        messages=[main.Message(role="user", content="Draft a supply agreement.")],
    )
    with pytest.raises(HTTPException) as caught:
        await main.run_route(req)
    assert caught.value.status_code == 403
    assert caught.value.detail == main.US_HOME_MESSAGE


@pytest.mark.asyncio
async def test_za_identifier_prompt_never_calls_a_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TANK_REGION", "za")
    monkeypatch.delenv("ZA_HOSTED_MODELS", raising=False)
    monkeypatch.setattr(main, "pool", lambda: _Explode())

    class _Client:
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise AssertionError("provider was called")

    monkeypatch.setattr(main.httpx, "AsyncClient", _Client)
    req = main.RouteRequest(
        tenant_id=uuid.UUID(TENANT),
        home_region="za",
        messages=[main.Message(role="user", content=f"Please file this ID {SA_ID}.")],
    )
    with pytest.raises(HTTPException) as caught:
        await main.run_route(req)
    assert caught.value.status_code == 403
    assert caught.value.detail == main.IDENTIFIER_REFUSAL
    assert SA_ID not in str(caught.value.detail)
    upload = main.RouteRequest(
        tenant_id=uuid.UUID(TENANT),
        home_region="za",
        task_type="zenas.draft",
        messages=[main.Message(role="user", content=f"Revise this clause for ID {SA_ID}.")],
    )
    with pytest.raises(HTTPException) as client:
        await main.run_route(upload)
    assert client.value.status_code == 403
    assert client.value.detail == main.IDENTIFIER_REFUSAL
    public = main.RouteRequest(
        tenant_id=uuid.UUID(TENANT),
        home_region="za",
        agent="zenas",
        task_type="zenas.case_facts",
        messages=[main.Message(role="user", content=f"Judgment. The ID {SA_ID} is in the reasons.")],
    )
    with pytest.raises(HTTPException) as named:
        await main.run_route(public)
    assert named.value.status_code == 403
    assert named.value.detail == main.IDENTIFIER_REFUSAL
    assert SA_ID not in str(named.value.detail)


@pytest.mark.asyncio
async def test_task_and_skill_refuse_a_foreign_home_before_a_write(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.setattr(main, "pool", lambda: _Explode())
    body = main.TaskCreate(
        tenant_id=uuid.uuid4(),
        title="A matter",
        home_region="za",
        messages=[main.Message(role="user", content="Hello")],
    )
    with pytest.raises(HTTPException) as caught:
        await main.create_task(body)
    assert caught.value.detail == main.ZA_HOME_MESSAGE
    skill = main.SkillRun(tenant_id=uuid.uuid4(), input={"text": "Hello"}, home_region="za")
    with pytest.raises(HTTPException) as caught:
        await main.run_one_skill("zenas.pii", skill, caller=None)
    assert caught.value.detail == main.ZA_HOME_MESSAGE


class _Provider:
    """Raised if a model client is constructed."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("provider was called")


class _Transport:
    """Raised if Redis or an already-open HTTP client is used."""

    async def request(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("http was called")

    async def get(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("http was called")

    async def post(self, *_args: object, **_kwargs: object) -> None:
        raise AssertionError("http was called")


@pytest.mark.asyncio
@pytest.mark.parametrize("box", ["us-east", "za"])
@pytest.mark.parametrize("home", ["", "eu"])
@pytest.mark.parametrize("kind", ["route", "task", "skill"])
async def test_empty_or_unknown_home_makes_no_call(
    monkeypatch: pytest.MonkeyPatch, box: str, home: str | None, kind: str,
) -> None:
    monkeypatch.setenv("TANK_REGION", box)
    monkeypatch.setattr(main, "pool", lambda: _Explode())
    monkeypatch.setattr(main, "_http", _Transport())
    monkeypatch.setattr(main, "_redis", _Transport())
    monkeypatch.setattr(main.httpx, "AsyncClient", _Provider)
    tenant = uuid.uuid4()
    if kind == "route":
        call = main.run_route(main.RouteRequest(
            tenant_id=tenant,
            home_region=home,
            messages=[main.Message(role="user", content="Hello")],
        ))
    elif kind == "task":
        call = main.create_task(main.TaskCreate(
            tenant_id=tenant,
            title="A matter",
            home_region=home,
            messages=[main.Message(role="user", content="Hello")],
        ))
    else:
        call = main.run_one_skill(
            "zenas.pii",
            main.SkillRun(tenant_id=tenant, input={"text": "Hello"}, home_region=home),
            caller=None,
        )
    with pytest.raises(HTTPException) as caught:
        await call
    assert caught.value.status_code == 403
    assert caught.value.detail == main.HOME_REQUIRED


class _Conn:
    async def fetchrow(self, *_args: object, **_kwargs: object) -> dict[str, object] | None:
        if "agent_skill_submissions" in str(_args[0]):
            return None
        return {
            "id": uuid.uuid4(),
            "model": "luna",
            "priority": "standard",
            "rung": 1,
            "max_tokens_out": 32,
            "system_prompt": None,
            "cache_scope": "none",
        }

    async def fetchval(self, sql: str, *_args: object, **_kwargs: object) -> str | bool:
        if "tank.controls" in sql:
            return False  # Paid work is enabled in this routing fixture.
        return "candidate"

    async def execute(self, *_args: object, **_kwargs: object) -> str:
        return "INSERT 0 1"

    async def __aenter__(self) -> "_Conn":
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False


class _Pool:
    def acquire(self) -> _Conn:
        return _Conn()


class _Answer:
    status_code = 200
    headers = {"content-type": "application/json", "x-litellm-response-cost": "0"}
    text = "Value added tax."

    def json(self) -> dict[str, object]:
        return {"choices": [{"message": {"content": self.text}}], "usage": {}}


class _Gateway:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    async def __aenter__(self) -> "_Gateway":
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def post(self, *_args: object, **_kwargs: object) -> _Answer:
        return _Answer()


@pytest.mark.asyncio
async def test_a_request_with_no_home_is_accepted_on_us_east(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TANK_REGION", "us-east")
    monkeypatch.setattr(main, "pool", lambda: _Pool())
    monkeypatch.setattr(main, "_redis", None)
    monkeypatch.setattr(main.httpx, "AsyncClient", _Gateway)
    seen: dict[str, str | None] = {}

    async def remember_task(_task_id: uuid.UUID, req: main.RouteRequest) -> None:
        seen["task_home"] = req.home_region

    async def remember_skill(_skill_id: str, _body: main.SkillRun, _caller: str | None) -> dict[str, bool]:
        seen["skill_home"] = main._skill_home.get()
        return {"ok": True}

    monkeypatch.setattr(main, "_run_task", remember_task)
    monkeypatch.setattr(main, "_run_one_skill", remember_skill)
    tenant = uuid.uuid4()
    response = await main.run_route(main.RouteRequest(
        tenant_id=tenant,
        messages=[main.Message(role="user", content="What does VAT stand for?")],
    ))
    assert response.content == "Value added tax."
    await main.create_task(main.TaskCreate(
        tenant_id=tenant,
        title="A question",
        messages=[main.Message(role="user", content="Hello")],
    ))
    await asyncio.gather(*list(main._background))
    await main.run_one_skill(
        "tier0.answer",
        main.SkillRun(tenant_id=tenant, input={"text": "Hello"}),
        caller=None,
    )
    assert seen["task_home"] == "us-east"
    assert seen["skill_home"] == "us-east"


@pytest.mark.asyncio
async def test_evals_pass_for_a_skill_that_calls_a_model(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TANK_REGION", "us-east")
    folder = tmp_path / "demo.echo" / "1.0.0"
    (folder / "evals").mkdir(parents=True)
    (folder / "run.py").write_text(
        "async def run(payload, ctx):\n"
        "    text = await ctx.model([{'role': 'user', 'content': payload['text']}], task_type='tier0.answer')\n"
        "    return {'text': text}\n",
        encoding="utf-8",
    )
    (folder / "evals" / "cases.jsonl").write_text(
        '{"input": {"text": "What does VAT stand for?"}, "expected": {"text": "value added tax"}, "tolerance": "contains"}\n',
        encoding="utf-8",
    )
    pkg = main.skala.SkillPackage(
        id="demo.echo",
        version="1.0.0",
        agent="tier0",
        rung=1,
        task_type="tier0.answer",
        description="",
        input_schema={},
        output_schema={},
        eval_threshold=1.0,
        path=folder,
        cases=main.skala._load_cases(folder),
    )
    monkeypatch.setattr(main, "get_package", lambda _skill_id, _version: pkg)
    monkeypatch.setattr(main, "pool", lambda: _Pool())
    monkeypatch.setattr(main, "_redis", None)
    monkeypatch.setattr(main, "_http", object())
    monkeypatch.setattr(main.httpx, "AsyncClient", _Gateway)
    homes: list[str | None] = []
    real = main.run_route

    async def watch(req: main.RouteRequest, task_id: uuid.UUID | None = None) -> main.RouteResponse:
        homes.append(req.home_region)
        return await real(req, task_id)

    monkeypatch.setattr(main, "run_route", watch)
    result = await main.run_skill_evals("demo.echo", "1.0.0", None)
    assert result["passed"] == 1
    assert result["total"] == 1
    assert result["gate"] == "failed"
    assert result["eligible"] is False
    preview = main.make_ctx(pkg, uuid.uuid4(), preview=True)
    await preview.model([{"role": "user", "content": "hi"}], task_type="tier0.answer")
    assert homes == ["us-east", "us-east"]


def _published_judgment() -> str:
    return (
        "The Constitutional Court dismissed the appeal on the sale of goods. "
        f"The published reasons record identity number {SA_ID} as it appears in the record."
    )


def _convert_prompt(judgment: str, citation: str = "2020 ZACC 1") -> str:
    return main._CONVERT_HEAD + citation + "\n\n" + judgment


class _CourtPool:
    """Tank's own read. A caller does not hand this object in."""

    def __init__(self, rows: list[dict[str, str]]) -> None:
        self.rows = rows
        self.fetches: list[tuple[object, ...]] = []

    def acquire(self) -> "_CourtPool":
        return self

    async def __aenter__(self) -> "_CourtPool":
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def fetch(self, sql: str, *args: object) -> list[dict[str, str]]:
        self.fetches.append((sql, args))
        text = str(args[0])
        sources = set(args[1])  # type: ignore[arg-type]
        return [
            row for row in self.rows
            if row["source_id"] in sources and len(row["text"]) >= 40 and text.endswith(row["text"])
        ]

    async def fetchrow(self, *_args: object, **_kwargs: object) -> dict[str, object]:
        if "agent_skill_submissions" in str(_args[0]):
            return None
        return {
            "id": uuid.uuid4(),
            "model": "luna",
            "priority": "standard",
            "rung": 1,
            "max_tokens_out": 800,
            "system_prompt": None,
            "cache_scope": "none",
        }

    async def fetchval(self, sql: str, *_args: object) -> bool:
        assert "tank.controls" in sql
        return False

    async def execute(self, *_args: object, **_kwargs: object) -> str:
        return "INSERT 0 1"


class _SeenGateway:
    def __init__(self, *_args: object, **_kwargs: object) -> None:
        self.sent: list[dict[str, object]] = []

    async def __aenter__(self) -> "_SeenGateway":
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        return False

    async def post(self, *_args: object, **kwargs: object) -> _Answer:
        body = kwargs.get("json")
        if isinstance(body, dict):
            self.sent.append(body)
        return _Answer()


def _key_request(path: str) -> object:
    from starlette.requests import Request

    return Request({
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 1234),
        "server": ("test", 80),
    })


def test_tank_wrappers_match_the_zenas_pool_read() -> None:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from agents.zenas.core.convert import _PROMPT_HEAD
    from agents.zenas.core.release_mask import COURT_SOURCES
    from agents.zenas.core.service import FACTS_PROMPT_PREFIX

    assert main._COURT_SOURCES == COURT_SOURCES
    assert main._CONVERT_HEAD == _PROMPT_HEAD
    assert main._FACTS_PREFIX == FACTS_PROMPT_PREFIX


@pytest.mark.asyncio
async def test_only_the_zenas_key_and_a_real_pool_row_skip_the_identifier_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TANK_REGION", "za")
    monkeypatch.delenv("ZA_HOSTED_MODELS", raising=False)
    monkeypatch.delenv("TANK_PROVIDER_ALLOW", raising=False)
    monkeypatch.setattr(main, "_pool", None)
    monkeypatch.setattr(main, "_agent_keys_synced", False)
    monkeypatch.setenv("TANK_KEY_ZENAS", "zenas-room-secret")
    monkeypatch.setenv("TANK_KEY_TIGER", "tiger-room-secret")
    route = _key_request("/v1/route")
    assert await main.require_key(route, main.TANK_API_KEY) is None
    assert await main.require_key(route, "zenas-room-secret") == "zenas"
    assert await main.require_key(route, "tiger-room-secret") == "tiger"

    judgment = _published_judgment()
    court = _CourtPool([{"source_id": "concourt", "text": judgment, "citation": "2020 ZACC 1"}])
    gate = _SeenGateway()
    monkeypatch.setattr(main, "pool", lambda: court)
    monkeypatch.setattr(main, "_redis", None)
    monkeypatch.setattr(main.httpx, "AsyncClient", lambda *_a, **_k: gate)
    client = (
        "Please advise our client. The identity number "
        f"{SA_ID} is on the instruction."
    )
    stored = main.RouteRequest(
        tenant_id=uuid.UUID(TENANT),
        home_region="za",
        agent="tiger",
        task_type="zenas.case_facts",
        messages=[main.Message(role="user", content=_convert_prompt(judgment))],
    )
    delivered = await main.route(stored, caller="zenas")
    assert delivered.content == "Value added tax."
    assert gate.sent
    assert judgment in str(gate.sent[0]["messages"])
    assert court.fetches
    assert "zenas_pool.documents" in str(court.fetches[0][0])

    async def refused(req: main.RouteRequest, caller: str | None) -> None:
        before = len(gate.sent)
        with pytest.raises(HTTPException) as caught:
            await main.route(req, caller=caller)
        assert caught.value.status_code == 403
        assert caught.value.detail == main.IDENTIFIER_REFUSAL
        assert SA_ID not in str(caught.value.detail)
        assert len(gate.sent) == before

    spoofed = stored.model_copy(update={"agent": "zenas"})
    await refused(spoofed, None)
    await refused(stored, "tiger")
    await refused(
        main.RouteRequest(
            tenant_id=uuid.UUID(TENANT),
            home_region="za",
            task_type="zenas.case_facts",
            messages=[main.Message(role="user", content=client)],
        ),
        "zenas",
    )
    await refused(
        main.RouteRequest(
            tenant_id=uuid.UUID(TENANT),
            home_region="za",
            task_type="zenas.case_facts",
            messages=[main.Message(role="user", content=_convert_prompt(judgment) + f"\nAlso note ID {SA_ID}.")],
        ),
        "zenas",
    )
    await refused(
        main.RouteRequest(
            tenant_id=uuid.UUID(TENANT),
            home_region="za",
            task_type="zenas.case_facts",
            messages=[main.Message(role="user", content="Summarise this case.\n\n" + judgment)],
        ),
        "zenas",
    )
    await refused(
        main.RouteRequest(
            tenant_id=uuid.UUID(TENANT),
            home_region="za",
            task_type="zenas.case_facts",
            messages=[main.Message(role="user", content=_convert_prompt(judgment, citation=f"Note ID {SA_ID}"))],
        ),
        "zenas",
    )
    statute = _CourtPool([{"source_id": "client-upload", "text": judgment}])
    monkeypatch.setattr(main, "pool", lambda: statute)
    await refused(stored, "zenas")
    facts = main.RouteRequest(
        tenant_id=uuid.UUID(TENANT),
        home_region="za",
        task_type="zenas.case_facts",
        messages=[main.Message(role="user", content=main._FACTS_PREFIX + judgment)],
    )
    monkeypatch.setattr(main, "pool", lambda: court)
    again = await main.route(facts, caller="zenas")
    assert again.content == "Value added tax."


@pytest.mark.asyncio
async def test_a_failed_pool_read_does_not_skip_the_rule(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("TANK_REGION", "za")
    monkeypatch.delenv("ZA_HOSTED_MODELS", raising=False)

    class _Broken:
        def acquire(self) -> "_Broken":
            return self

        async def __aenter__(self) -> "_Broken":
            return self

        async def __aexit__(self, *_exc: object) -> bool:
            return False

        async def fetch(self, *_args: object, **_kwargs: object) -> list[dict[str, str]]:
            raise RuntimeError(f"driver said {SA_ID}")

    monkeypatch.setattr(main, "pool", lambda: _Broken())
    monkeypatch.setattr(main.httpx, "AsyncClient", _Provider)
    judgment = _published_judgment()
    req = main.RouteRequest(
        tenant_id=uuid.UUID(TENANT),
        home_region="za",
        task_type="zenas.case_facts",
        messages=[main.Message(role="user", content=_convert_prompt(judgment))],
    )
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(HTTPException) as caught:
            await main.run_route(req, caller="zenas")
    assert caught.value.detail == main.IDENTIFIER_REFUSAL
    assert SA_ID not in str(caught.value.detail)
    assert SA_ID not in caplog.text


@pytest.mark.asyncio
async def test_skala_run_never_skips_the_identifier_rule(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    monkeypatch.setenv("TANK_REGION", "za")
    monkeypatch.delenv("ZA_HOSTED_MODELS", raising=False)
    judgment = _published_judgment()
    folder = tmp_path / "zenas.case_facts" / "1.0.0"
    folder.mkdir(parents=True)
    (folder / "run.py").write_text(
        "async def run(payload, ctx):\n"
        "    text = await ctx.model(\n"
        "        [{'role': 'user', 'content': payload['text']}],\n"
        "        task_type='zenas.case_facts',\n"
        "    )\n"
        "    return {'text': text}\n",
        encoding="utf-8",
    )
    pkg = main.skala.SkillPackage(
        id="zenas.case_facts",
        version="1.0.0",
        agent="zenas",
        rung=1,
        task_type="zenas.case_facts",
        description="",
        input_schema={},
        output_schema={},
        eval_threshold=1.0,
        path=folder,
        cases=[],
    )
    court = _CourtPool([{"source_id": "concourt", "text": judgment, "citation": "2020 ZACC 1"}])
    gate = _SeenGateway()
    monkeypatch.setattr(main, "pool", lambda: court)
    monkeypatch.setattr(main, "_redis", None)
    monkeypatch.setattr(main, "_http", object())
    monkeypatch.setattr(main, "get_package", lambda *_a, **_k: pkg)
    monkeypatch.setattr(main.httpx, "AsyncClient", lambda *_a, **_k: gate)

    async def approved(*_args: object, **_kwargs: object) -> str:
        return "approved"

    monkeypatch.setattr(main, "skill_state", approved)
    body = main.SkillRun(
        tenant_id=uuid.UUID(TENANT),
        home_region="za",
        input={"text": _convert_prompt(judgment)},
        version="1.0.0",
    )
    for caller in (None, "zenas"):
        with pytest.raises(HTTPException) as caught:
            await main._run_one_skill("zenas.case_facts", body, caller)
        assert caught.value.status_code == 403
        assert caught.value.detail == main.IDENTIFIER_REFUSAL
        assert SA_ID not in str(caught.value.detail)
    assert gate.sent == []


@pytest.mark.asyncio
async def test_cases_facts_refuses_judgment_text_from_the_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TANK_REGION", "za")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from agents.zenas import app as zapp

    client = f"Our client, identity number {SA_ID}, wants this contract reviewed."
    court_text = "The court dismissed the appeal on a sale of goods between two companies."
    used: list[dict[str, str]] = []

    async def extract(*_args: object, **kwargs: object) -> dict[str, bool]:
        used.append({
            "judgment": str(kwargs.get("judgment") or ""),
            "source_id": str(kwargs.get("source_id") or ""),
        })
        return {"ok": True}

    async def refuse_body(source_id: str, text: str) -> None:
        async def row(_pool_doc_id: str) -> dict[str, str]:
            return {"source_id": source_id, "text": text, "citation": "2020 ZACC 1"}

        monkeypatch.setattr(zapp, "_pool_case_row", row)
        body = zapp.CaseFactsIn(
            tenant_id=uuid.UUID(TENANT),
            home_region="za",
            jurisdiction="za",
            pool_doc_id="doc-1",
            source_id="concourt",
            judgment=client,
        )
        with pytest.raises(HTTPException) as caught:
            await zapp.post_case_facts(body)
        assert caught.value.status_code == 403
        assert caught.value.detail == main.IDENTIFIER_REFUSAL
        assert SA_ID not in str(caught.value.detail)

    async def ready() -> object:
        return object()

    zapp.app.state.tank = object()
    monkeypatch.setattr(zapp, "extract_case_facts", extract)
    monkeypatch.setattr(zapp, "_ready", ready)
    monkeypatch.setattr(zapp, "_model", lambda _tenant: object())
    await refuse_body("concourt", court_text)

    async def missing(_pool_doc_id: str) -> None:
        return None

    monkeypatch.setattr(zapp, "_pool_case_row", missing)
    gone = zapp.CaseFactsIn(
        tenant_id=uuid.UUID(TENANT),
        home_region="za",
        jurisdiction="za",
        pool_doc_id="doc-1",
        source_id="concourt",
        judgment=client,
    )
    with pytest.raises(HTTPException) as caught:
        await zapp.post_case_facts(gone)
    assert caught.value.detail == main.IDENTIFIER_REFUSAL
    await refuse_body("client-upload", court_text + " " + client)
    assert used == []

    async def court(_pool_doc_id: str) -> dict[str, str]:
        return {"source_id": "sca", "text": court_text, "citation": "2020 ZASCA 1"}

    monkeypatch.setattr(zapp, "_pool_case_row", court)
    loaded = await zapp.post_case_facts(gone.model_copy(update={"judgment": "", "source_id": "concourt"}))
    assert loaded["ok"] is True
    assert used == [{"judgment": court_text, "source_id": "sca"}]

