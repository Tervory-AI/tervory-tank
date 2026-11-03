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
