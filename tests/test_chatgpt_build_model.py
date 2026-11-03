"""ChatGPT sign-in is a build-only model: platform tenant and TANK_BUILD_TENANTS only.

No database, no network, no model. See docs/ops/CHATGPT-BUILD-MODEL.md.
"""
from __future__ import annotations

import os
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
PLATFORM = "00000000-0000-0000-0000-000000000001"
CUSTOMER = "11111111-1111-1111-1111-111111111111"
CONFIGS = ["config.yaml", "config.za.yaml"]


def _config(name: str) -> dict:
    return yaml.safe_load((ROOT / "litellm" / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", CONFIGS)
def test_build_chatgpt_is_listed_and_every_chatgpt_entry_is_build_only(name: str) -> None:
    rows = _config(name)["model_list"]
    chatgpt = [r for r in rows if str(r["litellm_params"]["model"]).startswith("chatgpt/")]
    assert [r["model_name"] for r in chatgpt] == ["build-chatgpt"]
    for row in chatgpt:
        assert row["model_name"].startswith(main.BUILD_MODEL_PREFIX)
        assert row["model_info"]["build_only"] is True
        assert "api_key" not in row["litellm_params"]
    for row in rows:
        if row["model_name"].startswith(main.BUILD_MODEL_PREFIX):
            assert str(row["litellm_params"]["model"]).startswith("chatgpt/")


@pytest.mark.parametrize("name", CONFIGS)
def test_no_fallback_chain_reaches_or_leaves_a_build_model(name: str) -> None:
    for entry in _config(name)["litellm_settings"]["fallbacks"]:
        for source, chain in entry.items():
            assert not source.startswith("build-")
            assert not any(str(model).startswith("build-") for model in chain)


@pytest.mark.parametrize("compose,volume", [("docker-compose.yml", "litellm_chatgpt_token"),
                                            ("docker-compose.za.yml", "za_litellm_chatgpt_token")])
def test_token_volume_is_named_writable_and_persistent(compose: str, volume: str) -> None:
    data = yaml.safe_load((ROOT / compose).read_text(encoding="utf-8"))
    litellm = data["services"]["litellm"]
    assert litellm["environment"]["CHATGPT_TOKEN_DIR"] == "/var/lib/litellm-chatgpt"
    assert f"{volume}:/var/lib/litellm-chatgpt" in litellm["volumes"]  # no :ro
    assert volume in data["volumes"]
    assert "TANK_BUILD_TENANTS" in data["services"]["tank"]["environment"]
    for name, service in data["services"].items():
        if name != "litellm":
            assert not any(volume in str(v) for v in service.get("volumes") or []), name


def test_dockerfile_owns_the_token_dir_for_the_runtime_user() -> None:
    text = (ROOT / "litellm" / "Dockerfile").read_text(encoding="utf-8")
    assert "chown tervory:tervory /home/tervory /var/lib/litellm-chatgpt" in text
    assert "ENV CHATGPT_TOKEN_DIR=/var/lib/litellm-chatgpt" in text


@pytest.mark.parametrize("box", ["us-east", "za"])
def test_customer_tenant_is_refused_platform_is_not(box: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TANK_BUILD_TENANTS", raising=False)
    text = "What does section 12 require?"
    assert main.model_call_refusal(text, "build-chatgpt", box=box, tenant_id=CUSTOMER) == main.BUILD_ONLY_REFUSAL
    assert main.model_call_refusal(text, "BUILD-chatgpt", box=box, tenant_id=CUSTOMER) == main.BUILD_ONLY_REFUSAL
    assert main.model_call_refusal(text, "build-chatgpt", box=box, tenant_id=PLATFORM) is None
    assert main.model_call_refusal(text, "luna", box=box, tenant_id=CUSTOMER) is None


def test_customer_allow_list_cannot_open_the_wall(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TANK_PROVIDER_ALLOW", '{"%s":["build-chatgpt"]}' % CUSTOMER)
    assert main.model_call_refusal("hi", "build-chatgpt", box="us-east", tenant_id=CUSTOMER) == main.BUILD_ONLY_REFUSAL


def test_build_tenants_env_adds_internal_test_tenants(monkeypatch: pytest.MonkeyPatch) -> None:
    other = str(uuid.uuid4())
    monkeypatch.setenv("TANK_BUILD_TENANTS", f" {other.upper()} ,")
    assert main.model_call_refusal("hi", "build-chatgpt", box="us-east", tenant_id=other) is None
    assert main.model_call_refusal("hi", "build-chatgpt", box="us-east", tenant_id=CUSTOMER) == main.BUILD_ONLY_REFUSAL


def test_za_identifier_rule_still_applies_to_the_build_model() -> None:
    text = "Client ID 8001015009087 asks about eviction."
    assert main.model_call_refusal(text, "build-chatgpt", box="za", tenant_id=PLATFORM) == main.IDENTIFIER_REFUSAL


def _no_pool() -> None:
    raise AssertionError("policy was written")


@pytest.mark.asyncio
@pytest.mark.parametrize("fields", [
    {"tenant_id": None},
    {"tenant_id": CUSTOMER},
    {"tenant_id": PLATFORM, "batch_eligible": True},
    {"tenant_id": PLATFORM, "cache_scope": "tenant"},
    {"tenant_id": PLATFORM, "semantic_cache": True},
])
async def test_put_policy_keeps_build_model_off_customer_rows(monkeypatch: pytest.MonkeyPatch, fields: dict) -> None:
    monkeypatch.delenv("TANK_BUILD_TENANTS", raising=False)
    monkeypatch.setattr(main, "pool", _no_pool)
    for key in ("model", "escalation_model"):
        names = {"model": "luna", key: "build-chatgpt"}
        body = main.PolicyRow(task_type="zenas.rule_card", **names, **fields)
        with pytest.raises(HTTPException) as caught:
            await main.put_policy("zenas.rule_card", body)
        assert caught.value.status_code == 403


@pytest.mark.asyncio
async def test_put_policy_allows_the_platform_tenant_row(monkeypatch: pytest.MonkeyPatch) -> None:
    written: list = []

    class _Conn:
        async def execute(self, *args):
            written.append(args)

    class _Acquire:
        async def __aenter__(self):
            return _Conn()

        async def __aexit__(self, *_):
            return False

    class _Pool:
        def acquire(self):
            return _Acquire()

    monkeypatch.setattr(main, "pool", lambda: _Pool())
    body = main.PolicyRow(task_type="zenas.rule_card", tenant_id=PLATFORM, model="build-chatgpt", max_tokens_out=4096)
    assert await main.put_policy("zenas.rule_card", body) == {"ok": True}
    assert written and written[0][4] == "build-chatgpt"


@pytest.mark.asyncio
async def test_build_models_are_not_on_the_roster(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "_roster_cache", None)
    monkeypatch.setattr(main, "_http", None)
    monkeypatch.setattr(main, "_roster_path", lambda: ROOT / "litellm" / "config.yaml")
    names = {row["model_name"] for row in await main._roster_models()}
    assert "luna" in names
    assert not any(name.startswith("build-") for name in names)
    assert main._build_row({"model_name": "anything", "litellm_params": {"model": "chatgpt/gpt-6-luna"}})


@pytest.mark.asyncio
async def test_live_roster_drops_build_models(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        status_code = 200

        def json(self):
            return {"data": [
                {"model_name": "luna", "litellm_params": {"model": "openai/gpt-6-luna"}, "model_info": {}},
                {"model_name": "build-chatgpt", "litellm_params": {"model": "chatgpt/gpt-6.1-sol"}, "model_info": {}},
                {"model_name": "sneaky", "litellm_params": {"model": "chatgpt/gpt-6-luna"}, "model_info": {}},
            ]}

    class _Http:
        async def get(self, *_a, **_k):
            return _Resp()

    monkeypatch.setattr(main, "_roster_cache", None)
    monkeypatch.setattr(main, "_http", _Http())
    assert [row["model_name"] for row in await main._roster_models()] == ["luna"]


@pytest.mark.asyncio
async def test_shadow_and_cache_never_use_a_build_model() -> None:
    with pytest.raises(RuntimeError):
        await main._llm("build-chatgpt", [{"role": "user", "content": "hi"}], 10)
    # The cache stays off because put_policy only takes a build model with
    # cache_scope "none" (tested above); _cache_write itself is frozen by
    # tests/test_tenant_rls.py.


@pytest.mark.asyncio
async def test_build_model_cannot_be_a_graduation_candidate(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Conn:
        async def fetchrow(self, *_a):
            return {"model": "luna"}

        async def execute(self, *_a):
            raise AssertionError("candidate was written")

    class _Acquire:
        async def __aenter__(self):
            return _Conn()

        async def __aexit__(self, *_):
            return False

    monkeypatch.setattr(main, "pool", lambda: type("P", (), {"acquire": lambda self: _Acquire()})())
    body = main.CandidateBody(candidate_model="build-chatgpt", shadow_rate=0.1, by="test")
    with pytest.raises(HTTPException) as caught:
        await main.set_candidate("zenas.rule_card", body)
    assert caught.value.status_code == 403


def test_semantic_cache_schedule_skips_build_models() -> None:
    import semantic_cache

    class _Rt:
        _background: set = set()

    semantic_cache.schedule(_Rt(), None, {"model": "build-chatgpt"}, ("a", "b", "c"), [], object(), uuid.uuid4(), "x", 0.0)
    assert not _Rt._background


@pytest.mark.asyncio
async def test_bench_refuses_build_models() -> None:
    import bench

    with pytest.raises(ValueError):
        await bench.call_model("build-chatgpt", [], 10)


def test_doc_covers_sign_in_switch_and_revoke() -> None:
    doc = (ROOT / "docs" / "ops" / "CHATGPT-BUILD-MODEL.md").read_text(encoding="utf-8")
    for needle in ("Authenticator().get_access_token()", "auth.openai.com/codex/device",
                   "PUT", "DELETE", "## Revoke", "rm /var/lib/litellm-chatgpt/auth.json"):
        assert needle in doc
