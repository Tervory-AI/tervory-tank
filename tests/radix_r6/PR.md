# PR #634 — R4 takeover + I8 + R6

Branch: `codex/radix-w3`. The founder authorized takeover of the existing R4 stack without waiting for its merge. No merge of main. I8 history/evidence remains in `tests/radix_i8/PR.md`.

## Step 1 — R4 audit

| Requirement | Disposition | Evidence |
| --- | --- | --- |
| Confirmed watch, unwatch, watches; tenant/founder Radix tools | already on R4 | `tank/command.py:46`, `:1266`; `tank/radix_watch.py:8`; `agents/radix/passive_routes.py:117` |
| Existing TXT proof re-check; missing/changed TXT stops watch | already on R4 | `agents/radix/passive_gateway.py:28`, `:67`; `passive_store.py:283` |
| Existing passive scan, honest target sha256 artifact | already on R4 | `passive_watch.py:47`; `passive_store.py:100` |
| Existing scheduler and one running scan | already on R4 | `app.py:70`; `passive_watch.py:21`; `passive_store.py:68` |
| Domain comparison, severity change new, existing rule wording | already on R4 | `passive_store.py:111`, `:223` |
| $0 changes, existing card projection | already on R4 | `tank/command.py:1372`, `:1504` |
| Tenant schema/RLS rollout | already on R4; restricted-role catalog lookup added here | `passive_store.py:40`; avoids needing USAGE on Tank schema. `tank/main.py:755` remains the idempotent Tank startup. |
| Explicit watch/scheduler/TXT-change regressions | added here | `tests/radix_i8/test_events.py:310`; I8 tests already cover tenant isolation and shared lock. |

Step-1 check: `TMPDIR=/workspace/codex-radix-w3/.test-data/tmp RADIX_I8_TEST_DATABASE_URL=postgresql://placeholder@127.0.0.1:56483/radix_passive_test /workspace/codex-radix-r4-py312/bin/python -m pytest -q --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 tests/radix_i8/` → **27 passed in 3.89s**, exit 0. Previous full regression: 298 passed, 437 subtests, one expected OSV skip (I8 report). Step-1 source checkpoint `e2f90df1` plus this report. All finished files committed/pushed individually. Continuing to R6 as authorized; no pause for review.
