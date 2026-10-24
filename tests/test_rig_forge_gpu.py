"""Run the actual Jobs adapter against a deterministic provider and receipt sink."""
import uuid
from types import SimpleNamespace

import pytest

from agents.rig.forge.gpu import GPU, GPUError


class Provider:
    def __init__(self, state="COMPLETED", submit_error=False):
        self.state, self.submit_error = state, submit_error
        self.started, self.cancelled = [], []
    def run_job(self, **kwargs):
        self.started.append(kwargs)
        if self.submit_error:
            raise OSError("lost response")
        return SimpleNamespace(id="stub-job-1")
    def inspect_job(self, **kwargs):
        return SimpleNamespace(status=SimpleNamespace(stage=self.state))
    def cancel_job(self, **kwargs):
        self.cancelled.append(kwargs)


def scope():
    return {"tenant_id": str(uuid.uuid4()), "job_id": str(uuid.uuid4()), "home_region": "us-east"}


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["photogrammetry", "trellis2"])
async def test_gpu_stub_reserves_claims_tracks_and_receipts(method, monkeypatch):
    monkeypatch.setenv("RIG_FORGE_TRELLIS_ENABLED", "true")
    body, events, ids, provider = scope(), [], [], Provider()
    async def relay(action, payload):
        events.append((action, payload))
        if action == "reserve":
            return {**body,"image":"ghcr.io/tervory-ai/forge@sha256:"+"a"*64,
                    "flavor":"a10g-small","timeout_seconds":60}
        return {"recorded": True}
    async def save_provider(value):
        ids.append(value)
    result = await GPU(provider).run(body, method, transfers={}, timeout=60, cap="1",
        relay=relay, save_provider=save_provider, namespace="fixture")
    assert result == "stub-job-1" and ids == [result]
    assert [action for action, _ in events] == ["reserve", "claim", "steps", "steps", "complete"]
    assert events[-1][1]["outcome"] == "delivered"
    assert provider.started[0]["timeout"] == 60
    assert provider.started[0]["command"][-1] == method
    assert set(provider.started[0]["secrets"]) == {"FORGE_TRANSFERS"}
    assert not any(name.startswith("R2_") for name in provider.started[0]["env"])
    assert "HF_JOBS_TOKEN" not in provider.started[0]["env"]


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ["timeout", "lost_response", "failed"])
async def test_failures_stop_cancel_and_keep_uncertain_spend(mode):
    body, events = scope(), []
    provider = Provider("RUNNING" if mode == "timeout" else "ERROR", submit_error=mode == "lost_response")
    ticks = [0]
    async def wait(delay):
        ticks[0] += delay
    async def relay(action, payload):
        events.append((action, payload))
        return {**body,"image":"ghcr.io/tervory-ai/forge@sha256:"+"a"*64,
                "flavor":"a10g-small","timeout_seconds":60}
    async def save_provider(value): pass
    with pytest.raises(GPUError):
        await GPU(provider,wait=wait,clock=lambda:ticks[0]).run(body,"photogrammetry",transfers={},
            timeout=60,cap="1",relay=relay,save_provider=save_provider,namespace="fixture")
    assert len(provider.started) == 1
    assert events[-1][0] == "complete"
    assert events[-1][1]["outcome"] in {"unverified","failed"}
    assert bool(provider.cancelled) == (mode != "lost_response")


@pytest.mark.asyncio
async def test_missing_token_or_denied_budget_never_launches(monkeypatch):
    monkeypatch.delenv("HF_JOBS_TOKEN", raising=False)
    async def denied(*args): raise RuntimeError("Budget denied")
    for gpu, error in ((GPU(), GPUError), (GPU(Provider()), RuntimeError)):
        with pytest.raises(error):
            await gpu.run(scope(),"photogrammetry",transfers={},timeout=60,cap="1",
                relay=denied,save_provider=denied,namespace="fixture")
        if gpu.api:
            assert not gpu.api.started
