"""Security regression cases from PR #254; no provider or storage credentials."""
import asyncio
import json
import sys
import uuid

import pytest
from fastapi import HTTPException

from agents.rig.forge import retention, service
from agents.rig.forge.gpu import GPU, GPUError
from agents.rig.forge.pipeline import command, StageFailed
from agents.rig.forge.storage import Storage


def job(**changed):
    return service.Job(tenant_id=uuid.uuid4(), job_id=uuid.uuid4(), home_region="us-east",
                       inputs=["sample.glb"], unit_mm=1000, dimensions_mm=(20, 30, 40),
                       **{"method": "scan", **changed})


@pytest.mark.asyncio
async def test_trellis_defaults_off_before_storage_budget_or_provider(monkeypatch):
    monkeypatch.delenv("RIG_FORGE_TRELLIS_ENABLED", raising=False)
    async def forbidden(*args, **kwargs):
        pytest.fail("Disabled TRELLIS must never reserve or launch work")
    with pytest.raises(GPUError, match="disabled"):
        await GPU(object()).run({}, "trellis2", transfers={}, timeout=60, cap="1",
                               relay=forbidden, save_provider=forbidden, namespace="fixture")
    body = job().model_copy(update={"method": "trellis2", "inputs": ["photo.png"]})
    with pytest.raises(HTTPException) as caught:
        await service.submit(body)
    assert caught.value.status_code == 503 and "disabled" in caught.value.detail


def test_presigned_transfers_limit_methods_keys_and_expiry():
    calls = []
    class Signer:
        def generate_presigned_url(self, operation, **kwargs):
            calls.append((operation, kwargs))
            return "opaque-capability"
    body = job().model_copy(update={"method": "trellis2", "inputs": ["a.png", "b.png"], "timeout_seconds": 3600})
    store = Storage(str(body.tenant_id), str(body.job_id), client=Signer())
    result = store.transfers(body.model_dump(mode="json"))
    assert set(result) == {"manifest", "get", "put"}
    assert set(result["put"]) == {"result.glb", "source.zip"}
    assert len(calls) == 4
    for operation, options in calls:
        params = options["Params"]
        assert params["Bucket"] == "tervory-rig" and params["Key"].startswith(store.prefix)
        if operation == "get_object":
            # GET covers queue time too, so a queued job does not pay to fail.
            assert options["HttpMethod"] == "GET" and options["ExpiresIn"] == 3900
            assert params["Key"].removeprefix(store.prefix) in {"inputs/a.png", "inputs/b.png"}
        else:
            assert options["HttpMethod"] == "PUT" and options["ExpiresIn"] == 3900
            assert params["Key"].removeprefix(store.prefix) in {"gpu/result.glb", "gpu/source.zip"}
            assert params["Metadata"] == {"approval": "draft"}


@pytest.mark.asyncio
async def test_oversized_transfer_secret_is_refused_before_any_reservation(monkeypatch):
    monkeypatch.setenv("RIG_FORGE_TRELLIS_ENABLED", "false")
    async def forbidden(*args, **kwargs):
        pytest.fail("An oversized link set must never reserve budget or launch work")
    long_link = "https://" + "a" * 32 + ".r2.cloudflarestorage.com/tervory-rig/x?" + "s" * 900
    transfers = {"manifest": {}, "get": {f"p{i}.jpg": long_link for i in range(150)}, "put": {}}
    with pytest.raises(GPUError, match="Too many photo links"):
        await GPU(object()).run({}, "photogrammetry", transfers=transfers, timeout=60, cap="1",
                               relay=forbidden, save_provider=forbidden, namespace="fixture")


@pytest.mark.asyncio
async def test_poll_of_unknown_job_creates_no_folder(monkeypatch, tmp_path):
    monkeypatch.setenv("FORGE_DATA_DIR", str(tmp_path))
    tenant, job_id = uuid.uuid4(), uuid.uuid4()
    with pytest.raises(HTTPException) as caught:
        await service.poll(job_id, tenant)
    assert caught.value.status_code == 404
    assert not (tmp_path / str(tenant)).exists() and list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_parser_process_has_limits_and_no_service_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_JOBS_TOKEN", uuid.uuid4().hex)
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY_RIG", uuid.uuid4().hex)
    probe = tmp_path / "probe.py"
    probe.write_text('import os, resource\n'
                     'assert not any("KEY" in k or "TOKEN" in k or "PROXY" in k for k in os.environ)\n'
                     'assert resource.getrlimit(resource.RLIMIT_AS) == (134217728, 134217728)\n')
    await command([sys.executable, str(probe)], tmp_path, memory_bytes=128 * 1024**2)
    with pytest.raises(StageFailed):
        await command([sys.executable, "-c", "bytearray(512 * 1024**2)"], tmp_path, memory_bytes=128 * 1024**2)
    with pytest.raises(asyncio.TimeoutError):
        await command([sys.executable, "-c", "import time; time.sleep(60)"], tmp_path, timeout=0.05,
                      memory_bytes=128 * 1024**2)
    # A killed/over-budget parser must leave the worker able to process a new job.
    await command([sys.executable, "-c", "pass"], tmp_path, memory_bytes=128 * 1024**2)


def terminal(root, body, status="draft"):
    work = root / str(body.tenant_id) / str(body.job_id)
    work.mkdir(parents=True)
    retention.save(work / "request.json", body.model_dump(mode="json"))
    retention.save(work / "state.json", {**body.scope(), "status": status, "finished_at": 1,
                                        "receipts": [{"stage": "upload"}], "report": {"passed": True}})
    (work / "draft.glb").write_bytes(b"intermediate")
    (work / "report.json").write_text('{}')
    return work


@pytest.mark.asyncio
async def test_retention_cleans_terminal_artifacts_preserves_pending_and_retry_identity(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_RETENTION_SECONDS", "3600")
    monkeypatch.setenv("FORGE_DATA_DIR", str(tmp_path))
    # Other test modules set TANK_API_KEY at import; the forge must see none.
    for name in ("TANK_KEY", "TANK_API_KEY", "TANK_KEY_RIG"):
        monkeypatch.delenv(name, raising=False)
    finished, waiting, active = job(), job(), job()
    done = terminal(tmp_path, finished)
    pending = terminal(tmp_path, waiting, "failed")
    busy = terminal(tmp_path, active, "running")
    retention.save(pending / "pending-receipt.json", {"outcome": "delivered"})
    retention.sweep(tmp_path, {(active.tenant_id, active.job_id)}, now=4000)
    assert not (done / "draft.glb").exists() and not (pending / "draft.glb").exists()
    assert (busy / "draft.glb").exists()
    assert (pending / "report.json").exists() and (pending / "pending-receipt.json").exists()
    assert not (done / "report.json").exists()
    assert json.loads((done / "state.json").read_text())["diagnostics_expired"]
    # Retry after retention still polls the original job and cannot relaunch it.
    monkeypatch.setattr(service, "Storage", lambda *args: object())
    response = await service.submit(finished)
    assert json.loads(response.body)["diagnostics_expired"] and not service.tasks


def test_retention_restart_marks_orphan_failed_and_never_follows_symlinks(tmp_path, monkeypatch):
    monkeypatch.setenv("FORGE_RETENTION_SECONDS", "3600")
    body = job()
    work = terminal(tmp_path / "data", body, "running")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "keep").write_text("keep")
    (work / "linked").symlink_to(outside, target_is_directory=True)
    retention.sweep(tmp_path / "data", set(), now=10)
    assert (outside / "keep").exists() and not (work / "linked").exists()
    assert json.loads((work / "state.json").read_text())["status"] == "failed"


@pytest.mark.parametrize("suffix", ["step", "stp", "iges", "igs"])
def test_cad_requests_are_rejected(suffix):
    from pydantic import ValidationError
    data = job().model_dump(mode="json")
    with pytest.raises(ValidationError):
        service.Job(**{**data, "inputs": ["part." + suffix]})
    with pytest.raises(ValidationError):
        service.Job(**{**data, "method": "cad"})
