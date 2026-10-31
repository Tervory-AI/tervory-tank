"""The offline suite fails fast, with stacks, instead of hanging until the job timeout.

ci run 41241674166 (31 Oct 2026): xdist worker gw0 died in tests/test_rig_landing_overflow.py
at 21:17:42 UTC, then the tank job printed nothing until its 30-minute timeout cancelled it
at 21:32:44 UTC. These tests run real pytest/xdist subprocesses on tiny fixture suites.
"""
import importlib.util
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "offline_suite.py"


def _suite():
    spec = importlib.util.spec_from_file_location("offline_suite_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _arg(args, name):
    return args[args.index(name) + 1]


def test_crash_ends_the_run_and_stacks_print_before_the_test_timeout():
    args = _suite().pytest_args("auto", "300")
    assert _arg(args, "--max-worker-restart") == "0"
    assert _arg(args, "--timeout") == "300" and _arg(args, "--timeout-method") == "thread"
    assert _arg(args, "-o") == "faulthandler_timeout=240"
    assert _suite()._faulthandler(0) == [] and _suite()._faulthandler(60) == ["-o", "faulthandler_timeout=30"]


def test_budgets_cover_every_run_and_fit_inside_the_tank_job_timeout():
    suite = _suite()
    assert set(suite.BUDGETS) == {"main", *suite.ALONE}
    job = yaml.safe_load((ROOT / ".github/workflows/ci.yml").read_text())["jobs"]["tank"]
    setup = 4 * 60  # checkout, installs, Chromium, npm ci: about 1.5 minutes on main
    assert sum(suite.BUDGETS.values()) + setup <= job["timeout-minutes"] * 60
    # Slowest main run on hosted runners, 31 Oct 2026, was 834s: keep real headroom.
    assert suite.BUDGETS["main"] >= 834 * 1.25


def test_over_budget_run_dumps_stacks_and_kills_the_whole_group(tmp_path):
    child = tmp_path / "child.py"
    pidfile = tmp_path / "grandchild.pid"
    child.write_text(
        "import faulthandler, subprocess, sys, time\n"
        "faulthandler.enable()\n"
        f"p = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(600)'])\n"
        f"open({str(pidfile)!r}, 'w').write(str(p.pid))\n"
        "def stuck_here():\n    time.sleep(600)\n"
        "stuck_here()\n")
    out = tmp_path / "out.txt"
    t0 = time.monotonic()
    with out.open("w") as fh:
        code = _suite().run([sys.executable, str(child)], 3, "fixture", grace=5, stdout=fh, stderr=subprocess.STDOUT)
    assert code == _suite().OVER_BUDGET and time.monotonic() - t0 < 30
    assert "stuck_here" in out.read_text()  # faulthandler stack from SIGABRT
    grandchild = int(pidfile.read_text())
    for _ in range(50):
        try:
            os.kill(grandchild, 0)
        except ProcessLookupError:
            break
        time.sleep(0.1)
    else:
        os.kill(grandchild, signal.SIGKILL)
        pytest.fail("a process started by the run outlived its budget")


def _fixture_suite(tmp_path, body):
    for name in ("a", "b", "c"):
        (tmp_path / f"test_{name}.py").write_text(body if name == "a" else "def test_ok():\n    pass\n")
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    return tmp_path


@pytest.mark.parametrize("body, needle", [
    ("import os\ndef test_native_crash():\n    os._exit(9)\n", "test_native_crash"),
    ("import time\ndef test_hangs():\n    time.sleep(60)\n", "test_hangs"),
])
def test_worker_crash_or_hang_fails_the_run_fast_with_the_test_named(tmp_path, body, needle):
    suite = _suite()
    folder = _fixture_suite(tmp_path, body)
    args = suite.pytest_args("2", "6")  # hang: stack printed at 3s, worker killed at 6s
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    out = tmp_path / "out.txt"
    t0 = time.monotonic()
    with out.open("w") as fh:
        code = suite.run([*args, "-p", "no:randomly", str(folder)], 90, "fixture", cwd=folder, env=env,
                         stdout=fh, stderr=subprocess.STDOUT)
    text = out.read_text()
    assert code != 0, text
    assert time.monotonic() - t0 < 60, text
    assert needle in text and ("node down" in text or "crashed" in text), text
    if needle == "test_hangs":
        # faulthandler's stack, with the hung test's own frame, before the worker is killed
        assert "Timeout (0:00:03)!" in text and 'test_a.py", line 3 in test_hangs' in text, text
