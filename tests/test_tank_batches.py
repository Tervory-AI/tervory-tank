"""Durable provider batches, normal retry caps and tenant isolation (real SQL)."""
import json
import uuid

import httpx
import pytest

from test_tank_tenant_boundaries import boundary  # noqa: F401 -- shared fixture
from test_tank_ladder import ladder, policy, request  # noqa: F401 -- fixture injection


@pytest.mark.asyncio
async def test_batch_results_receipts_and_owner_only_reads(ladder, monkeypatch):  # noqa: F811
    b = ladder
    monkeypatch.setenv("TANK_BATCH_MIN", "2")
    for tenant in b.tenants:
        await policy(b, tenant, model="luna", rung=1, batch_eligible=True)
    uploads = {}
    gateway_calls = []

    async def gateway(method, path, **kwargs):
        gateway_calls.append((method, path))
        if path == "/v1/files":
            rows = [json.loads(line) for line in kwargs["files"]["file"][1].decode().splitlines()]
            assert all(row["body"]["model"] == "gpt-6-luna" for row in rows)
            file_id = "file-" + uuid.uuid4().hex
            uploads[file_id] = rows
            return httpx.Response(200, json={"id": file_id})
        if path == "/v1/batches":
            assert kwargs["json"]["completion_window"] == "24h"
            return httpx.Response(200, json={"id": kwargs["json"]["input_file_id"]})
        if path.startswith("/v1/batches/"):
            return httpx.Response(200, json={"status": "completed", "output_file_id": path.rsplit("/", 1)[-1]})
        file_id = path.split("/")[3]
        return httpx.Response(200, text="\n".join(json.dumps({"custom_id": r["custom_id"], "response": {"status_code": 200,
            "body": {"choices": [{"message": {"content": "fixture result " + r["custom_id"]}}],
                     "usage": {"prompt_tokens": 100, "completion_tokens": 50}}}}) for r in uploads[file_id]))

    monkeypatch.setattr(b.tank, "_batch_gateway", gateway)
    batches = []
    for tenant in b.tenants:
        body = b.tank.BatchRequest(requests=[request(b, tenant, interactive=False, text="fixture " + str(i)) for i in range(2)])
        batches.append(body)
        queued = await b.tank.route_batch(body, None)
        assert queued["status"] == "queued" and queued["completion_window"] == "24h"
        assert (await b.tank.route_batch(body, None))["id"] == queued["id"]
    await b.tank.process_batches_once()
    await b.tank.process_batches_once()
    await b.tank.process_batches_once()  # idempotent after completion
    assert not b.sent and len([c for c in gateway_calls if c == ("POST", "/v1/batches")]) == 2
    for i, body in enumerate(batches):
        result = await b.tank.batch_status(body.id, b.tenants[i])
        assert result["status"] == "completed" and len(result["results"]) == 2
        for receipt in result["results"]:
            assert receipt["batch"] and receipt["ledger_id"] and receipt["content"]
            assert float(receipt["baseline_cost_usd"]) == pytest.approx(0.000035)
            assert float(receipt["cost_usd"]) == pytest.approx(0.000018, abs=0.000001)
            assert receipt["discount_usd"] > 0
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as denied:
            await b.tank.batch_status(body.id, b.tenants[1-i])
        assert denied.value.status_code == 404
    async with b.pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM tank.ledger WHERE batch") == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("interactive,eligible", [(True, True), (False, False)])
async def test_interactive_or_ineligible_work_never_enters_provider_batch(ladder, monkeypatch, interactive, eligible):  # noqa: F811
    b = ladder
    monkeypatch.setenv("TANK_BATCH_MIN", "2")
    for tenant in b.tenants:
        await policy(b, tenant, model="luna", rung=1, batch_eligible=eligible)
        result = await b.tank.route_batch(b.tank.BatchRequest(requests=[request(b, tenant, interactive=interactive) for _ in range(2)]), None)
        assert result["status"] == "completed" and not result["batch"]
    async with b.pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM tank.batches") == 0
    assert len(b.sent) == 4


@pytest.mark.asyncio
@pytest.mark.parametrize("cap,expected", [(1, "completed"), (0.0004, "failed")])
async def test_expired_batch_retries_once_inside_cap(ladder, monkeypatch, cap, expected):  # noqa: F811
    b = ladder
    monkeypatch.setenv("TANK_BATCH_MIN", "1")

    async def gateway(method, path, **kwargs):
        if path == "/v1/files":
            return httpx.Response(200, json={"id": "fixture-file"})
        if path == "/v1/batches":
            return httpx.Response(200, json={"id": "fixture-batch"})
        return httpx.Response(200, json={"status": "expired"})

    monkeypatch.setattr(b.tank, "_batch_gateway", gateway)
    bodies = []
    for tenant in b.tenants:
        await policy(b, tenant, model="luna", rung=1, batch_eligible=True, max_cost_usd=cap)
        body = b.tank.BatchRequest(requests=[request(b, tenant, interactive=False)])
        bodies.append(body)
        await b.tank.route_batch(body, None)
    await b.tank.process_batches_once()
    await b.tank.process_batches_once()
    await b.tank.process_batches_once()
    for body, tenant in zip(bodies, b.tenants):
        result = await b.tank.batch_status(body.id, tenant)
        assert result["status"] == expected
        receipt = result["results"][0]
        if expected == "completed":
            assert receipt["batch"] and receipt["discount_usd"] == 0
        else:
            assert receipt["error"] == "cost_cap" and receipt["ledger_id"] is None
        async with b.pool.acquire() as conn:
            assert await conn.fetchval("SELECT attempts FROM tank.batch_items WHERE batch_id=$1 AND tenant_id=$2", body.id, tenant) == 1
    assert len(b.sent) == (2 if expected == "completed" else 0)


@pytest.mark.asyncio
async def test_identifier_work_cannot_escape_batch_cost_cap(ladder, monkeypatch):  # noqa: F811
    from fastapi import HTTPException
    b = ladder
    monkeypatch.setenv("TANK_BATCH_MIN", "1")
    monkeypatch.setattr(b.tank, "prompt_has_identifier", lambda _: True)
    for tenant in b.tenants:
        await policy(b, tenant, model="luna", rung=1, batch_eligible=True, max_cost_usd=0.000001)
        body = b.tank.BatchRequest(requests=[request(b, tenant, interactive=False)])
        with pytest.raises(HTTPException) as refused:
            await b.tank.route_batch(body, None)
        assert refused.value.status_code == 409
    assert not b.sent
    async with b.pool.acquire() as conn:
        assert await conn.fetchval("SELECT count(*) FROM tank.batches") == 0


@pytest.mark.asyncio
async def test_failed_normal_retry_keeps_escalation_and_batch_receipt(ladder, monkeypatch):  # noqa: F811
    b = ladder
    monkeypatch.setenv("TANK_BATCH_MIN", "1")

    async def code(*args):
        return json.dumps({"answerable": False}), 0

    async def gateway(method, path, **kwargs):
        return httpx.Response(200, json={"id": "fixture-id", "status": "expired"})

    class FailedProvider(b.tank.httpx.AsyncClient):
        async def post(self, url, **kwargs):
            b.sent.append(kwargs["json"])
            raise httpx.ConnectError("fixture outage")

    monkeypatch.setattr(b.tank, "_run_code_candidate", code)
    monkeypatch.setattr(b.tank, "_batch_gateway", gateway)
    monkeypatch.setattr(b.tank.httpx, "AsyncClient", FailedProvider)
    bodies = []
    for tenant in b.tenants:
        await policy(b, tenant, batch_eligible=True)
        body = b.tank.BatchRequest(requests=[request(b, tenant, interactive=False)])
        bodies.append(body)
        await b.tank.route_batch(body, None)
    for _ in range(3):
        await b.tank.process_batches_once()
    for body, tenant in zip(bodies, b.tenants):
        result = await b.tank.batch_status(body.id, tenant)
        receipt = result["results"][0]
        assert result["status"] == "failed" and receipt["error"] == "normal_retry_failed"
        assert receipt["batch"] and receipt["ledger_id"] and receipt["discount_usd"] == 0
        assert json.loads(receipt["escalation"])[0]["reason"] == "not_answerable"
    assert len(b.sent) == 2


@pytest.mark.asyncio
async def test_batch_mixed_tenants_and_unknown_submission_fail_closed(ladder, monkeypatch):  # noqa: F811
    from fastapi import HTTPException
    b = ladder
    monkeypatch.setenv("TANK_BATCH_MIN", "1")
    with pytest.raises(HTTPException) as mixed:
        await b.tank.route_batch(b.tank.BatchRequest(requests=[request(b, t, interactive=False) for t in b.tenants]), None)
    assert mixed.value.status_code == 422
    for tenant in b.tenants:
        await policy(b, tenant, model="luna", rung=1, batch_eligible=True)
        body = b.tank.BatchRequest(requests=[request(b, tenant, interactive=False)])
        await b.tank.route_batch(body, None)
        async with b.pool.acquire() as conn:
            await conn.execute("UPDATE tank.batches SET status='submitting' WHERE id=$1 AND tenant_id=$2", body.id, tenant)
        await b.tank.process_batches_once()
        result = await b.tank.batch_status(body.id, tenant)
        assert result["status"] == "failed" and result["results"][0]["error"] == "interrupted_attempt"
    assert b.sent == []


@pytest.mark.asyncio
async def test_small_and_unsupported_provider_batches_use_capped_calls(ladder, monkeypatch):  # noqa: F811
    b = ladder
    monkeypatch.setenv("TANK_BATCH_MIN", "2")
    for tenant in b.tenants:
        await policy(b, tenant, model="flash", rung=1, batch_eligible=True)
        for size in (1, 2):
            result = await b.tank.route_batch(b.tank.BatchRequest(requests=[request(b, tenant, interactive=False) for _ in range(size)]), None)
            assert result["status"] == "completed" and not result["batch"]
    assert len(b.sent) == 6
    assert all(call["disable_fallbacks"] for call in b.sent)


@pytest.mark.asyncio
async def test_batch_deadline_cancels_before_retry_and_receipts_keep_positions(ladder, monkeypatch):  # noqa: F811
    b = ladder
    monkeypatch.setenv("TANK_BATCH_MIN", "1")
    cancelled = []

    async def gateway(method, path, **kwargs):
        if path == "/v1/files":
            return httpx.Response(200, json={"id": "file"})
        if path == "/v1/batches":
            return httpx.Response(200, json={"id": kwargs["json"]["metadata"]["tank_batch_id"]})
        if path.endswith("/cancel"):
            cancelled.append(path.split("/")[-2])
            return httpx.Response(200, json={"status": "cancelling"})
        return httpx.Response(200, json={"status": "in_progress"})

    monkeypatch.setattr(b.tank, "_batch_gateway", gateway)
    for tenant in b.tenants:
        await policy(b, tenant, model="luna", rung=1, batch_eligible=True)
        body = b.tank.BatchRequest(requests=[request(b, tenant, interactive=False, text="fixture " + str(i)) for i in range(2)])
        await b.tank.route_batch(body, None)
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as changed:
            await b.tank.route_batch(body.model_copy(update={"requests": body.requests[:1]}), None)
        assert changed.value.status_code == 409
    await b.tank.process_batches_once()
    async with b.pool.acquire() as conn:
        await conn.execute("UPDATE tank.batches SET submitted_at=now()-interval '25 hours'")
    await b.tank.process_batches_once()
    await b.tank.process_batches_once()
    assert len(cancelled) == 2 and not b.sent
    async with b.pool.acquire() as conn:
        rows = await conn.fetch("SELECT error FROM tank.batches")
        assert all("awaiting provider cancellation" in r["error"] for r in rows)
        assert await conn.fetchval("SELECT sum(attempts) FROM tank.batch_items") == 0


@pytest.mark.asyncio
async def test_room_batch_http_keeps_free_and_escalated_results_ordered(ladder, monkeypatch):  # noqa: F811
    b = ladder
    monkeypatch.setenv("TANK_BATCH_MIN", "2")
    key = uuid.uuid4().hex
    monkeypatch.setenv("TANK_KEY_BASE", key)
    headers = {"X-Tank-Key": key}

    async def code(req, candidate, messages):
        return json.dumps({"answer": "free fixture", "confidence": 1} if messages[-1]["content"] == "free" else {"answerable": False}), 0

    async def gateway(method, path, **kwargs):
        return httpx.Response(200, json={"id": "fixture-file" if path == "/v1/files" else "fixture-batch", "status": "expired"})

    monkeypatch.setattr(b.tank, "_run_code_candidate", code)
    monkeypatch.setattr(b.tank, "_batch_gateway", gateway)
    ids = []
    for tenant in b.tenants:
        await policy(b, tenant, batch_eligible=True)
        body = b.tank.BatchRequest(requests=[request(b, tenant, interactive=False, text=t) for t in ("free", "paid")])
        ids.append(body.id)
        response = await b.client.post("/v1/route/batch", json=body.model_dump(mode="json"), headers=headers)
        assert response.status_code == 200 and response.json()["status"] == "queued"
        assert [item["position"] for item in response.json()["results"]] == [0, 1]
        assert response.json()["results"][0]["rung"] == 3
    await b.tank.process_batches_once()
    await b.tank.process_batches_once()
    for i, tenant in enumerate(b.tenants):
        response = await b.client.get(f"/v1/route/batch/{ids[i]}", params={"tenant_id": str(tenant)}, headers=headers)
        assert response.status_code == 200 and response.json()["status"] == "completed"
        assert [r["rung"] for r in response.json()["results"]] == [3, 2]
        assert all(r["batch"] for r in response.json()["results"])
        assert (await b.client.get(f"/v1/route/batch/{ids[i]}", params={"tenant_id": str(b.tenants[1-i])}, headers=headers)).status_code == 404
        assert (await b.client.get(f"/v1/route/batch/{ids[i]}", params={"tenant_id": str(tenant)}, headers={"X-Tank-Key": "invalid"})).status_code == 401
