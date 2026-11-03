# PR #597 CI review

Pulled `0449ce49` before editing. Its fixed-origin proxy remains unchanged.

- Moved the Tisan sharing package to `tank/skills/scan.secrets/1.1.0`, updated metadata, changelog and references. Version 1.0.1 is untouched; engine/runner bytes still match it. No `SUPERSEDED` exception was added.
- The founder approves **scan.secrets 1.1.0 in /skala** (also stated in the PR body).
- `tests/test_skala_eval_contract.py` checks the forwarded room tenant explicitly. `tests/trigger_gate2/test_gate2.py` checks the accepted-copy tenant explicitly. The real call retains `tenant_id`.

Commands run from the task clone:

```sh
git pull --ff-only origin codex/tisan-q1-quality-checks
TMPDIR=/workspace/codex-tisan-q1/.git/tmp .git/venv/bin/python -m pytest -q tests/test_skala_patch_code_unchanged.py tests/test_skala_eval_contract.py tests/trigger_gate2/test_gate2.py tests/test_tisan_quality.py
# 160 passed, 10 skipped, 15 warnings in 60.04s.
.git/venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
# All checks passed.
git diff --exit-code 0449ce49 -- agents/tisan/templates/next-site/scripts/quality-check.cjs
# Exit 0.
```

From the template directory:

```sh
TMPDIR=/workspace/codex-tisan-q1/.git/tmp node tests/quality-browser.cjs
# Exit 0: clean page passed; critical image-alt found at both widths;
# /missing-test-link named with 404; external server received no requests.
```

The first full Tank offline run used four workers, normal network restrictions and disposable PostgreSQL on loopback port 32806: main **8 failed, 6381 passed, 56 skipped, 1805 subtests passed**; Tiger **46 passed**; Zenas regulation alerts **40 passed**. The eight failures were test setup: task temp files lived under `.git`, which Radix deliberately excludes and which let Base's flat-image test discover the enclosing repository's skills. No application change was made for these failures.

```sh
mkdir -p /workspace/codex-tisan-q1-tmp
TMPDIR=/workspace/codex-tisan-q1-tmp .git/venv/bin/python -m pytest -q tests/test_rx1_scans.py tests/test_base_engine_terms_approved.py tests/test_radix_osv_real.py
# 40 passed, 1 skipped in 2.14s.
```

The corrected-temp rerun encountered a worker timeout/crash while another full suite was using the shared host. It was stopped rather than counted as passing. A lower-concurrency full rerun follows, with short tracebacks so failures can be diagnosed without expensive long traceback formatting. No application tests or timeouts are weakened. No production database is used.

Final-run setup: Python requirements from `tank/requirements.txt`, `tank/requirements-dev.txt` and `agents/rig/forge/requirements.lock`; the existing Workspace npm dependencies; pinned Chromium at `/home/ammosync/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome`. A fresh task-owned `postgres:16` container uses loopback port 32806 and trust authentication, with disposable `pooltest`, `radix_passive_test` and `market_test` databases. Every CI database variable is set, including the opt-in real-Postgres tests. The existing offline runner removes provider credentials and limits in-process sockets to loopback.

The exact launcher `.git/q1-ci-run.py` used for the final run is:

```python
import os,subprocess,sys
from pathlib import Path
root=Path('/workspace/codex-tisan-q1')
env=os.environ.copy()
shared='postgresql://postgres@127.0.0.1:32806/pooltest'
for name in ('POOL_SCHEMA','ZENAS_SCHEMA','MEMORY_TEST','BASE_TEST','RLS_TEST','SKALA_B3_TEST','SKALA_INTAKE_TEST','TIGER_MAIL_TEST','RIG_TEST','TRAINING_SCHEMA'):
    env[name+'_DATABASE_URL']=shared
env.update(RADIX_PASSIVE_TEST_DATABASE_URL='postgresql://postgres@127.0.0.1:32806/radix_passive_test', DATABASE_URL='postgresql://postgres@127.0.0.1:32806/market_test',TMPDIR='/workspace/codex-tisan-q1-tmp',SUITE_WORKERS='3',SUITE_BUDGET_SCALE='3',SUITE_JUNIT_DIR=str(root/'.git/q1-ci-junit'),PYTHONPATH='tank',READ1_CHROMIUM_EXECUTABLE='/home/ammosync/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome')
raise SystemExit(subprocess.call([sys.executable,'.github/scripts/offline_suite.py','-vv','--tb=short'],env=env,cwd=root))
```

```sh
.git/venv/bin/python .git/q1-ci-run.py > .git/q1-full-tank-suite-final-low.log 2>&1
```

The lower-concurrency full run is in progress; the final summary will follow. Its cases were collected after merging `origin/main` at `fb55cd35`. Main advanced to `cf95a07e` during a required push checkpoint; its new/changed test files will also receive a separate post-merge run. Test-generated dashboard HTML artifacts will be restored, not included in the PR.

The host is concurrently running another full suite. Inspection found only this run's three active workers and their current subprocess, with no leftover workers from the stopped attempt. At 79%, the lower-concurrency run has reported the same three failures in the unrelated immutable Trigger intake checks (`identity4`, `identity5`, `identity6`). Final tracebacks and counts are still pending. The requested accepted-copy regression has also passed inside this full run. This is not a passing full-suite claim.
