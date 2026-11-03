# Tiger alerts read in /chats

Branch: `codex/tiger-alerts-read`. Claude opens the PR; the founder merges.
Implementation and focused tests verified at `c24a4372094339e5a72eeefcb17bdf04a638dcd9`,
including main `3c336a7528164814579a63f0e5d5bf1b2b2ab4e0`.

## Result and scope

`tiger.alerts` reads the tenant's saved alerts for all five kinds through the
existing Tiger page relay. Optional URL and kind filters return the six alert
fields and counts for all five kinds, including zero counts. The read records
one code receipt with agent `tiger` and cost $0. No alert is changed.

As corrected by the founder, reads retain the ordinary pending card. Confirm
uses ordinary adapter dispatch; `tiger.alerts` is absent from the side-effect
confirmed-dispatch set. Reconfirming the saved card does not read again or add
another receipt. `finish_turn`, `propose_action`, and the card flow are unchanged.
The existing code planner handles typed `tiger.alerts` without a model call.
Its existing planning receipt is separate from the read receipt after Confirm.

#599, #604 and #603 were already on main. This branch retains all six T1 tools
and their adapters and adds `tiger.alerts` to T1's planner pattern. No changes to
`tank/trigger_routes.py`, any schema, the Tiger page, or Workspace are introduced
by this branch. No new UI wording, production SQL, live settings or deployment.

## Files and verified lines

Line numbers refer to the verified implementation head above.

| File and line | Change |
| --- | --- |
| `agents/tiger/watch.py:110` | Literal SQL adds optional `$3` kind filter; existing tenant, URL, newest-200 behavior retained. |
| `agents/tiger/watch.py:849` | SQL store passes optional kind as parameter. |
| `agents/tiger/watch.py:1020` | Memory store mirrors optional kind filtering. |
| `agents/tiger/app.py:480` | Room GET /alerts validates the five kinds; invalid kind returns 422. |
| `tank/tiger_alerts.py:14` | Optional arguments reuse UrlArgs URL validation and reject unknown kinds. |
| `tank/tiger_alerts.py:34` | Identity, Tiger squad requirement, existing page relay/tenant filtering, six-field result, five counts, agent-tiger $0 receipt. |
| `tank/main.py:4079` | Existing page relay forwards optional kind; absent kind leaves existing call unchanged. |
| `tank/main.py:4207` | Mount new read router beside base_lists. |
| `tank/command.py:42` | Add tool after existing six Tiger tools. |
| `tank/command.py:1249` | GET adapter directly after tiger.read. |
| `tank/command.py:1812` | Extend T1 code planner pattern. These are the only three changed command.py lines. |
| `tests/test_command.py:49`, `tests/test_command.py:956`, `tests/test_personal_tokens.py:49` | Update existing Tiger tool inventory expectations only. |
| `tests/test_tiger_alerts_read.py:31` | Disposable PostgreSQL and memory-store parametrization; real room/page relay and real ledger writes. |
| `tests/test_tiger_alerts_read.py:107` | Five kinds, counts, URL/kind filters, invalid arguments, exact no-kind room bytes including SQL newest-200 cap, tenant isolation, no-squad 403 and empty results. |
| `tests/test_tiger_alerts_read.py:197` | Actual pending card, Confirm, ordinary dispatch, $0 receipt in thread, no side-effect dispatch, idempotent re-Confirm, unchanged alerts. |
| `tests/test_tiger_alerts_read.py:239` | Typed command does not invoke model planner. |

## Exact validation commands and results

All commands ran from `/workspace/codex-tiger-alerts`. The existing unchanged
runner starts and removes its own trust-authenticated loopback postgres:16;
pytest-socket blocks external networking. No production database was used.

```sh
TMPDIR=/workspace/codex-tiger-alerts-tmp .venv/bin/python tests/rig_tiger_prices/run_t1_offline.py tests/test_tiger_alerts_read.py::test_pending_card_confirms_through_ordinary_dispatch_with_zero_receipt --maxfail=1
```

**2 passed, 14 warnings in 20.43s.** Both memory and PostgreSQL exercise the
founder's corrected card semantics. Replaced the previous direct-dispatch test.

```sh
TMPDIR=/workspace/codex-tiger-alerts-tmp .venv/bin/python tests/rig_tiger_prices/run_t1_offline.py tests/test_tiger*.py tests/tiger_alert_email/ tests/tiger_alert_page/ tests/test_command.py tests/test_personal_tokens.py
```

**418 passed, 14 warnings in 1209.12s (0:20:09).** Includes all 36 new read cases,
existing Tiger tests, T1 concurrency/non-superuser checks, email/page tests,
command regression tests and the updated personal-token inventory expectation.
The test subprocess started after the main merge; no implementation changed
during that subprocess. Warnings are existing FastAPI on_event deprecations.

```sh
TMPDIR=/workspace/codex-tiger-alerts-tmp .venv/bin/python tests/rig_tiger_prices/run_t1_offline.py tests/tiger_g5/
```

**46 passed, 14 warnings in 147.80s (0:02:27).** Separate run avoids unrelated
bare test-module name collisions, matching the existing CI split.

```sh
.venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
.venv/bin/ruff check agents/tiger/app.py agents/tiger/watch.py --select E9,F
.venv/bin/python -m pytest tests/test_secrets.py -q
git diff --check
git diff origin/main --check
```

**Both Ruff checks passed; 2 secret checks passed in 31.88s; whitespace checks
passed.** Semgrep is left to CI; it is not installed in this local virtualenv.
Runtime SQL remains literal with numbered parameters; no schema change.

Earlier isolated read-suite verification, before the card correction, was
**36 passed, 14 warnings in 200.92s**. Initial test-harness attempts exposed
missing placeholder environment setup and offline DNS setup; these were fixed
in the tests. The final 418-case run supersedes those intermediate attempts.

Setup used the existing Python 3.12 interpreter to create this branch's own
virtualenv, then the repository dependency manifests:

```sh
/workspace/codex-tiger-t1/.venv/bin/python -m venv .venv
.venv/bin/pip install -r tank/requirements.txt -r tank/requirements-dev.txt
.venv/bin/pip install --require-hashes -r agents/rig/forge/requirements.lock
(cd workspace && npm ci --no-audit --no-fund)
```

All setup commands succeeded; npm installed 45 packages. The prior checkout
was only used as an interpreter source and was not modified.

Each completed file was committed and pushed individually. The corrected test
commit is `0abc07de`; main merge is `c24a4372`. The final evidence commit only
adds this document. Before each push:

```sh
git fetch origin main
git merge origin/main
git push origin codex/tiger-alerts-read
```

Previous pushes succeeded. Latest fetch/merge before this evidence commit
reported **Already up to date**. No push to main and no PR creation or merge.

## CI and founder-browser acceptance still pending

Per the latest instruction, CI is the full Tank suite test of record; the full
suite was not run locally. Claude must record the final-head CI Tank job URL
and result when the PR exists. No CI success is claimed here.

No founder-browser screenshots were supplied or captured in this offline run.
This is implementation/test proof, not completion of the founder acceptance.
The remaining browser proof is: Custom Nation runs and confirms `tiger.alerts`
in /chats, compares saved kind/product URL/time/before/after with Tiger, filters
`below_cost`, inspects the $0 receipt, and verifies a second tenant cannot see
Custom Nation's rows. Save those actual screenshots with the PR; no live or
fixture data was inserted to manufacture them.
