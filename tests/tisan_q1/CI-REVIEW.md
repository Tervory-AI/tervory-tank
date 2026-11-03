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

The full Tank offline suite is running with four workers, its normal network restrictions and disposable PostgreSQL on loopback port 32806. It has reported failures; final counts and diagnoses will be appended after completion. No production database is used.
