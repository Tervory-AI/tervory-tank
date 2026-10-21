# WORKER-0: the first worker run (a small test for the shadow budget)

> Written 21 Oct 2026. The first task for Tervory's own build workers, to prove the full path end to end: an issue, a sealed container, model calls through Tank with ledger rows (agent `workers`), a draft PR, green CI, ready for review. Small on purpose.

**Files you may change:**
- `tests/test_shadow_budget.py` (new)

## Task
Add pytest tests for `_shadow_budget()` in `tank/main.py`, which reads `TANK_SHADOW_BUDGET_USD`:
- unset gives `1.0`;
- `"5"` gives `5.0`;
- `"0"` gives `0.0`;
- `"abc"` gives `1.0`;
- `"-2"` gives `1.0`.

Set and clear the variable with pytest's `monkeypatch`. Import Tank the same way `tests/test_tank_models_route.py` does (set the same placeholder environment variables first, then `import main as tank`). No database, no network, no secrets.

Change nothing else.

## Done when
CI green, and the PR description lists the five cases.
