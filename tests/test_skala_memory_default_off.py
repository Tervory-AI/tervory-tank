"""The optional memory wire preserves the pre-existing skill entry when off."""
from types import SimpleNamespace
from uuid import uuid4

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("setting", [None, "false", "0"])
@pytest.mark.parametrize("run_id", [None, "supplied"])
async def test_disabled_memory_keeps_existing_skill_path(monkeypatch, setting, run_id):
    import paid_steps
    from skala_memory_wire import run_skill_with_identity

    if setting is None:
        monkeypatch.delenv("SKALA_MEMORY_ENABLED", raising=False)
    else:
        monkeypatch.setenv("SKALA_MEMORY_ENABLED", setting)
    body = SimpleNamespace(paid_run_id=uuid4() if run_id else None)
    expected = {"result": "placeholder existing skill result"}
    calls = []

    async def existing(skill_id, request, caller):
        calls.append((skill_id, request, caller))
        return expected

    async def unexpected_checkpoint(*args, **kwargs):
        pytest.fail("Disabled memory introduced a durable checkpoint")

    monkeypatch.setattr(paid_steps, "checkpoint", unexpected_checkpoint)
    actual = await run_skill_with_identity("placeholder.skill", body, None, existing)
    assert actual is expected
    assert calls == [("placeholder.skill", body, None)]
