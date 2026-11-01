"""Actual dispatch metadata only; all upstream calls are offline doubles."""
import json
from uuid import uuid4

import httpx
import pytest

from execution_receipt import capture
from chassis.tank import TankClient
from test_tank_tenant_boundaries import boundary  # noqa: F401
from test_tank_ladder import ladder, policy, request  # noqa: F401


def receipt(**changes):
    fields = dict(ledger_id=str(uuid4()), tenant_id=str(uuid4()), task_type="moot.counsel", requested_model="route-alias",
        answered_model="actual-group", dispatched={"max_tokens": 64}, headers={"x-litellm-model-group": "actual-group"},
        response={"model": "actual-native-version", "messages": "secret", "api_key": "secret"}, delivered=True)
    fields.update(changes)
    return capture(**fields)


def test_dispatch_hash_is_audit_only_even_with_actual_model_evidence():
    first, second = receipt(), receipt()
    assert first["dispatched_settings_hash"] == second["dispatched_settings_hash"]
    assert first["settings_hash"] is None and first["settings_status"] == "upstream_effective_settings_unavailable"
    assert first["upstream_model"] == "actual-native-version" and first["upstream_model_group"] == "actual-group"
    assert "secret" not in json.dumps(first) and "api_key" not in json.dumps(first)
    assert receipt(dispatched={"max_tokens": 32})["dispatched_settings_hash"] != first["dispatched_settings_hash"]
    assert receipt(requested_model="other-alias")["dispatched_settings_hash"] != first["dispatched_settings_hash"]
    assert receipt(headers={}, response={})["upstream_model"] is None


@pytest.mark.parametrize("settings", [{"max_tokens": float("nan")}, {"max_tokens": 64, "api_key": "never-hash"}, {"stop": ["private-data"]}])
def test_unknown_or_sensitive_controls_are_not_fingerprinted(settings):
    result = receipt(dispatched=settings)
    assert result["dispatched_settings_hash"] is result["settings_hash"] is None
    assert "never-hash" not in json.dumps(result) and "private-data" not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("tamper", [None, "tenant_id", "task_type", "ledger_id", "model", "settings_hash"])
async def test_chassis_preserves_receipt_and_checks_actual_call_binding(tamper):
    execution = receipt()
    if tamper:
        execution[tamper] = "different-call"
    async def transport(req):
        return httpx.Response(200, json={"ledger_id": execution["ledger_id"] if tamper != "ledger_id" else "other-ledger",
            "model": "actual-group", "settings_hash": None, "execution": execution})
    tenant = execution["tenant_id"] if tamper != "tenant_id" else str(uuid4())
    async with httpx.AsyncClient(transport=httpx.MockTransport(transport)) as http:
        client = TankClient("http://offline", "offline-test-key", "zenas", http)
        if tamper:
            with pytest.raises(RuntimeError, match="receipt|attestation"):
                await client.route(tenant, "moot.counsel", [])
        else:
            result = await client.route(tenant, "moot.counsel", [])
            assert result["execution"] == execution and result["settings_hash"] is None


@pytest.mark.asyncio
async def test_actual_route_receipt_after_escalation_and_cache_remain_distinct(ladder, monkeypatch):  # noqa: F811
    b = ladder
    tenant = b.tenants[0]
    await policy(b, tenant, model="route-alias", rung=1, cache_scope="tenant", semantic_cache=False)
    sent = []
    class Provider:
        def __init__(self, *args, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            sent.append(kwargs["json"])
            return httpx.Response(200, headers={"content-type": "application/json", "x-litellm-model-group": "actual-group", "x-litellm-response-cost": "0.001"},
                json={"model": "native-version", "choices": [{"message": {"content": "Supported independent answer"}}], "usage": {}}, request=httpx.Request("POST", url))
    monkeypatch.setattr(b.tank.httpx, "AsyncClient", Provider)
    result = await b.tank.run_route(request(b, tenant, text="Public independent material"))
    execution = result.execution
    assert execution["ledger_id"] == str(result.ledger_id) and execution["tenant_id"] == str(tenant)
    assert execution["task_type"] == "base.normalize" and result.model == execution["model"] == "actual-group"
    assert execution["upstream_model"] == "native-version" and result.settings_hash is None
    expected = receipt(requested_model=sent[0]["model"], dispatched={k: v for k, v in sent[0].items() if k not in ("model", "messages")})
    assert execution["dispatched_settings_hash"] == expected["dispatched_settings_hash"]
    cached = await b.tank.run_route(request(b, tenant, text="Public independent material"))
    assert cached.rung == 4 and cached.execution is cached.settings_hash is None and len(sent) == 1
    # Actual code-to-model escalation fingerprints the final dispatched settings.
    await policy(b, b.tenants[1], confidence_floor=1)
    escalated = await b.tank.run_route(request(b, b.tenants[1]))
    assert escalated.rung == 2 and escalated.escalation
    assert escalated.execution["requested_model"] == sent[-1]["model"]
