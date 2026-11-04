# Trigger W3 gate 1 review evidence

Branch: `codex/trigger-w3`. Checkout: `/workspace/codex-trigger-w3`.
Base: `9ca6dab26cb7d0b9784064ab7fbb57b651a31184`.
Implementation head: `2f6b75c8` (this evidence is committed afterwards).
Gate 1 only. No PR opened, labelled or merged by Codex.

## Changes

- `tank/trigger_crm.py:51`: founder or tenant-admin authority, retaining the
  actor-bound confirmed `base.list.to_crm` exception. Binding, attestation,
  write tenant mismatch and write confirmation remain enforced.
- `tank/trigger_crm.py:154` and `:194`: list/get use their own tool entitlements
  and the existing `code_receipt`, returning `ledger_id`, zero cost and zero
  model calls. List retains `items`; detail retains the record ID as data.
- `tank/command.py:51`, `:53`: the three CRM tools belong to Trigger; write is
  removed from the founder-only list. Existing tenant-admin exposure is reused.
- `tank/command.py:1197`, `:1212`, `:1268`, `:1497`: strict read schemas, GET
  adapters, resource/record paths and allowed query arguments. Actor identity
  stays in the existing trusted headers, never read query parameters.
- `tank/command.py:1697`: CRM reads bypass confirmed write dispatch; CRM write
  stays in it. Existing pending-card confirmation applies to all three tools.
- `tank/trigger_commands.py:16`: explicit CRM commands produce existing cards
  using code and strict action validation, including write JSON arguments.
- `tests/test_trigger_crm.py:29`, `:149`, `:248`, `:377`, `:414`, `:438`, `:459`,
  `:472`: receipt-aware read contracts, member/admin visibility, two distinct
  bindings, unbound refusal, write confirmation and mismatch, code planning,
  founder Base capability and actual card dispatch selection.
- `tests/trigger_bot_b1/test_engine.py:142`: replace the obsolete denial of
  generic CRM to admins with the newly authorised admin/member contract.
- `docs/ops/TRIGGER-CRM-CLIENTS.md:1`: founder onboarding steps with setting
  names only, configuration delivery requirement and own-workspace acceptance.

No page or card labels were changed. `resource` and `record_id` remain data:
new visible labels for either require an approved Figma frame. No model calls,
production SQL, live record changes, deployment or setting-value inspection.

## Commands and observed results

Initial setup used the exact clone/fetch/checkout/config commands from the brief:
all succeeded. Required-file `ls` originally exited 2 for
`plan/DECISIONS-2026-11-03.md`; the founder explicitly corrected that reference
and authorised skipping it. No main merge was performed.

The first edit attempt used `python`, which is unavailable (exit 127); no source
changed. The edit was rerun successfully with `python3`. Its following initial
push created the branch at the base head. Every completed file was then committed
and pushed with `git push origin codex/trigger-w3`, all successful, in this order:
`198d949f`, `017cd749`, `af5645d0`, `ba9d47eb`, `a08e86ba`, `816130ac`,
`ed2810ec`, `21367338`, `2f6b75c8`.

1. `PYTHONPATH=tank /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_trigger_crm.py --tb=short`
   failed collection: that existing runtime lacks `selectolax`.
2. `PYTHONPATH=/home/ammosync/.codex/trigger-crm-acceptance-deps-20261031:tank /tmp/tervory-rls-merge-python/bin/python -m pytest -q tests/test_trigger_crm.py --tb=short`
   returned 73 passed / 1 failed. The new fake lead-list envelope was wrong;
   it was corrected to the pinned open/closed envelope in `816130ac`.
3. `PYTHONPATH=/home/ammosync/.codex/trigger-crm-acceptance-deps-20261031:tank /tmp/tervory-rls-merge-python/bin/python -m pytest -q tests/test_trigger_crm.py tests/test_trigger*.py tests/test_command*.py tests/test_base_lists.py tests/trigger_first_build tests/trigger_second_build tests/trigger_gate2 tests/trigger_bot_b1 tests/trigger_m1 --tb=short`
   returned 604 passed / 13 failed / 181 skipped. Failures were four Django
   subprocess dependency failures; seven missing Workspace dependency failures;
   one missing `POOL_SCHEMA_DATABASE_URL`; and the obsolete bot admin/CRM
   assertion updated in `ed2810ec`. This is not a passing full-suite claim.
4. Reused installed dependencies without modifying their source:
   `/tmp/tervory-rls-merge-python/bin/python -m venv .venv`;
   wrote `.venv/lib/python3.12/site-packages/trigger-test-runtime.pth` containing
   the existing `/tmp/tervory-rls-merge-python/lib/python3.12/site-packages`,
   `/home/ammosync/trigger-crm-venv312/lib/python3.12/site-packages` and
   `/home/ammosync/.codex/trigger-crm-acceptance-deps-20261031` directories;
   `ln -s /home/ammosync/.codex/trigger-crm-workspace-20261031/workspace/node_modules workspace/node_modules`.
   All succeeded. Runtime, dependency symlink and logs are local and untracked.
5. `PYTHONPATH=tank .venv/bin/python -m pytest -q tests/test_trigger_crm.py tests/test_trigger_crm_wsgi.py tests/trigger_bot_b1/test_engine.py tests/test_command_1b_workspace.py tests/test_base_lists.py tests/trigger_bot_b1/test_workspace.py --tb=short`
   returned **174 passed, 1 skipped**, three existing Pydantic warnings.
6. After adding dispatch regressions:
   `PYTHONPATH=tank .venv/bin/python -m pytest -q tests/test_trigger_crm.py --tb=short`
   returned **77 passed**, three existing warnings.
7. `PYTHONPATH=tank .venv/bin/python -m pytest -q tests/test_trigger*.py tests/test_command*.py tests/test_base_lists.py tests/trigger_first_build tests/trigger_second_build tests/trigger_gate2 tests/trigger_bot_b1 tests/trigger_m1 tests/test_secrets.py --deselect=tests/trigger_bot_b1/test_database.py::test_startup_refuses_bypass_tenant_role_before_schema_and_bot_task --tb=short`
   returned **621 passed, 1 failed, 180 skipped, 1 deselected**, 26 warnings.
   Only failure: `tests/test_command_squads_ui.py` hit shared temporary-storage
   quota, Node write error `-122`. Missing local disposable database configuration
   explains the deselection; database-dependent skips remain CI's responsibility.
8. `mkdir -p .gate1-tmp`, then
   `TMPDIR=/workspace/codex-trigger-w3/.gate1-tmp PYTHONPATH=tank .venv/bin/python -m pytest -q tests/test_command_squads_ui.py --tb=short`
   returned **1 passed**. The failed test succeeds with a checkout-local temp dir.
9. After the final regex flag spelling change:
   `TMPDIR=/workspace/codex-trigger-w3/.gate1-tmp PYTHONPATH=tank .venv/bin/python -m pytest -q tests/test_trigger_crm.py tests/test_secrets.py --tb=short`
   returned **79 passed**, three existing warnings, 17.18 seconds.
10. `git diff --check`: passed.
    `/home/ammosync/trigger-crm-venv312/bin/ruff check --select E9,F63,F7,F82 tank/trigger_crm.py tank/trigger_commands.py tank/command.py tests/test_trigger_crm.py tests/trigger_bot_b1/test_engine.py`:
    all checks passed. Earlier unrestricted Ruff on CRM/commands/tests reported
    12 style findings, including existing import ordering/regex aliases; the two
    aliases introduced by this gate were removed. No full style clearance claimed.

## Evidence still required

- Founder binds his own tenant through `TRIGGER_CRM_TENANT_BINDINGS` and a unique
  `TRIGGER_CRM_PAT_…` setting, with its value entered only by the founder. No live
  configuration was inspected to determine whether this has already happened.
- Separate connector image fix #601 must be merged for the founder's live test.
  No merge/deploy status is inferred here.
- Founder browser acceptance: admin lists leads, confirms creation of a real
  contact, lists contacts, then observes refusal from his unbound second tenant.
  **No founder browser screenshots are available. Live completion is unproven.**
- Claude opens the PR; exact final-head hosted Tank and Workspace CI results must
  then be recorded on it. No hosted CI result is claimed before a PR exists.
