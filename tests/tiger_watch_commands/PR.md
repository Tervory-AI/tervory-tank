# Tiger TG1: manage watches from /chats

Branch: `codex/tiger-w3`. Base: `a870ade14bce0b15fb1fb88fbf80d868029f253f`
(#614 merged). Implementation and tests are unchanged since `3034093a`;
subsequent commits record evidence. Claude opens the PR; the founder merges.

## Behavior

`tiger.watches` lists the actor's watches, with existing Name and Result fields.
Full watch fields remain in the result data. Pause, resume and remove look up
the exact URL only within that tenant, and require server-bound Confirm before
any room request. Missing or foreign URLs return 404. Reads retain the normal
pending card and ordinary Confirm dispatch; they are outside both mutation lists.

`tiger.watch.bulk` accepts 1–50 URLs. It uses the room's POST /watchlist and
the single-watch defaults, counts existing URLs (including duplicates inside
the batch and concurrent room conflicts), and continues past duplicates.
Both single and bulk creation now send `every="1d"`. The accepted interval
values exactly match EVERY_OPTIONS: 15m, 1h, 6h, 12h, 1d; invalid values fail
argument validation before any room call. The founder explicitly supplied this
default and authorized repairing the existing single-watch gap.

Bulk uses the same paid flag and `paid_run` card kind as `tiger.watch`.
The card's paid-work check combines successfully with server-side confirmation.
Watch registration is code-only and records $0; duplicate URLs create no new
watches. Future checks retain the room's existing execution path. No model
estimate or future check charge is fabricated. Typed watch-management commands
use the existing code planner and never call a model to select these tools.

Bulk creates are sequential room operations. A non-duplicate room failure stops
the card; any earlier successful creates remain. Attempted cards are not retried
automatically. This preserves the existing card failure behavior and does not
claim a transaction across independent room requests.

## Changes by file and line

| File and line | Change |
| --- | --- |
| `tank/tiger_watch_commands.py:12` | Bounded bulk arguments, approved daily default, existing WatchArgs validation. |
| `tank/tiger_watch_commands.py:25` | All room calls reuse `_tiger_call` and `_tiger_response`, with actor-owned tenant identity and existing response filtering. |
| `tank/tiger_watch_commands.py:40` | Reuse `code_receipt`, agent tiger, $0. |
| `tank/tiger_watch_commands.py:45` | Identity/grant-protected router; tenant-filtered reads, confirmed exact-URL mutations, bulk creation and duplicate counts. |
| `tank/command.py:43` | Add five tools only to Tiger's inventory. |
| `tank/command.py:1018` | Repair WatchArgs with the approved interval literal and daily default. |
| `tank/command.py:1282` | Five adapters beside tiger.read; bulk matches single-watch paid/card classification. |
| `tank/command.py:1492` | Add four changing tools beside base.list.save to identity-only adapter body handling. |
| `tank/command.py:1686` | Add the same four tools to confirmed dispatch; exclude the read. |
| `tank/command.py:1859` | Explicit watch-management commands use code planning. |
| `tank/main.py:4208` | Mount the new router beside base_lists. |
| `tests/test_personal_tokens.py:49` | Update the Tiger allowed-tools expectation. No direct CLI route expansion is needed: existing action/card endpoints dispatch internally with Workspace assertions. |
| `tests/test_command.py:49` and `:956` | Update the two existing Tiger inventory expectations. |
| `tests/test_tiger_watch_commands.py:33` | Actual Tiger ASGI routes with MemoryStore, fake DNS/transport, deliberately leaky list responses, placeholder data only. |
| `tests/test_tiger_watch_commands.py:108` | Tenant isolation, receipts, confirmation refusal, exact URL matching, scheduler pause/resume, duplicate counts, URL/interval rejection, defaults and no-model planning. |
| `tests/test_tiger_watch_commands.py:260` | Real persisted pending cards and Confirm through Command, paid bulk plus confirmed dispatch, one execution/receipt on repeated Confirm. Disposable PostgreSQL only. |
| `tests/test_tiger_watch_commands.py:297` | Compare both interval enums against the actual Tiger page options. |
| `tests/tiger_watch_commands/evidence/` | Raw check outputs, including initial environment failures and their successful reruns. |

The existing `tank/Dockerfile` already uses `COPY *.py`; it includes the new
module without an edit. No Workspace, room, schema, setting, deployment or
runtime-config file changed. No merge from origin/main was performed.

## Card limits requiring Figma

The cards cannot show a watch's check interval, threshold, alert kinds or enabled
state without an approved Figma frame. Changing interval, threshold or alert
kinds through a new visible /chats control waits for that frame. This gate adds
no page, presenter label, empty state, error copy or visible interval control.

## Exact validation commands and results

Commands ran from `/workspace/codex-tiger-w3`, mounted as `/repo` inside the
temporary `codex-tiger-w3-tests` container. It uses the already-cached Tank image
for the base commit, Python 3.12.16 and a system-package virtualenv. Test sockets
are restricted to loopback/Unix sockets. Test PostgreSQL and Redis are new,
named disposable containers, never production services or data.

```sh
docker exec --user root codex-tiger-w3-tests /repo/.venv/bin/python -m pytest tests/test_tiger_watch_commands.py -q --tb=short --timeout=120 --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1 -k 'not real_cards'
docker exec --user root -e POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32871/postgres codex-tiger-w3-tests /repo/.venv/bin/python -m pytest tests/test_tiger_watch_commands.py::test_real_cards_confirm_paid_bulk_and_code_changes_once -q --tb=short --timeout=300 --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1
```

**36 passed, 1 deselected in 9.88s; 1 passed in 8.65s.** All 37 TG1 cases pass.
The first uncommitted harness attempt seeded watches before setting fake DNS
(35 setup errors, 1 pass); moving fake DNS before seeding fixed the harness.

```sh
docker exec --user root -e POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32871/postgres -e TIGER_MAIL_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32871/postgres codex-tiger-w3-tests /repo/.venv/bin/python -m pytest tests/test_tiger*.py tests/test_tg2_tiger_watchlist.py tests/tiger_alert_email/ tests/tiger_alert_page/ tests/test_command.py tests/test_personal_tokens.py -n 2 -q --tb=short --timeout=300 --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1
```

**459 passed, 6 failed in 391.27s.** See `evidence/tiger-command-suite.txt`.
Five failures came from running G5 concurrently against the same test cluster:
its objects depended on the global agent_tiger role that migration tests drop.
The first traceback identifies the conflicting G5 test database. The sixth
failure, a PDF block test, also failed in isolation (`evidence/pdf-reproduction.txt`):
the test container lacked the existing dev dependency pypdf. Installing the
repository's `pypdf==6.21.4` pin and using a fresh cluster fixed all six below.
No production code changed to address these harness failures.

```sh
docker exec --user root -e POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32873/postgres codex-tiger-w3-tests /repo/.venv/bin/python -m pytest 'tests/test_tiger_competitors.py::test_room_migration_and_nonowner_tank_admin_after_role_ownership[True]' 'tests/test_tiger_competitors.py::test_room_migration_and_nonowner_tank_admin_after_role_ownership[False]' 'tests/test_tiger_competitors.py::test_room_schema_concurrently_repeats_without_catalog_writes[False]' 'tests/test_tiger_competitors.py::test_room_schema_concurrently_repeats_without_catalog_writes[True]' tests/test_tiger_competitors.py::test_room_schema_repairs_only_missing_table_privileges tests/test_tiger_public_policy.py::test_pdf_block_records_url_and_prevents_a_second_download -q --tb=short --timeout=300 --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1
```

**6 passed in 26.06s.** See `evidence/environment-rerun.txt`. Every case in the
465-case selection has a passing result; this is an initial run plus focused
reruns, not a claim of one uninterrupted green 465-case run.

```sh
docker exec --user root -e POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32871/postgres -e TIGER_MAIL_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32871/postgres codex-tiger-w3-tests /repo/.venv/bin/python -m pytest tests/tiger_g5/ -q --tb=short --timeout=300 --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1
docker exec --user root -e POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32871/postgres codex-tiger-w3-tests /repo/.venv/bin/python -m pytest tests/tiger_playbooks/ tests/tiger_before_deploy/ tests/tiger_price_read/ tests/rig_tiger_prices/ -q --tb=short --timeout=300 --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1
docker exec --user root -e POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32871/postgres -e TENANT_BUS_REDIS_URL=redis://127.0.0.1:32872/0 codex-tiger-w3-tests /repo/.venv/bin/python -m pytest tests/tenant_bus/test_tiger_history.py -q --tb=short --timeout=300 --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1
```

**46 passed in 150.91s; 77 passed, 1 skipped in 74.99s; 2 passed in 31.87s.**
Raw results: `evidence/tiger-g5.txt`, `evidence/tiger-additional.txt`,
`evidence/tiger-history.txt`. The existing skip is the unfilled, human-labeled
100-page gold set in `tests/tiger_before_deploy/test_before_deploy.py:181`.

```sh
docker exec --user root codex-tiger-w3-tests /repo/.venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
docker exec --user root codex-tiger-w3-tests /repo/.venv/bin/python -m pytest tests/test_secrets.py -q --tb=short
git diff --check
git diff origin/main --check
```

**Ruff passed; 2 secret checks passed in 18.40s; both whitespace checks passed.**
Outputs: `evidence/ruff.txt`, `evidence/secrets.txt`. Captured warning lines had
trailing whitespace; it was trimmed from the three affected logs before the
final successful whitespace checks. Test result text is otherwise unchanged.
The initial secret-scan
attempt found Git absent from the test image; installing Git in that temporary
container and setting its safe directory allowed the scanner to run.

Setup reused the cached Tank/Workspace images; no new provider, service, key or
repository dependency was added. A temporary container supplied the image's Node
and npm binaries for the existing TypeScript tests. These setup commands passed:

```sh
docker exec --user root codex-tiger-w3-tests python -m venv --system-site-packages /repo/.venv
docker exec --user root codex-tiger-w3-tests /repo/.venv/bin/pip install pytest==9.1.1 pytest-asyncio==1.4.1 pytest-xdist==3.8.0 pytest-timeout==2.4.0 pytest-socket==0.8.1 ruff==0.17.2 aiosmtpd==1.4.6
docker exec --user root codex-tiger-w3-tests /repo/.venv/bin/pip install playwright==1.64.1
docker exec --user root codex-tiger-w3-tests node /usr/local/lib/node_modules/npm/bin/npm-cli.js ci --include=dev --no-audit --no-fund --prefix workspace
docker exec --user root codex-tiger-w3-tests /repo/.venv/bin/python -m playwright install --with-deps chromium
docker exec --user root codex-tiger-w3-tests /repo/.venv/bin/pip install pypdf==6.21.4
```

Each finished source/evidence file was committed and pushed separately using
`git add <file>`, `git commit -m '<description>'`, and
`git push origin codex/tiger-w3`; the first push used `-u`. Every push succeeded.

## CI and founder-browser acceptance pending

Read-only GitHub metadata showed no open PR for this branch. Claude must open
the PR and record the final-head Tank and Workspace CI URLs/results. No CI
success is claimed. No deployment, live SQL or founder-data mutation was made.

No founder-browser screenshots were captured or supplied. Acceptance remains:
the founder lists watches in his own /chats, pauses one and verifies no new
Tiger check, resumes it, removes another, then confirms one bulk card containing
five real product URLs and verifies all five on Tiger. Attach screenshots of
those actual actions after deployment. Offline tests are not founder acceptance.
