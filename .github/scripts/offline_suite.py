"""Run the whole offline test suite, in parallel, the way the PR tank job does.

  python3 .github/scripts/offline_suite.py [extra pytest args]

Offline means: no provider keys in the environment, and in-process sockets
may only reach loopback (pytest-socket). The Postgres service, a local Redis
container started by tests/tenant_bus, Chromium and Node all run on the runner.

Three pytest runs, because two test folders import sibling modules by bare
name (test_alerts, test_review) and so cannot share one process with other
folders that have files of the same name:
  1. everything else, 2. tests/tiger_g5, 3. tests/zenas_regulation_alerts.
tests/ci_security runs in the security job (it needs the pinned gitleaks).

Known failures on main are listed with reasons in tests/quarantine.txt.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALONE = ["tests/tiger_g5", "tests/zenas_regulation_alerts"]
ELSEWHERE = ["tests/ci_security"]
# Provider keys and tokens must never reach the suite, even if a runner has them set.
KEY_HINTS = ("API_KEY", "TOKEN", "SECRET", "PASSWORD", "OPENAI", "ANTHROPIC", "OPENROUTER",
             "PERPLEXITY", "DEEPSEEK", "GROQ", "TOGETHER", "MISTRAL", "GEMINI", "XAI_", "HF_")


def clean_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not any(h in k.upper() for h in KEY_HINTS)}
    env.setdefault("PYTHONPATH", "tank")
    return env


def main(extra: list[str]) -> int:
    workers = os.environ.get("SUITE_WORKERS", "auto")
    common = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rfE",
              "-n", workers, "--dist", "loadfile", "--timeout", os.environ.get("SUITE_TEST_TIMEOUT", "300"),
              "--disable-socket", "--allow-unix-socket", "--allow-hosts=127.0.0.1,localhost,::1",
              "--durations", "15"]
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
        code = subprocess.call([*common, *junit, *extra, *args], cwd=ROOT, env=env)
        print(f"===== {name}: exit {code} in {time.monotonic() - t0:.0f}s =====", flush=True)
        if code != 0:
            failed.append(name)
    print(f"\nOffline suite finished in {time.monotonic() - started:.0f}s; "
          f"{'failed: ' + ', '.join(failed) if failed else 'all runs passed'}", flush=True)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
