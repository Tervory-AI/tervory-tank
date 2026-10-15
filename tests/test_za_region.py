"""South Africa region: own stack, and Tank refuses the other region's tenants.

No database, no network, no model. The compose file is checked as YAML.
A foreign home region returns before any write. An identifier in a za prompt
is refused for every provider that is not running in South Africa.
"""
from __future__ import annotations

import os
import re
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


def test_za_compose_is_a_zenas_stack_with_its_own_stores() -> None:
    data = _parsed()
    assert set(data["services"]) == {
        "postgres", "redis", "qdrant", "hermes", "litellm", "tank", "agent-roles", "agent-zenas",
    }
    assert "pool-loader" not in data["services"]
    assert "Thread A — pool-loader" in COMPOSE
    for name, service in data["services"].items():
        assert service["environment"]["TANK_REGION"] == "za", name
    assert data["networks"]["default"]["name"] == "tervory-za"
    assert data["networks"]["tervory-gw-zenas"]["name"] == "tervory-gw-zenas"
    assert "external" not in data["networks"]["default"]
    assert "external" not in data["networks"]["tervory-gw-zenas"]
    assert set(data["volumes"]) == {
        "za_pgdata", "za_redisdata", "za_qdrantdata", "za_agent_data", "za_backups",
    }
    assert data["services"]["agent-zenas"]["networks"] == ["tervory-gw-zenas"]
    assert "tervory-gw-zenas" in data["services"]["postgres"]["networks"]
    assert "tervory-gw-zenas" in data["services"]["tank"]["networks"]
    assert "tervory-gw-zenas" in data["services"]["hermes"]["networks"]
    assert data["services"]["tank"]["environment"]["ZENAS_AGENT_URL"] == "http://agent-zenas:8000"
    assert "/app/config.za.yaml" in data["services"]["litellm"]["command"]
    assert "za-api.tervory.com" in COMPOSE
    for service in data["services"].values():
        assert "ports" not in service


def test_za_compose_names_no_us_host_and_does_not_replicate() -> None:
    lowered = COMPOSE.lower()
    assert "us-east" not in lowered
    assert "boston" not in lowered
    assert "app.tervory.com" not in lowered
    assert "api.tervory.com" not in COMPOSE.replace("za-api.tervory.com", "")
    assert "replicaof" not in lowered
    assert "wal_level" not in lowered
    assert "primary_conninfo" not in lowered
    assert "external: true" not in lowered
    addresses = set(re.findall(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", COMPOSE))
    assert addresses <= {"127.0.0.1"}
    for banned in ("workspace", "searxng", "agent-base", "agent-tiger", "agent-rig", "deepseek", "moonshot"):
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
        provider = item["litellm_params"]["model"].split("/", 1)[0]
        assert provider not in {"deepseek", "moonshot"}
        assert "api_base" not in item["litellm_params"]
    assert main.sa_hosted_models() == frozenset()


def test_home_region_refusal_both_ways() -> None:
    assert main.home_region_refusal("za", "us-east") == main.ZA_HOME_MESSAGE
    assert main.home_region_refusal("us-east", "za") == main.US_HOME_MESSAGE
    assert main.home_region_refusal("us", "us-east") is None
    assert main.home_region_refusal("za", "za") is None
    assert main.home_region_refusal(None, "us-east") is None
    assert main.home_region_refusal("eu", "za") == "home region must be us-east or za"


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
    assert main.model_call_refusal("No identifier here.", "deepseek/chat", box="za", tenant_id=TENANT) == main.ALLOW_REFUSAL


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
