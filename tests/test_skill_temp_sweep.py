"""Killed trigger.* engines leave their rules.zip scratch folder in /tmp; Tank sweeps it."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
import skala

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "tank/skills/trigger.proselint/1.0.0/engine.py"


def _folder(root: Path, name: str, age_s: float) -> Path:
    path = root / name
    (path / "trigger").mkdir(parents=True)
    (path / "trigger" / "rules.txt").write_text("x")
    stamp = time.time() - age_s
    os.utime(path, (stamp, stamp))
    return path


def test_sweep_removes_only_stale_skill_folders(tmp_path):
    stale = _folder(tmp_path, "trigger-skill-old", 2 * 3600)
    fresh = _folder(tmp_path, "trigger-skill-new", 60)
    other = _folder(tmp_path, "pytest-of-someone", 2 * 3600)
    (tmp_path / "trigger-skill-file").write_text("not a folder")
    os.utime(tmp_path / "trigger-skill-file", (0, 0))
    assert skala.sweep_skill_temp(tmp_path) == ["trigger-skill-old"]
    assert not stale.exists() and fresh.exists() and other.exists()
    assert (tmp_path / "trigger-skill-file").exists()
    assert skala.sweep_skill_temp(tmp_path / "missing") == []


def test_killed_engine_leaks_its_folder_and_the_sweep_removes_it(tmp_path):
    """The root cause: SIGKILL (run.py's timeout and cancel path) skips TemporaryDirectory cleanup."""
    pytest.importorskip("proselint")
    env = {**os.environ, "TMPDIR": str(tmp_path)}
    proc = subprocess.Popen([sys.executable, "-I", str(ENGINE), "proselint"], env=env,
                            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 60
        while not list(tmp_path.glob("trigger-skill-*/trigger")) and time.monotonic() < deadline:
            assert proc.poll() is None, "engine exited before unpacking its rules"
            time.sleep(0.05)
        time.sleep(0.5)  # let extraction finish
    finally:
        proc.send_signal(signal.SIGKILL)
        proc.wait()
    leaked = list(tmp_path.glob("trigger-skill-*"))
    assert len(leaked) == 1
    assert skala.sweep_skill_temp(tmp_path) == []  # a young folder may belong to a live engine
    assert skala.sweep_skill_temp(tmp_path, now=time.time() + skala.SKILL_TEMP_MAX_AGE_S + 1) == [leaked[0].name]
    assert not leaked[0].exists()


def test_run_skill_sweeps_at_most_every_ten_minutes(monkeypatch):
    monkeypatch.delenv("TANK_SKILL_TEMP_SWEEP", raising=False)
    calls = []
    monkeypatch.setattr(skala, "_last_temp_sweep", None)
    monkeypatch.setattr(skala, "_sweep_skill_temp_quietly", lambda: calls.append(1))
    started = []

    class Thread:
        def __init__(self, target, name, daemon):
            assert daemon and name == "skill-temp-sweep"
            self.target = target

        def start(self):
            started.append(1)
            self.target()

    monkeypatch.setattr(skala.threading, "Thread", Thread)
    clock = [1000.0]
    monkeypatch.setattr(skala.time, "monotonic", lambda: clock[0])
    skala._maybe_sweep_skill_temp()
    skala._maybe_sweep_skill_temp()
    clock[0] += skala.SKILL_TEMP_SWEEP_EVERY_S
    skala._maybe_sweep_skill_temp()
    assert calls == [1, 1] and started == [1, 1]


def test_run_skill_calls_the_sweep(monkeypatch):
    import asyncio
    seen = []
    monkeypatch.setattr(skala, "_maybe_sweep_skill_temp", lambda: seen.append("sweep"))

    async def run(payload, ctx):
        return {"ok": True}

    monkeypatch.setattr(skala, "_import_run", lambda pkg: run)
    out = asyncio.run(skala.run_skill(type("P", (), {"ref": "x@1"})(), {}, None))
    assert out["ok"] is True and seen == ["sweep"]


def test_sweep_switch_and_thread_failure_never_fail_the_call(monkeypatch):
    started = []
    monkeypatch.setattr(skala, "_last_temp_sweep", None)
    monkeypatch.setenv("TANK_SKILL_TEMP_SWEEP", "off")  # what tests/conftest.py sets for every test

    class Boom:
        def __init__(self, **kwargs):
            started.append(kwargs)

        def start(self):
            raise RuntimeError("can't start new thread")

    monkeypatch.setattr(skala.threading, "Thread", Boom)
    skala._maybe_sweep_skill_temp()
    assert started == [] and skala._last_temp_sweep is None
    monkeypatch.delenv("TANK_SKILL_TEMP_SWEEP")
    skala._maybe_sweep_skill_temp()  # must not raise
    assert len(started) == 1
