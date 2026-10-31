"""Run the whole offline test suite, in parallel, the way the PR tank job does.

  python3 .github/scripts/offline_suite.py [extra pytest args]

Offline means: no provider keys in the environment, and in-process sockets
may only reach loopback (pytest-socket). The Postgres service, a local Redis
container started by tests/tenant_bus, Chromium and Node all run on the runner.

Three pytest runs, because two test folders import sibling modules by bare
name (test_alerts, test_review) and so cannot share one process with other
folders that have files of the same name:
  1. everything else, 2. tests/tiger_g5, 3. tests/zenas_regulation_alerts.
tests/ci_security runs in the security job (it needs the pinned gitleaks) and
tests/test_live_check.py in live-check.yml (it needs Playwright for Node).

Known failures on main are listed with reasons in tests/quarantine.txt.

Fail fast (ci run 41241674166, 31 Oct 2026: worker gw0 died in
tests/test_rig_landing_overflow.py at 21:17:42 UTC and the job then sat silent
until the 30-minute job timeout cancelled it at 21:32:44 UTC, with no stack):
  - faulthandler_timeout prints every thread's stack for a test still running
    after 240s, before the 300s per-test timeout kills its worker;
  - --max-worker-restart 0 ends a run as soon as a worker crashes, instead of
    replacing the worker and re-running the same file;
  - each run has a wall-clock budget; past it, the whole process group gets
    SIGABRT (pytest's faulthandler prints the stacks) and then SIGKILL, so the
    step fails with evidence well before the job timeout.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALONE = ["tests/tiger_g5", "tests/zenas_regulation_alerts"]
# Run by their own workflows: security job (pinned gitleaks), live-check.yml (Node Playwright).
ELSEWHERE = ["tests/ci_security", "tests/test_live_check.py"]
# Provider keys and tokens must never reach the suite, even if a runner has them set.
# Wall-clock seconds per run. Hosted-runner times on main, 31 Oct 2026: main 651-834s,
# tests/tiger_g5 11-15s, tests/zenas_regulation_alerts 6-7s. All three budgets plus
# about 1.5 minutes of job setup fit inside the tank job's 30-minute timeout.
BUDGETS = {"main": 1080, "tests/tiger_g5": 180, "tests/zenas_regulation_alerts": 180}
OVER_BUDGET = 124  # the exit code timeout(1) uses
KEY_HINTS = ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "OPENAI", "ANTHROPIC", "OPENROUTER",
             "PERPLEXITY", "DEEPSEEK", "GROQ", "TOGETHER", "MISTRAL", "GEMINI", "XAI_", "HF_")


def clean_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not any(h in k.upper() for h in KEY_HINTS)}
    env.setdefault("PYTHONPATH", "tank")
    return env


def _signal_group(pgid: int, sig: int) -> None:
    try:
        os.killpg(pgid, sig)
    except ProcessLookupError:
        pass


def run(cmd: list[str], budget: float, name: str, grace: float = 20, **kwargs) -> int:
    """Run cmd in its own process group; past budget seconds, dump stacks and stop it all.

    The group holds pytest, its xdist workers and the plain subprocesses they
    start. Chromium (Playwright) makes its own process group, so it is not in it;
    it exits by itself when its --remote-debugging-pipe closes as the worker dies."""
    proc = subprocess.Popen(cmd, start_new_session=True, **kwargs)
    try:
        return proc.wait(timeout=budget)
    except KeyboardInterrupt:  # Ctrl-C or a cancelled job: its own session no longer gets it
        _signal_group(proc.pid, signal.SIGINT)
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            pass  # it ignored SIGINT; SIGKILL below, then re-raise the interrupt
        finally:
            _signal_group(proc.pid, signal.SIGKILL)
        raise
    except subprocess.TimeoutExpired:
        print(f"\n::error title=offline suite over budget::{name} still running after {budget:.0f}s; "
              "sending SIGABRT to print stacks, then stopping it", flush=True)
        _signal_group(proc.pid, signal.SIGABRT)
        try:
            proc.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            pass
        _signal_group(proc.pid, signal.SIGKILL)
        proc.wait()
        return OVER_BUDGET


def _faulthandler(test_timeout: int) -> list[str]:
    if test_timeout <= 0:  # per-test timeout switched off
        return []
    return ["-o", f"faulthandler_timeout={test_timeout - 60 if test_timeout > 120 else max(1, test_timeout // 2)}"]


def pytest_args(workers: str = "auto", test_timeout: str = "300") -> list[str]:
    return [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfEs",
            "-n", workers, "--dist", "loadfile",
            # A crashed worker (hung test killed by the thread timeout, or a native
            # crash) ends the run: no replacement worker re-running the same file.
            "--max-worker-restart", os.environ.get("SUITE_MAX_WORKER_RESTART", "0"),
            # thread: a hung test (or its teardown) kills only its worker.
            "--timeout", test_timeout, "--timeout-method", "thread",
            # ...but first print its stack: the thread timeout's own dump is lost when
            # xdist reports the worker as "node down: Not properly terminated".
            *_faulthandler(int(test_timeout)),
            "--disable-socket", "--allow-unix-socket", "--allow-hosts=127.0.0.1,localhost,::1",
            "--durations", "15"]


def _interrupt(signum, frame):
    raise KeyboardInterrupt


def main(extra: list[str]) -> int:
    signal.signal(signal.SIGTERM, _interrupt)
    common = pytest_args(os.environ.get("SUITE_WORKERS", "auto"), os.environ.get("SUITE_TEST_TIMEOUT", "300"))
    # A slower machine (fewer workers) can stretch the budgets, e.g. SUITE_BUDGET_SCALE=3.
    scale = float(os.environ.get("SUITE_BUDGET_SCALE", "1"))
    runs = [
        ("main", [*(f"--ignore={p}" for p in ALONE + ELSEWHERE)]),
        *((p, [p]) for p in ALONE),
    ]
    env, failed = clean_env(), []
    started = time.monotonic()
    for name, args in runs:
        print(f"\n===== offline suite: {name} =====", flush=True)
        t0 = time.monotonic()
        junit = []
        if os.environ.get("SUITE_JUNIT_DIR"):
            junit = [f"--junitxml={os.environ['SUITE_JUNIT_DIR']}/{name.replace('/', '_')}.xml"]
        code = run([*common, *junit, *extra, *args], BUDGETS[name] * scale, name, cwd=ROOT, env=env)
        print(f"===== {name}: exit {code} in {time.monotonic() - t0:.0f}s =====", flush=True)
        if code != 0:
            failed.append(name)
    print(f"\nOffline suite finished in {time.monotonic() - started:.0f}s; "
          f"{'failed: ' + ', '.join(failed) if failed else 'all runs passed'}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
