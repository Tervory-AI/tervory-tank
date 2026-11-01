"""trigger.*/1.1.0: run.py owns the engine's scratch folder, so no exit path leaks it.

1.0.0's engine made its own trigger-skill-* folder and only removed it on a clean
exit; SIGKILL, SIGTERM, run.py's 30 s timeout (which kills it) and a cancelled
call each left the extracted rules.zip in the system temp directory. These tests
drive the real engines and run.py, with the temp directory pointed at tmp_path.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import signal
from pathlib import Path

import pytest

SKILLS = Path(__file__).resolve().parents[1] / "tank" / "skills"
COMPONENTS = ["proselint", "agent_style", "house_style", "readability", "voice_check"]
TEXT = {"text": "I want to sleep, perchance to dream. I would argue that this is a good test."}


def _load(component: str, version: str):
    path = SKILLS / f"trigger.{component}" / version / "run.py"
    spec = importlib.util.spec_from_file_location(f"_trigger_{component}_{version.replace('.', '_')}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scratch(tmp: Path) -> list[Path]:
    return sorted(tmp.glob("trigger-skill-*"))


@pytest.fixture
def private_tmp(tmp_path, monkeypatch):
    import tempfile

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))  # run.py (1.1.0)
    monkeypatch.setenv("TMPDIR", str(tmp_path))  # the engine process (1.0.0)
    return tmp_path


class _Asyncio:
    """run.py's asyncio, recording the engine process and optionally shortening the timeout."""

    def __init__(self, timeout: float | None = None):
        self.process: asyncio.subprocess.Process | None = None
        self.timeout = timeout

    def __getattr__(self, name):
        return getattr(asyncio, name)

    async def create_subprocess_exec(self, *args, **kwargs):
        self.process = await asyncio.create_subprocess_exec(*args, **kwargs)
        return self.process

    def wait_for(self, awaitable, timeout):
        return asyncio.wait_for(awaitable, self.timeout if self.timeout is not None else timeout)


async def _once_extracted(fake: _Asyncio, tmp: Path) -> int:
    """Wait until the engine is running and has extracted rules.zip; return its pid."""
    for _ in range(600):
        folders = _scratch(tmp)
        if fake.process and folders and (folders[0] / "trigger").exists():
            return fake.process.pid
        await asyncio.sleep(0.01)
    raise AssertionError("engine never extracted rules.zip")


async def _call(component: str, version: str, tmp: Path, how: str):
    module = _load(component, version)
    fake = _Asyncio(timeout=1.0 if how == "timeout" else None)
    module.asyncio = fake
    call = asyncio.ensure_future(module.run(dict(TEXT), None))
    if how != "ok":
        pid = await _once_extracted(fake, tmp)
        if how == "cancel":
            call.cancel()
        else:
            # "timeout": freeze the engine so run.py's own wait_for expires and kills it.
            os.kill(pid, {"sigkill": signal.SIGKILL, "sigterm": signal.SIGTERM, "timeout": signal.SIGSTOP}[how])
    try:
        return await call, None
    except BaseException as error:  # noqa: BLE001 - the outcome is what the test checks
        return None, error


@pytest.mark.asyncio
@pytest.mark.parametrize("component", COMPONENTS)
async def test_clean_call_matches_1_0_0_and_leaves_nothing(component, private_tmp):
    old, _ = await _call(component, "1.0.0", private_tmp, "ok")
    new, error = await _call(component, "1.1.0", private_tmp, "ok")
    assert error is None and new == old and new["model_calls"] == 0
    assert _scratch(private_tmp) == []


@pytest.mark.parametrize("how,raised", [
    ("sigkill", ValueError), ("sigterm", ValueError),
    ("timeout", asyncio.TimeoutError), ("cancel", asyncio.CancelledError),
])
@pytest.mark.asyncio
async def test_killed_engine_leaves_no_scratch_folder(how, raised, private_tmp):
    _, error = await _call("proselint", "1.1.0", private_tmp, how)
    assert isinstance(error, raised)
    assert _scratch(private_tmp) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("how", ["sigkill", "sigterm", "timeout"])
async def test_1_0_0_leaked_on_the_same_paths(how, private_tmp):
    """The probe above detects the leak: 1.0.0 (unchanged, still approved) leaves one folder."""
    await _call("proselint", "1.0.0", private_tmp, how)
    assert len(_scratch(private_tmp)) == 1


def test_engine_refuses_to_run_without_an_empty_scratch_folder(tmp_path):
    import subprocess
    import sys

    engine = SKILLS / "trigger.proselint" / "1.1.0" / "engine.py"
    (tmp_path / "busy").mkdir()
    (tmp_path / "busy" / "x").write_text("x")
    for argv in ([], [str(tmp_path / "missing")], [str(tmp_path / "busy")]):
        done = subprocess.run([sys.executable, "-I", str(engine), "proselint", *argv],
                              input=b"{}", capture_output=True, timeout=60)
        assert done.returncode != 0
    assert sorted(p.name for p in tmp_path.iterdir()) == ["busy"]
