# PR #597 CI review

The Tisan sharing change now ships as **scan.secrets 1.1.0**. The founder approves **scan.secrets 1.1.0 in /skala**. Version 1.0.1 is untouched, and the new engine/runner remain byte-identical to it. No SUPERSEDED exception was added.

Pulled Claude's `0449ce49` before editing; its fixed-origin proxy SSRF fix remains byte-for-byte unchanged. The two stubs now accept and assert `tenant_id`; the real call retains that argument:

- `tests/test_skala_eval_contract.py:242`: the room's checker stub asserts the tenant provided by its eval context.
- `tests/trigger_gate2/test_gate2.py:213`: the accepted-copy stub asserts `str(TENANT)`.
- `tank/skills/scan.secrets/1.1.0/skill.yaml:2` and `CHANGELOG.md:1`: minor version for sharing metadata; all Tisan scanner test/evidence references updated.

## Exact results

| Run | Passed | Skipped | Failed / crashed |
| --- | ---: | ---: | ---: |
| Full main group | 6388 | 52 | 5 |
| Full Tiger group | 46 | 0 | 0 |
| Full Zenas regulation alerts group | 40 | 0 | 0 |
| **Full run total** | **6474** | **52** | **5** |

The main group additionally recorded **1805 passing subtests**. Its full run was **not green**. All three group JUnit reports completed; the outer launcher session returned 143. Main's own report had already failed with the counts above.

All five failures passed separately afterward, without changing their code or timeout limits:

- Trigger intake `identity4`, `identity5`, `identity6`: **3 passed in 52.75s**. In the full run, some subprocess evals returned empty error details and reduced their scores.
- `tests/autumbra_public_bugs/test_page.py::test_public_host_and_direct_page_have_no_shell_admin_keeps_gate`: **1 passed in 50.98s** after its full-run worker crashed.
- `tests/test_skills_offline.py::test_rung3_offline_cases`: **1 passed in 91.60s** after its full-run worker crashed.

The four reported Tisan failures did not recur. The initial focused run was **160 passed, 10 skipped**. The later post-merge/review batch was **379 passed, 3 skipped**, with two collection errors caused by a newly merged dependency missing locally. After syncing main's pinned `PyJWT[crypto]==2.15.1` and other requirements, the two affected identity files passed with the full CI database settings: **19 passed**. Thus the final post-merge checks cover **398 passed, 3 skipped**, with those collection errors resolved. These separate passes do not replace the recorded non-green full run.

Machine-readable counts, failure/recheck boundaries and file lists: [ci-review-results.json](ci-review-results.json).

## Commands and setup

All commands ran in `/workspace/codex-tisan-q1`, except the explicit template command. No production database or model was used. Every push was preceded by fetching and merging origin/main.

```sh
git pull --ff-only origin codex/tisan-q1-quality-checks
.git/venv/bin/pip install -r tank/requirements.txt -r tank/requirements-dev.txt
.git/venv/bin/pip install --require-hashes -r agents/rig/forge/requirements.lock
TMPDIR=/workspace/codex-tisan-q1/.git/tmp .git/venv/bin/python -m pytest -q tests/test_skala_patch_code_unchanged.py tests/test_skala_eval_contract.py tests/trigger_gate2/test_gate2.py tests/test_tisan_quality.py
# 160 passed, 10 skipped.
.git/venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
# All checks passed.
git diff --exit-code 0449ce49 -- agents/tisan/templates/next-site/scripts/quality-check.cjs
# Exit 0.
```

From `agents/tisan/templates/next-site`:

```sh
TMPDIR=/workspace/codex-tisan-q1/.git/tmp node tests/quality-browser.cjs
# Exit 0: clean page passed; critical image-alt found at both widths;
# /missing-test-link named with 404; external server received no requests.
```

The first full run used a temporary directory under `.git`: main had 6381 passed, 56 skipped, 8 failed; Tiger 46 passed; Zenas 40 passed. Radix excludes `.git` paths, and Base's flat-image test found the enclosing checkout. Moving temp files outside the checkout resolved all affected files: **40 passed, 1 skipped**. A six-worker retry was stopped after a worker timeout/crash under shared-host contention and is not counted as passing. The final run used three workers, unchanged 300s test limits and the existing runner's network restrictions. Another full suite was concurrently running on the shared host.

```sh
mkdir -p /workspace/codex-tisan-q1-tmp
TMPDIR=/workspace/codex-tisan-q1-tmp .git/venv/bin/python -m pytest -q tests/test_rx1_scans.py tests/test_base_engine_terms_approved.py tests/test_radix_osv_real.py
# 40 passed, 1 skipped.
```

A fresh task-owned postgres:16 container exposed only loopback port 32806, with trust authentication and disposable pooltest/radix_passive_test/market_test databases. The exact final launcher was:

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

Its cases were collected after merging main at fb55cd35. Main advanced during required push checkpoints; the post-merge batch below includes its new and changed Python test files. It used the same database environment and the existing runner's credential removal and loopback socket limits. Exact subprocess commands, in order (postmerge, intake, browser, rung3):

```sh
/workspace/codex-tisan-q1/.git/venv/bin/python -m pytest -q -p no:cacheprovider -rfEs -n 1 --dist loadfile --max-worker-restart 0 --timeout 300 --timeout-method thread -o faulthandler_timeout=240 --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --durations 15 --tb=short --junitxml=/workspace/codex-tisan-q1/.git/q1-ci-junit/postmerge.xml tests/test_command_repo_tools.py tests/test_identity_backup.py tests/test_identity_stack.py tests/test_identity_za.py tests/test_mcp_client.py tests/test_mcp_server_client_integration.py tests/test_restore_drill.py tests/test_trigger_w1.py tests/test_trigger_x_length.py tests/trigger_second_build/test_second.py tests/test_skala_patch_code_unchanged.py tests/test_skala_eval_contract.py tests/trigger_gate2/test_gate2.py tests/test_tisan_quality.py
```
```sh
/workspace/codex-tisan-q1/.git/venv/bin/python -m pytest -q -p no:cacheprovider -rfEs -n 1 --dist loadfile --max-worker-restart 0 --timeout 300 --timeout-method thread -o faulthandler_timeout=240 --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --durations 15 --tb=short --junitxml=/workspace/codex-tisan-q1/.git/q1-ci-junit/intake-recheck.xml 'tests/skala_intake/test_intake.py::test_each_package_meets_real_skala_gate[identity4]' 'tests/skala_intake/test_intake.py::test_each_package_meets_real_skala_gate[identity5]' 'tests/skala_intake/test_intake.py::test_each_package_meets_real_skala_gate[identity6]'
```
```sh
/workspace/codex-tisan-q1/.git/venv/bin/python -m pytest -q -p no:cacheprovider -rfEs -n 1 --dist loadfile --max-worker-restart 0 --timeout 300 --timeout-method thread -o faulthandler_timeout=240 --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --durations 15 --tb=short --junitxml=/workspace/codex-tisan-q1/.git/q1-ci-junit/browser-recheck.xml tests/autumbra_public_bugs/test_page.py::test_public_host_and_direct_page_have_no_shell_admin_keeps_gate
```
```sh
/workspace/codex-tisan-q1/.git/venv/bin/python -m pytest -q -p no:cacheprovider -rfEs -n 1 --dist loadfile --max-worker-restart 0 --timeout 300 --timeout-method thread -o faulthandler_timeout=240 --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --durations 15 --tb=short --junitxml=/workspace/codex-tisan-q1/.git/q1-ci-junit/rung3-recheck.xml tests/test_skills_offline.py::test_rung3_offline_cases
```

The postmerge command initially returned 1 solely for the two missing-jwt collection errors; the other three commands returned 0. Then:

```sh
.git/venv/bin/pip install 'PyJWT[crypto]==2.15.1'
.git/venv/bin/pip install -r tank/requirements.txt
```

With the same CI database environment and network restrictions:

```sh
/workspace/codex-tisan-q1/.git/venv/bin/python -m pytest -q -p no:cacheprovider -rfEs -n 1 --dist loadfile --max-worker-restart 0 --timeout 300 --timeout-method thread -o faulthandler_timeout=240 --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 --durations 15 --tb=short --junitxml=.git/q1-ci-junit/identity-ci-recheck.xml tests/test_identity_stack.py tests/test_identity_za.py
# 19 passed; exit 0.
```

A preliminary identity retry without the CI database environment was 13 passed, 6 skipped; the 19-pass run above supersedes it. Test-generated dashboard HTML artifacts were restored and are not part of this change. Founder browser acceptance remains outstanding as documented in PR.md.
