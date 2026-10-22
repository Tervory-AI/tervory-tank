"""RIG-5 state transitions, tenant boundaries and real empty/reapplied Postgres."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import sys
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import httpx
import pytest
import pytest_asyncio
from fastapi import FastAPI
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
for folder in (ROOT / "agents/rig", ROOT / "agents/_chassis"):
    sys.path.insert(0, str(folder))

from rigbox.api import mount as public_mount  # noqa: E402
from rigbox.service import RigError, hash_key  # noqa: E402
from rigbox.three_d.api import mount  # noqa: E402
from rigbox.three_d.contracts import Assembly, Job, Review, Report  # noqa: E402
from rigbox.three_d.engine import check_artifact  # noqa: E402
from rigbox.three_d.forge import BrainForge  # noqa: E402
from rigbox.three_d.sample import TENANT, WITHOUT_3D, PUBLIC_KEY, PLAIN_KEY, seed  # noqa: E402


@pytest.mark.asyncio
async def test_workspace_corridor_requires_room_key_tenant_and_review(rig, monkeypatch):
    engine, pool, client, _ = rig
    room_key = secrets.token_urlsafe(32)
    monkeypatch.setenv("TANK_KEY", room_key)
    headers = {"X-Tank-Key": room_key}
    body = {"tenant_id": str(TENANT), "actor": "reviewer-fixture", "payload": {}}
    root = "/v1/rig/internal/3d/workspace/"
    assert (await client.post(root + "dashboard", json=body)).status_code == 401
    assert (await client.post(root + "dashboard", headers={"X-Rig-Key": PUBLIC_KEY}, json=body)).status_code == 401
    assert (await client.post(root + "dashboard", headers=headers, json={**body, "actor": ""})).status_code == 403
    assert (await client.post(root + "dashboard", headers=headers, json={**body, "tenant_id": str(WITHOUT_3D)})).status_code == 403
    caps = await client.post(root + "capabilities", headers=headers, json={**body, "actor": ""})
    assert caps.json()["rig_3d"] is True
    assert (await client.post(root + "entitlement", headers=headers, json=body)).status_code == 422
    request = job()
    submitted = await client.post(root + "submit", headers=headers, json={**body, "payload": request.model_dump(mode="json")})
    assert submitted.status_code == 200
    dashboard = (await client.post(root + "dashboard", headers=headers, json=body)).json()
    assert dashboard["jobs"][0]["status"] == "draft"
    preview = await client.post(root + "preview", headers=headers, json={**body, "payload": {"id": str(request.id)}})
    assert preview.content[:4] == b"glTF" and "no-store" in preview.headers["cache-control"]
    review = {"id": str(request.id), "review": {"scale": True, "appearance": True}}
    assert (await client.post(root + "approve", headers=headers, json={**body, "payload": review})).status_code == 422
    review["review"]["attachment_points"] = True
    assert (await client.post(root + "approve", headers=headers, json={**body, "payload": review})).status_code == 200
    actor = await pool.fetchval("SELECT reviewed_by FROM agent_rig.rig_3d_jobs WHERE tenant_id=$1 AND id=$2", TENANT, request.id)
    assert actor == "reviewer-fixture"
    assert (await client.post(root + "runtime", headers=headers, json={**body, "payload": {"name": "../api.py"}})).status_code == 422
    runtime = await client.post(root + "runtime", headers=headers, json={**body, "payload": {"name": "runtime.js"}})
    assert runtime.status_code == 200 and "no-store" in runtime.headers["cache-control"]
    kiosk = str(uuid4())
    reset = await client.post(root + "reset", headers=headers, json={**body, "payload": {"id": kiosk}})
    assert reset.json()["revision"] == 1
    assert await engine.store.kiosk(WITHOUT_3D, kiosk) == 0


@pytest.mark.asyncio
async def test_tank_proxy_does_not_accept_unscoped_or_entitlement_writes(rig, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", os.environ.get("RIG_TEST_DATABASE_URL") or os.environ["POOL_SCHEMA_DATABASE_URL"])
    monkeypatch.setenv("LITELLM_MASTER_KEY", secrets.token_urlsafe(32))
    monkeypatch.setenv("TANK_API_KEY", secrets.token_urlsafe(32))
    import main as tank
    from rig_three_d import build_router
    _, _, room, _ = rig
    room_key, workspace_key = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    monkeypatch.setenv("TANK_KEY", room_key)
    monkeypatch.setenv("TANK_KEY_RIG", room_key)
    monkeypatch.setenv("TANK_API_KEY", workspace_key)
    monkeypatch.setattr(tank, "TANK_API_KEY", workspace_key)
    monkeypatch.setattr(tank, "_http", room)
    monkeypatch.setattr(tank, "RIG_AGENT_URL", "http://rig.test")
    app = FastAPI(); app.include_router(build_router(tank))
    headers = {"X-Tank-Key": workspace_key, "X-Tervory-User": "reviewer-fixture"}
    body = {"tenant_id": str(TENANT), "payload": {}}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://tank.test") as client:
        root = "/v1/rig/3d/workspace/"
        assert (await client.post(root + "capabilities", json=body)).status_code == 401
        assert (await client.post(root + "capabilities", headers=headers, json=body)).json()["rig_3d"] is True
        assert (await client.post(root + "dashboard", headers={"X-Tank-Key": workspace_key}, json=body)).status_code == 403
        assert (await client.post(root + "dashboard", headers=headers, json={})).status_code == 400
        assert (await client.post(root + "entitlement", headers=headers, json=body)).status_code == 404
        assert (await client.post(root + "dashboard?tenant_id=" + str(WITHOUT_3D), headers=headers, json=body)).status_code == 403
        foreign = job().model_dump(mode="json"); foreign["tenant_id"] = str(WITHOUT_3D)
        assert (await client.post(root + "submit", headers=headers, json={**body, "payload": foreign})).status_code == 403
        request = job().model_dump(mode="json")
        assert (await client.post(root + "submit", headers=headers, json={**body, "payload": request})).status_code == 200
        assert (await client.post(root + "dashboard", headers=headers, json=body)).json()["jobs"][0]["status"] == "draft"
        data = await client.post(root + "preview", headers=headers, json={**body, "payload": {"id": request["id"]}})
        assert data.content[:4] == b"glTF" and "no-store" in data.headers["cache-control"]


@pytest_asyncio.fixture
async def rig(tmp_path):
    url = os.environ.get("RIG_TEST_DATABASE_URL") or os.environ.get("POOL_SCHEMA_DATABASE_URL")
    if not url:
        if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
            pytest.fail("RIG-5 requires the CI Postgres service")
        pytest.skip("Set RIG_TEST_DATABASE_URL for the real database checks")
    name = "rig3d_" + uuid4().hex
    admin = await asyncpg.connect(url)
    await admin.execute(f'CREATE DATABASE "{name}"')
    parts = urlsplit(url)
    database = urlunsplit((parts.scheme, parts.netloc, "/" + name, "", ""))
    pool = await asyncpg.create_pool(database, min_size=1, max_size=4)
    try:
        engine, key = await seed(pool, tmp_path, approve_models=False)
        # Apply the entire room schema again, as the real app does on every boot.
        await engine.catalogue.store.apply_schema()
        app = FastAPI()
        public_mount(app); mount(app)
        app.state.rig, app.state.rig_three_d = engine.catalogue, engine
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://rig.test") as client:
            yield engine, pool, client, key
    finally:
        await pool.close()
        await admin.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
        await admin.close()


def job(product="centre", **changes):
    dimensions = {"centre": (160,70,110), "part-a": (40,40,40), "part-b": (40,60,40), "part-tall": (40,70,40)}
    return Job(id=uuid4(), tenant_id=TENANT, product_id=product, source="cad",
               inputs=[f"{TENANT}/uploads/model.step"], dimensions_mm=dimensions[product], cost_cap_usd=0, **changes)


async def approve_all(engine):
    for product in ("centre", "part-a", "part-b", "part-tall"):
        request = job(product)
        await engine.submit(str(TENANT), request)
        assert (await engine.poll(str(TENANT), request.id))["status"] == "draft"
        await engine.approve(str(TENANT), request.id, Review(scale=True, appearance=True, attachment_points=True), "test-reviewer")
    for part, anchor in [("part-a", "left"), ("part-tall", "left"), ("part-b", "right")]:
        await engine.mount_points(str(TENANT), part, "centre", anchor, "attach")


@pytest.mark.asyncio
async def test_draft_hidden_until_all_human_checks_and_idempotent_submission(rig):
    engine, _, client, admin = rig
    request = job()
    response = await client.post("/v1/rig/admin/3d/jobs", headers={"X-Rig-Key": admin}, json=request.model_dump(mode="json"))
    assert response.status_code == 202
    assert (await engine.submit(str(TENANT), request))["id"] == str(request.id)
    assert (await engine.poll(str(TENANT), request.id))["status"] == "draft"
    path = f"/v1/rig/3d/assets/{request.id}"
    assert (await client.get(path, headers={"X-Rig-Key": PUBLIC_KEY})).status_code == 404
    assert (await client.get(f"/v1/rig/admin/3d/preview/{request.id}", headers={"X-Rig-Key": admin})).status_code == 200
    route = f"/v1/rig/admin/3d/jobs/{request.id}/approve"
    assert (await client.post(route, headers={"X-Rig-Key": admin}, json={"scale": True, "appearance": True})).status_code == 422
    checks = {"scale": True, "appearance": True, "attachment_points": True}
    assert (await client.post(route, headers={"X-Rig-Key": PUBLIC_KEY}, json=checks)).status_code == 403
    assert (await client.post(route, headers={"X-Rig-Key": admin}, json=checks)).status_code == 200
    assert (await client.post(route, headers={"X-Rig-Key": admin}, json=checks)).status_code == 409
    result = await client.get(path, headers={"X-Rig-Key": PUBLIC_KEY})
    assert result.status_code == 200 and result.content[:4] == b"glTF"
    assert int(result.headers["content-length"]) == len(result.content)
    assert result.headers["content-type"] == "model/gltf-binary"
    assert "no-store" in result.headers["cache-control"]


@pytest.mark.parametrize("field,value,reason", [
    ("outward_faces", False, "inward"), ("watertight", False, "holes"),
    ("real_size", False, "dimensions"), ("gltf_valid", False, "validation"),
    ("triangles", 100_001, "budget"), ("size_bytes", 5_000_001, "budget"),
    ("dimensions_mm", (1,1,1), "millimetres"),
])
@pytest.mark.asyncio
async def test_failed_automatic_checks_never_enter_review(rig, field, value, reason):
    engine, _, _, _ = rig
    request = job(); await engine.submit(str(TENANT), request)
    original = engine.forge.poll
    async def invalid(request):
        result = await original(request)
        result.report = result.report.model_copy(update={field: value})
        return result
    engine.forge.poll = invalid
    result = await engine.poll(str(TENANT), request.id)
    assert result["status"] == "failed" and reason in result["reason"]
    assert await engine.store.review_queue(TENANT) == []
    with pytest.raises(RigError):
        await engine.approve(str(TENANT), request.id, Review(scale=True, appearance=True, attachment_points=True), "reviewer")


@pytest.mark.asyncio
async def test_assembly_approved_mounts_swap_current_fit_and_single_total(rig):
    engine, pool, client, _ = rig
    await approve_all(engine)
    body = {"product_id": "centre"}
    response = await client.post("/v1/rig/3d/assembly", headers={"X-Rig-Key": PUBLIC_KEY}, json=body)
    assert response.status_code == 200
    assembly = response.json()
    assert assembly["available"] and len(assembly["models"]) == 3
    assert assembly["total"] == {"amount": 150, "currency": "USD", "indicative": True}
    assert {m["mount"]["parent"] for m in assembly["models"][1:]} == {"left", "right"}
    assert "receipt_ids" not in response.text and "cost_cap" not in response.text
    body["choices"] = {"module": "part-tall"}
    swapped = await client.post("/v1/rig/3d/assembly", headers={"X-Rig-Key": PUBLIC_KEY}, json=body)
    assert swapped.status_code == 200 and swapped.json()["total"]["amount"] == 155
    await pool.execute("UPDATE agent_rig.fits SET approved=false WHERE tenant_id=$1 AND part_sku='part-tall'", TENANT)
    assert (await client.post("/v1/rig/3d/assembly", headers={"X-Rig-Key": PUBLIC_KEY}, json=body)).status_code == 422
    # A stale browser cannot quote the revoked assembly either.
    quote = {"assembly": body, "name": "Sample Shopper", "email": "sample@example.test"}
    assert (await client.post("/v1/rig/3d/quote", headers={"X-Rig-Key": PUBLIC_KEY}, json=quote)).status_code == 422
    assert await pool.fetchval("SELECT count(*) FROM agent_rig.quotes WHERE tenant_id=$1", TENANT) == 0


@pytest.mark.asyncio
async def test_missing_model_falls_back_without_any_asset_address(rig):
    engine, _, _, _ = rig
    result = await engine.assembly(str(TENANT), Assembly(product_id="centre"))
    assert result["available"] is False and result["models"] == []


@pytest.mark.asyncio
async def test_all_admin_routes_reject_public_keys_and_foreign_tenants(rig, monkeypatch):
    engine, pool, client, admin = rig
    await approve_all(engine)
    model = await engine.store.approved(TENANT, "centre")
    await engine.store.set_entitlement(WITHOUT_3D, True, None, "USD")
    foreign_admin = secrets.token_urlsafe(32)
    await pool.execute("INSERT INTO agent_rig.keys (tenant_id,key_hash,kind) VALUES ($1,$2,'admin')", WITHOUT_3D, hash_key(foreign_admin))
    assert (await client.get(f"/v1/rig/3d/assets/{model['id']}", headers={"X-Rig-Key": PLAIN_KEY})).status_code == 404
    assert (await client.get(f"/v1/rig/admin/3d/jobs/{model['id']}", headers={"X-Rig-Key": foreign_admin})).status_code == 404
    assert (await client.get("/v1/rig/admin/3d/review", headers={"X-Rig-Key": PUBLIC_KEY})).status_code == 403
    assert (await client.post("/v1/rig/admin/3d/jobs", headers={"X-Rig-Key": foreign_admin}, json=job().model_dump(mode="json"))).status_code == 403
    assert (await client.get("/v1/rig/3d/capabilities", headers={"X-Rig-Key": PUBLIC_KEY, "Origin": "https://unrelated.example"})).status_code == 403
    monkeypatch.setenv("TANK_KEY", secrets.token_urlsafe(32))
    body = {"tenant_id": str(TENANT), "enabled": True}
    for key in (PUBLIC_KEY, admin):
        assert (await client.post("/v1/rig/internal/3d/entitlement", headers={"X-Rig-Key": key}, json=body)).status_code == 401


@pytest.mark.asyncio
async def test_entitlement_revocation_blocks_assets_jobs_and_assembly(rig):
    engine, _, client, _ = rig
    await approve_all(engine)
    model = await engine.store.approved(TENANT, "centre")
    await engine.store.set_entitlement(TENANT, False, None, "USD")
    headers = {"X-Rig-Key": PUBLIC_KEY}
    assert (await client.get("/v1/rig/3d/capabilities", headers=headers)).json()["rig_3d"] is False
    assert (await client.get(f"/v1/rig/3d/assets/{model['id']}", headers=headers)).status_code == 403
    assert (await client.post("/v1/rig/3d/assembly", headers=headers, json={"product_id": "centre"})).status_code == 403


@pytest.mark.asyncio
async def test_remote_reset_is_tenant_scoped_and_quote_is_stored(rig):
    engine, pool, client, admin = rig
    await approve_all(engine)
    kiosk = uuid4()
    path = f"/v1/rig/admin/3d/kiosks/{kiosk}/reset"
    assert (await client.post(path, headers={"X-Rig-Key": PUBLIC_KEY})).status_code == 403
    assert (await client.post(path, headers={"X-Rig-Key": admin})).json() == {"revision": 1}
    assert await engine.store.kiosk(WITHOUT_3D, kiosk) == 0
    body = {"assembly": {"product_id": "centre"}, "name": "Sample Shopper", "email": "sample@example.test"}
    response = await client.post("/v1/rig/3d/quote", headers={"X-Rig-Key": PUBLIC_KEY}, json=body)
    assert response.status_code == 200 and response.json()["request_id"]
    assert await pool.fetchval("SELECT count(*) FROM agent_rig.quotes WHERE tenant_id=$1", TENANT) == 1


@pytest.mark.asyncio
async def test_corrupted_model_cannot_be_approved_or_served(rig):
    engine, _, _, _ = rig
    request = job(); await engine.submit(str(TENANT), request); await engine.poll(str(TENANT), request.id)
    engine.assets.path(TENANT, request.id).write_bytes(b"damaged model")
    with pytest.raises(RigError, match="check report"):
        await engine.approve(str(TENANT), request.id, Review(scale=True, appearance=True, attachment_points=True), "reviewer")


@pytest.mark.asyncio
async def test_forge_relay_contract_and_failure_do_not_leak_upstream(rig):
    from rigbox.three_d.contracts import Anchor
    from rigbox.three_d.forge import wire_job
    request = job(anchors={"reviewed": Anchor(position_mm=(0,0,0), quaternion=(0,0,0,1))})
    fixture = (ROOT / "agents/rig/rigbox/three_d/fixtures/centre.glb").read_bytes()
    calls = []
    class Files:
        async def stage(self, value):
            assert value == request
        async def draft(self, value):
            assert value == request
            return fixture
    def handler(call):
        calls.append(call)
        if call.method == "POST":
            return httpx.Response(202, json={"tenant_id": str(TENANT), "job_id": str(request.id), "status": "queued"})
        return httpx.Response(200, json={"tenant_id": str(TENANT), "job_id": str(request.id), "status": "draft",
            "asset_key": f"forge/{TENANT}/{request.id}/drafts/model.glb",
            "report": {"passed": True, "checks": dict.fromkeys(["finite", "watertight", "outward", "manifold", "dimensions", "budget", "gltf_validator"], True),
                       "bytes": len(fixture), "triangles": 12, "dimensions_mm": [160,70,110]},
            "receipts": [{"tenant_id": str(TENANT), "task_id": str(request.id), "ledger_id": str(uuid4()),
                          "stage": stage, "outcome": "delivered"} for stage in ("model_check", "validate", "upload")]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        relay = BrainForge(client, secrets.token_urlsafe(32), Files())
        assert (await relay.submit(request)).id == request.id
        result = await relay.poll(request)
        artifact = await relay.artifact(request)
        assert result.tenant_id == TENANT and check_artifact(artifact, result.report) is None
    sent = json.loads(calls[0].content)
    assert set(sent) == {"tenant_id", "job_id", "home_region", "method", "inputs", "unit_mm", "dimensions_mm", "max_triangles", "max_bytes", "timeout_seconds", "cost_cap_usd"}
    assert sent["cost_cap_usd"] == "0" and sent["inputs"] == ["model.step"] and sent["method"] == "cad"
    assert calls[1].url.params["tenant_id"] == str(TENANT) and calls[1].url.params["home_region"] == "us-east"
    assert all("x-tank-key" in call.headers and "key" not in call.url.query.decode() for call in calls)
    for source, method in [("ai", "trellis2"), ("scan", "photogrammetry")]:
        value = request.model_copy(update={"source": source})
        assert wire_job(value)["method"] == method
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(503, text="private upstream detail"))) as client:
        with pytest.raises(RigError) as error:
            await BrainForge(client, secrets.token_urlsafe(32), Files()).submit(request)
        assert "private upstream" not in str(error.value)


@pytest.mark.parametrize("source,count", [("cad",1),("ai",1),("ai",4),("scan",50),("scan",70)])
def test_source_modes(source, count):
    suffix = "step" if source == "cad" else "jpg"
    value = job().model_dump(); value.update(source=source, inputs=[f"{TENANT}/uploads/photo-{n}.{suffix}" for n in range(count)])
    assert Job.model_validate(value).source == source


@pytest.mark.parametrize("change", [
    {"source":"scan"}, {"inputs":["https://example.test/model.step"]},
    {"inputs":[f"{WITHOUT_3D}/uploads/model.step"]}, {"dimensions_mm":[0,1,1]},
    {"dimensions_mm":[float("nan"),1,1]}, {"cost_cap_usd":-1}, {"max_bytes":5_000_001},
    {"inputs":[f"{TENANT}/uploads/../model.step"]},
])
def test_reject_unsafe_source_and_budget(change):
    value = job().model_dump(); value.update(change)
    with pytest.raises(ValidationError): Job.model_validate(value)


def test_fixture_glbs_match_their_report_and_are_compressed():
    root = ROOT / "agents/rig/rigbox/three_d/fixtures"
    for path in root.glob("*.glb"):
        data = path.read_bytes()
        report = Report(**json.loads(path.with_suffix(".json").read_text()), sha256=hashlib.sha256(data).hexdigest(),
                        size_bytes=len(data), receipt_ids=[uuid4()])
        assert check_artifact(data, report) is None


@pytest.mark.asyncio
async def test_unavailable_forge_changes_nothing(rig):
    engine, pool, _, _ = rig
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(503))) as client:
        engine.forge = BrainForge(client, secrets.token_urlsafe(32))
        with pytest.raises(RigError):
            await engine.submit(str(TENANT), job())
    assert await pool.fetchval("SELECT count(*) FROM agent_rig.rig_3d_jobs WHERE tenant_id=$1", TENANT) == 0


@pytest.mark.asyncio
async def test_forge_files_are_tenant_scoped_immutable_and_us_only():
    from rigbox.three_d.assets import ForgeFiles
    from chassis.storage import StorageError
    request = job()
    paths = []
    def handler(call):
        paths.append(call.url.path)
        if call.method == "PUT":
            assert call.headers["if-none-match"] == "*"
            assert call.url.path == f"/tervory-rig/forge/{TENANT}/{request.id}/inputs/model.step"
            return httpx.Response(412)
        return httpx.Response(200, content=b"same input")
    env = {"R2_ACCOUNT_ID": uuid4().hex, "R2_ACCESS_KEY_ID_RIG": secrets.token_hex(20),
           "R2_SECRET_ACCESS_KEY_RIG": secrets.token_hex(32)}
    files = ForgeFiles("rig", environ=env, transport=httpx.MockTransport(handler))
    try:
        await files.stage(request)
        assert paths[0] == f"/tervory-rig/us-east/{TENANT}/uploads/model.step"
        assert await files.draft(request) == b"same input"
        assert paths[-1] == f"/tervory-rig/forge/{TENANT}/{request.id}/drafts/model.glb"
        count = len(paths); files.region = "za"
        with pytest.raises(StorageError):
            await files.stage(request)
        assert len(paths) == count
    finally:
        await files.close()


@pytest.mark.asyncio
async def test_unapproved_fit_cannot_gain_mounts_or_enter_assembly(rig):
    engine, pool, _, _ = rig
    await approve_all(engine)
    with pytest.raises(RigError):
        await engine.mount_points(str(TENANT), "part-a", "centre", "unknown-anchor", "attach")
    await pool.execute("UPDATE agent_rig.fits SET approved=false WHERE tenant_id=$1 AND part_sku='part-a'", TENANT)
    with pytest.raises(RigError):
        await engine.mount_points(str(TENANT), "part-a", "centre", "left", "attach")
    result = await engine.assembly(str(TENANT), Assembly(product_id="centre"))
    assert "part-a" not in {model["product_id"] for model in result["models"]}


def test_glb_cannot_cause_external_fetch_even_with_a_matching_checksum():
    import struct
    path = ROOT / "agents/rig/rigbox/three_d/fixtures/centre.glb"
    data = path.read_bytes(); length = struct.unpack_from("<I", data, 12)[0]
    doc = json.loads(data[20:20+length]); doc["images"] = [{"uri": "https://invalid.example/texture.png"}]
    encoded = json.dumps(doc).encode(); encoded += b" " * (-len(encoded) % 4)
    tail = data[20+length:]
    modified = struct.pack("<4sIIII", b"glTF", 2, 20+len(encoded)+len(tail), len(encoded), 0x4E4F534A) + encoded + tail
    report = Report(**json.loads(path.with_suffix(".json").read_text()),
                    size_bytes=len(modified), sha256=hashlib.sha256(modified).hexdigest(), receipt_ids=[uuid4()])
    assert check_artifact(modified, report) == "The model contains an external resource"
