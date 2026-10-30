# Tiger learns public domain layout playbooks

Every new Tiger URL currently learns its layout from scratch. After three
distinct public pages confirm the same marker, Tiger now saves a domain
playbook. A new page tries it before the existing per-URL learning path.
One mismatch falls back locally; three consecutive playbook failures retire
the shared marker. Three fresh page confirmations can promote it again.

Branch: `codex/tiger-domain-playbooks`. Started from main
`678d47efcfc8002149870452996419293235be42`. Tested implementation: `c6098e4`.
Claude opens the PR. Git pushes only; no GitHub API, merge or deployment.

**Verification:** 205 passed, 1 existing gold-set skip. The one-door guard
has identical failures on this branch and a fresh checkout of starting main;
those are documented below. Founder browser screenshots remain pending.

## Behaviour and privacy

- The existing public browser response, extraction, `learn_layout` and
  `read_page` do the work. There are no additional page requests, model calls,
  services, dependencies, keys, UI controls or wording. Browser scope rules,
  domain rate limits, worker and scheduler are unchanged.
- A confirmed code reading must have a readable layout, product name, price,
  currency and known stock. OCR, feed/portal reads, login/private responses,
  challenges and incomplete readings cannot contribute public confirmations.
- Shared state contains only the public hostname, a structural marker,
  generation/failure counters and opaque SHA-256 fingerprints of confirming
  public paths. Structured markers are fixed method names. DOM markers hold
  hashes of tag/class tokens, matched by the existing DOM reader; arbitrary
  custom class names can work without storing their raw text. Extra fields
  are discarded. No tenant ID, label, name, price, stock, HTML, screenshot,
  credential, raw selector, raw URL or query value is stored in a playbook.
- Hostnames are exact; subdomains are independent. HTTP/HTTPS copies of the
  same path, repeated checks, and query/fragment aliases count once, including
  across tenants. Thus query-only product variants do not count as independent
  confirming paths. Credentialed/IP/local/nonstandard-port URLs stay on the
  existing per-URL path. These sharing restrictions do not change read scope.
- A new URL tries the active marker first. If it fails, that URL learns its
  own layout normally. Previously learned URLs keep their existing guard;
  a changed known page still says it cannot read rather than guessing. If
  that guard matches the active playbook, its result also updates the shared
  failure streak. A successful playbook read resets the streak.
- Three consecutive attempted-marker failures clear the active marker and
  its confirmations. Confirmation starts fresh after retirement. The failing
  page's fallback is not allowed to immediately reactivate the retired marker.
  A failed candidate read removes that path's stale vote. Other URLs' saved
  layouts are never rewritten or disabled by a shared failure.
- Postgres row locks serialize promotions/failures. Generation checks ignore
  late results from an older playbook. The additive, idempotent table survives
  a new store instance. Public-state lookup/write failures fall back to the
  existing URL behaviour; the observation remains tenant-scoped. No SQL was
  run on production data.

## What changed (file and line)

| File:line | Change |
| --- | --- |
| `agents/tiger/domain_playbooks.py:22`, `:41` | Reduce public markers to fixed methods/selector fingerprints and canonicalize public page identities. |
| `agents/tiger/domain_playbooks.py:77`, `:95`, `:104`, `:115` | Promotion/retirement state machine; additive schema; memory/Postgres state with distinct-page votes and generation checks. |
| `agents/tiger/page_guard.py:66`, `:295`, `:309` | Reuse the existing reader with hashed selector tokens; keep raw per-URL markers working. |
| `agents/tiger/watch.py:31`, `:500`, `:645`, `:691`, `:902` | Store integration and fingerprint persistence in existing per-URL observation evidence. |
| `agents/tiger/watch.py:1166`, `:1236` | Try a public playbook before new-URL learning; record only confirmed code results after the tenant observation saves. |
| `agents/tiger/Dockerfile:16` | Include the new module in the existing image. |
| `tests/tiger_playbooks/test_playbooks.py:39`, `:93` | Memory and disposable Postgres fixtures, real check path, privacy/lifecycle/concurrency regressions. |
| `tests/tiger_playbooks/fixtures/fourth.html:1` | Clearly labelled offline fourth-page fixture; never served by an app route. |
| `tests/tiger_playbooks/PR.md:1` | PR description, commands and proof record. |
| `tests/tiger_playbooks/evidence/{focused,fingerprints,regression,main-guard,branch-guard,guard-comparison,lint}.txt:1` | Saved command outputs. |

The first three shop pages are the repository's existing saved public book
pages in `tests/tiger_alert_page/fixtures/live/`. The fourth and layout changes
are offline fixtures/mutations, not claimed as new live captures. Every store
case runs against both memory and real local Postgres; the schema is applied
twice. Tests refuse OCR, extra fetching or model calls and use two tenants.

## Required tests

| Requirement | Test |
| --- | --- |
| Three pages form a playbook; fourth uses it without learning again; public sharing across tenants | `test_three_saved_pages_promote_fourth_uses_playbook_across_tenants` |
| Repeated/aliased URLs cannot manufacture three pages | `test_repeats_tenants_queries_and_fragments_are_not_three_pages` |
| One failed page falls back; other pages work; success resets the streak | `test_mismatch_falls_back_without_breaking_other_pages_and_success_resets` |
| Three failures retire; three fresh confirmations re-promote; stale results cannot revive an old generation | `test_three_consecutive_changes_retire_then_require_three_fresh_confirmations` |
| Existing per-URL protections survive | `test_known_url_guard_stays_in_control_and_failures_retire_shared_marker` plus existing changed-page tests |
| Domains/private reads isolated | `test_domain_and_public_private_boundaries`; `test_nonpublic_identity_never_enters_shared_store` |
| No tenant/content/URL values in shared records | `test_shared_records_contain_only_public_structure_and_opaque_page_fingerprints` |
| Custom selectors work without raw selector persistence | `test_custom_class_names_work_without_entering_shared_state` |
| Old candidate evidence cannot promote a changed marker | `test_failed_candidate_page_cannot_leave_a_stale_confirmation` |
| Persistence and concurrent distinct-page counting | `test_persistence_and_concurrent_confirmation_use_distinct_pages` |

## Exact commands and results

Commands run in `/workspace/tiger-playbooks` after
`source /workspace/tervory-env/activate.sh`. The local environment needed
main's existing SDK/parser pins for Tank-importing regression tests:

```sh
uv --cache-dir /tmp/tiger-playbooks-uv-cache pip install --python /workspace/tervory-env/venv/bin/python openai==2.54.0 jiter==0.18.0
```

Install exited 0; repository dependency files were not changed. An initial
broader run had eight import failures from the missing `jiter`; the final run
below passes those tests after installing the existing pins.

Focused command (exit 0), pushed at each implementation checkpoint:

```sh
python -m pytest -q tests/tiger_playbooks tests/tiger_alert_page/test_page_changed.py tests/test_tiger_missing_name.py
```

- `980b423`: **41 passed in 2.28s** — [output](evidence/focused.txt).
- `c6098e4`: **43 passed in 2.35s** — [output](evidence/fingerprints.txt).

Final regression command (exit 0):

```sh
TIGER_MAIL_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/pooltest python -m pytest -q -rs tests/tiger_playbooks tests/test_tiger.py tests/test_tg2_tiger_watchlist.py tests/test_tiger_public_policy.py tests/test_tiger_works.py tests/test_tiger_alert_email.py tests/test_tiger_missing_name.py tests/tiger_alert_page/test_page_changed.py tests/tiger_alert_page/test_change_alerts.py tests/tiger_before_deploy/test_before_deploy.py
```

**205 passed, 1 skipped, 6 warnings in 87.05s (0:01:27)** — [output](evidence/regression.txt).
The skip is the existing unfilled 100-page gold set at
`tests/tiger_before_deploy/test_before_deploy.py:181`. Warnings are existing
FastAPI/Pydantic notices. The new Postgres cases and existing SMTP Postgres
test ran; they were not skipped. No model or live-page request was used.

```sh
ruff check --select E9,F agents/tiger/domain_playbooks.py agents/tiger/page_guard.py agents/tiger/watch.py tests/tiger_playbooks
git diff --check
git diff --exit-code 678d47e -- workspace tank agents/_brain agents/_chassis tests/test_tank_one_door.py tests/tank_batch_providers tests/test_command_streaming.py
```

All exit 0. Lint: `All checks passed!` — [output](evidence/lint.txt).
Whitespace/scope checks produced no output.

## Existing one-door failure, verified against fresh main

The guard is **not green**. Both checkouts show the same three findings:
two at `tests/tank_batch_providers/verify_passthrough.py:87` and one at
`tests/test_command_streaming.py:81`. This branch changes neither those files
nor the guard/exception registry.

```sh
git clone --no-hardlinks --no-checkout /workspace/tiger-playbooks /tmp/tiger-playbooks-main-proof
git -C /tmp/tiger-playbooks-main-proof checkout --detach 678d47efcfc8002149870452996419293235be42
cd /tmp/tiger-playbooks-main-proof
source /workspace/tervory-env/activate.sh
python -m pytest -q tests/test_tank_one_door.py
cd /workspace/tiger-playbooks
python -m pytest -q tests/test_tank_one_door.py
```

- Fresh main: **1 failed, 26 passed in 12.40s**, exit 1 — [output](evidence/main-guard.txt).
- Branch: **1 failed, 26 passed in 13.04s**, exit 1 — [output](evidence/branch-guard.txt).

Complete scanner findings, including their counts, are identical; zero new
finding occurrences, exit 0 — [comparison](evidence/guard-comparison.txt):

```sh
python - <<'PY'
from collections import Counter
from pathlib import Path
import sys
sys.path.insert(0, 'tests')
import test_tank_one_door as guard
base = Counter(item.identity for item in guard.scan(Path('/tmp/tiger-playbooks-main-proof')))
branch = Counter(item.identity for item in guard.scan(Path.cwd()))
print('Starting main: 678d47efcfc8002149870452996419293235be42')
print('Scanner findings identical:', branch == base)
print('New finding occurrences:', sum((branch - base).values()))
assert branch == base
PY
```

## Founder browser proof — pending

This branch is not deployed, and the founder's browser session is unavailable.
The offline feature is demonstrated; live verification and founder screenshots
are not claimed. After founder merge/deployment, the remaining proof is the
existing Tiger page showing successful checks for three real public product
pages on one shop, then a fourth, with that shop's actual prices/stock. The
founder's screenshots and URLs/check times must be added here. No sample data
has been placed on a live screen to manufacture that proof.
