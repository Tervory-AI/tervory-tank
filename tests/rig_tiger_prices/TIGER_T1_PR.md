# Tiger T1: catalogue competitors and price position

PR #599, branch `codex/tiger-competitors`, includes main `ecef216b` (#602), including `b2fa83bd` (#598) and `305b833b` (#589). The merges keep Trigger's format tool, Tiger's matching tools, main's identity/Trigger schema changes, and CLI code mode. The founder merges.

Tiger reads the tenant's saved Tiger Source sites and Rig's catalogue, discovers public product pages using sitemaps and GTIN searches, and returns matches and price position through existing `/chats` cards. Valid GTIN identity confirms automatically; brand plus MPN stays suggested until Confirm. Titles and competitor SKUs never prove identity. Confirmed matches use existing feed links and ordinary six-hour watches. Receipts use literal parameterized SQL, cost $0 and explicitly record `tiger`; existing callers still record `trigger`.

No model calls, paid search, production SQL, deployment, new UI or runtime configuration changes were performed. Founder-browser acceptance and screenshots remain missing.

## Re-review at a2b5e9c1

| Item | Change and proof |
| --- | --- |
| 1 | [schema.sql:88](../../agents/tiger/schema.sql#L88) checks SELECT, INSERT and UPDATE separately for each of the four T1 tables and grants only when any privilege is missing. Existing RLS changes already check pg_class flags; policy creation checks pg_policies; column/index/table creation uses native IF NOT EXISTS. Ordinary repeated migrations therefore do not rewrite existing T1 catalog rows. [Concurrent test:955](../test_tiger_competitors.py#L955) runs the complete ordinary watch migration as non-superuser/non-BYPASSRLS agent_tiger after the actual _ownership pass: eight connections × twenty runs, both with RLS off and on, **320 runs, zero errors**. Table and policy xmin values remain unchanged. [Privilege repair:993](../test_tiger_competitors.py#L993) revokes only UPDATE on one table, verifies it is restored, and verifies the other tables' catalog rows are untouched. Existing run-twice and non-owner BYPASSRLS-admin tests remain. |
| 2 | [rig_watch.py:487](../../agents/tiger/rig_watch.py#L487) applies the same string, length, nonzero and GS1 check-digit rules as Tank's tiger_gtin before queuing/reserving searches. Invalid SKUs are skipped inside the bounded local loop. [Test:1012](../test_tiger_competitors.py#L1012) skips 200 invalid SKUs then reserves only the valid SKU's search; it covers a wrong check digit, zeros, wrong length, nonstring and missing values. |
| 3 | [app.py:262](../../agents/tiger/app.py#L262) retains finished-site warning details only in the single mutable match_runs.progress row. The cursor's finished-site summaries and each jobs.result contain warning_count, never those warning lists. Active-site warnings remain only in its cursor until completion; the transaction moves them into progress along with the next cursor/result. [Test:1030](../test_tiger_competitors.py#L1030) runs forty real persisted slices with three finished sites and 600 warnings, preserves every warning in run progress, and verifies every result's JSON and PostgreSQL storage size stay below **2,048 bytes**, with total result storage below 40 × 2,048 bytes. |

**Focused result: 86 passed, 3 warnings, exit 0, 187.23 seconds.** This includes the existing isolation, reader, receipt, no-model and role-migration cases plus all re-review regressions. Both Ruff commands and both whitespace checks pass. An initial run stopped at a test-fixture assertion because its supposedly invalid GTIN had a valid check digit; the fixture was corrected and the entire focused suite rerun successfully.

Exact commands from `/workspace/codex-tiger-t1`:

```sh
TMPDIR=/workspace/codex-tiger-t1-round2-tmp .venv/bin/python tests/rig_tiger_prices/run_t1_offline.py tests/test_tiger_competitors.py --maxfail=1
.venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
.venv/bin/ruff check agents/tiger/app.py agents/tiger/rig_watch.py --select E9,F
git diff --check
git diff origin/main --check
```

**CI is the full-suite test of record.** The exact final-head SHA, hosted tank job link, conclusion and full-suite counts are recorded in [PR #599's Final-head CI validation](https://github.com/Tervory-AI/tervory-tank/pull/599) after that head's run completes. That job runs the unchanged `.github/scripts/offline_suite.py`; the older results below are historical, not substitutes for final-head CI.

## Round-two fixes

| Review | Change and proof |
| --- | --- |
| 1 | Main `305b833b` and the later `b2fa83bd` merged with both sides retained in [command.py](../../tank/command.py) and [schema.sql](../../tank/schema.sql). |
| 2 | [test_mcp_client.py:245](../test_mcp_client.py#L245) expects the fifth receipt argument, `trigger`. Removing Tiger DDL from Tank removes the DuplicateSchema and idempotent-shape regressions. Whole-suite results appear below. |
| 3 | The four T1 tables now belong to [Tiger's schema:15](../../agents/tiger/schema.sql#L15). [RLS:56](../../agents/tiger/schema.sql#L56) follows the command-thread sentinel, including ELSE disabling FORCE/RLS, IF NOT EXISTS policies, and a role-existence-gated grant. [Room startup:309](../../agents/tiger/app.py#L309) migrates through the raw room pool before serving requests. Tank no longer creates or alters these tables or the agent_tiger schema. |
| 4 | [Browser service handling:85](../../agents/tiger/app.py#L85) treats every non-2xx catalogue response as a non-challenge failure. Only site status/markers from successful browser JSON can block discovery. [Tests:827](../test_tiger_competitors.py#L827) exercise service 401/403 through the real gate and assert no human_check flag or access_queue entry. |
| 5 | [Traversal:577](../../agents/tiger/rig_watch.py#L577) records URL warnings and continues after sitemap/product/search transport errors; only robots transport failures end a site. [Tests:804](../test_tiger_competitors.py#L804) prove both sitemap and product failures leave the default sitemap, other candidates and search available. |
| 6 | [Fetch/render deadlines:67](../../agents/tiger/app.py#L67) are 12/15 seconds overall, below the 45-second job slice, including trickling bodies. [Final attempt handling:216](../../agents/tiger/app.py#L216) saves failed progress; [card loading:1574](../../tank/access.py#L1574) reconciles a crashed exhausted job. [Tests:843](../test_tiger_competitors.py#L843) cover deadlines; [tests:913](../test_tiger_competitors.py#L913) cover handler exhaustion and crash reconciliation. |
| 7 | [Continuation storage:242](../../agents/tiger/app.py#L242) reads the catalogue from its single root job, stores the cursor once in match_runs, and writes only root_job_id into child input. Result, child enqueue and cursor update commit together. [Traversal:483](../../agents/tiger/rig_watch.py#L483) skips unusable/already-confirmed SKUs inside the bounded local loop. [2,000-SKU tests:878](../test_tiger_competitors.py#L878) assert serialized input and PostgreSQL pg_column_size(input) under 100 bytes, one catalogue copy, no job-input cursor, and at most six slices for no GTINs. |
| 8 | This document replaces the previous deployment and validation claims. Historical local six-failure output is not evidence of hosted-main failures: main's hosted tank job passed at cf95a07e. Final-head hosted evidence is recorded below and in the PR validation. |

## Ownership and deployment

[Role proof:702](../test_tiger_competitors.py#L702) creates disposable NOLOGIN roles and uses the actual chassis `_ownership` pass. It runs Tiger's migration twice as non-superuser/non-BYPASSRLS agent_tiger, then Tank's schema twice as a non-superuser BYPASSRLS admin with no membership in agent_tiger and no CREATE privilege in its schema. Both existing-table and fresh-room cases pass. The test also enables the sentinel, runs the room migration, disables the sentinel, and verifies the ELSE branch removes RLS/FORCE. This replaces the prior superuser-based deployment-order claim.

Tiger's startup installs its schema using the room login, rather than the optional administrative pool. Repeated RLS changes check pg_class flags before ALTER, avoiding an unnecessary table lock during watch creation while Tank holds a match row. [Startup test:940](../test_tiger_competitors.py#L940) verifies matching tables exist before the application yields to serve traffic. Tank retains its existing startup migration path; its admin needs no ownership of Tiger's tables.

Changed Tank, Rig, Tiger and shared browser sources need their normal stack/image rebuilds after founder merge. Existing deploy_changed.py deploys main/ZA before room stacks; this PR does not run deployments or change compose/settings.

## Preserved matching behavior

Catalogue browser requests use anonymous contexts without loading/saving cookies, execute no page scripts/assets, and refuse redirects; a permitted product redirect is separately queued and reserved. Robots path/query rules, wildcards, longest match and Allow ties apply. The shared public-host gate reserves failures too, spaces attempts by three seconds and limits each origin to 500 attempts per UTC day. Sitemaps and cursor queues are bounded. Search/home markup supplies links only, never product identity evidence.

Every match/card/read/write is tenant scoped. Sightings bind the actual slice and root jobs, so cards use their own evidence. Position returns at most 100 matched SKUs, includes every competitor for each returned SKU within the serialized card limit, and reports pagination. Rank is 1 plus cheaper comparable competitors; difference is own price minus cheapest comparable competitor. Missing prices and different currencies are excluded from arithmetic. Existing watch readers/OCR and handmade-watch settings remain intact.

## Round-two validation (historical)

**Hosted Tank offline suite: PASS on merge head `3e40f87f59e4aef127e15f51b3fc5d9bea1c0dc3`.** [tank job](https://github.com/Tervory-AI/tervory-tank/actions/runs/41633493659/job/125909376296): main **6,675 passed, 42 skipped, 1,799 subtests passed**; tiger_g5 **46 passed**; zenas_regulation_alerts **40 passed**. All three runs exited 0; the entrypoint finished in 875 seconds. Workspace, security and command acceptance also passed. The exact final documentation-head SHA, tank conclusion and job link are recorded in [PR #599 validation](https://github.com/Tervory-AI/tervory-tank/pull/599) after that head's CI completes.

**Focused Tiger: 77 passed** ([raw output](evidence/tiger_t1_round2_focused.txt)). The PostgreSQL pg_column_size assertion added afterward passed separately: **1 passed**. After merging main's CLI code mode, the combined schema/MCP/case-study/CLI/Tiger-planner regression selection passed: **26 passed**. Both Ruff commands and whitespace checks exited 0.

**Local whole-entrypoint attempt: exit 1**, with main **6,217 passed, 11 failed, 39 skipped, 1,799 subtests passed**; tiger_g5 **46 passed**; zenas_regulation_alerts **40 passed**. The main worker timed out at 93%, so this local run did not execute every collected test. It began before the later CLI merge; the successful hosted run above validates the merged implementation. The initial temporary-directory attempt also hit Errno 122. These local failures are not described as hosted-main failures and do not excuse red CI.

| Local failure | Error line |
| --- | --- |
| test_rx1_scans.py::test_planted_key_vulnerable_dependency_and_injection_are_found | :162 `assert False is True` |
| test_rx1_scans.py::test_scan_makes_no_network_call | :198 `assert 0 >= 1` |
| test_rx1_scans.py::test_file_source_stays_inside_the_tenant | :229 `assert False is True` |
| test_rx1_scans.py::test_rows_and_logs_do_not_contain_the_secret | :251 `assert []` |
| test_rx1_scans.py::test_failing_gitleaks_falls_back_without_leaking_stderr | :300 `IndexError: list index out of range` |
| test_rx1_scans.py::test_git_bundle_is_scanned_without_fetching | :338 `assert False` |
| test_base_engine_terms_approved.py::test_flat_app_layout_without_skills_dir_boots_empty | :191 engine terms were nonempty |
| test_workers_command.py::test_task_runner_reuses_local_branch_and_pr_for_followup | :399 `assert 1 == 0`; captured worker detail: `[Errno 122] Disk quota exceeded` |
| test_radix_osv_real.py::test_dockerfiles_are_collected_from_a_tree | :149 `assert [] == ['svc/Dockerfile', 'web.dockerfile']` |
| test_zenas_govza_nightly_resume.py::test_cancelled_ingest_does_not_acknowledge_unstored_pdf[govza-regulations-False] | :152 `assert 'stalled' == 'ok'` |
| test_b3b_base_wiring.py::test_scrape_1_2_0_returns_joined_html_capped_at_400_kb | worker timeout/crash after 300 seconds |

The temporary directory under this checkout's .venv affected path-sensitive scanner exclusions and flat-layout engine lookup. Those areas are unchanged from main. A follow-up run moves temporary files outside the checkout; its result is reported in the PR validation. Hosted CI's complete, successful run remains the merge-head gate.

Hosted tenant isolation and nonroot services passed on merge head `3e40f87f`: [workflow run](https://github.com/Tervory-AI/tervory-tank/actions/runs/41633493977).

Exact local commands, from `/workspace/codex-tiger-t1`:

```sh
.venv/bin/python tests/rig_tiger_prices/run_t1_offline.py tests/test_tiger_competitors.py --maxfail=1
TMPDIR=/workspace/codex-tiger-t1/.venv/t1-proof/tmp-full .venv/bin/python tests/rig_tiger_prices/run_t1_offline.py --tank
.venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
.venv/bin/ruff check agents/tiger/app.py agents/tiger/rig_watch.py agents/_brain/browser.py --select E9,F
git diff --check
git diff origin/main --check
TMPDIR=/workspace/codex-tiger-t1/.venv/t1-proof/tmp-full .venv/bin/python tests/rig_tiger_prices/run_t1_offline.py tests/test_tiger_competitors.py::test_large_catalogue_continuation_input_is_only_a_run_reference
TMPDIR=/workspace/codex-tiger-t1/.venv/t1-proof/tmp-full .venv/bin/python tests/rig_tiger_prices/run_t1_offline.py tests/test_command_code.py tests/test_schema.py tests/test_mcp_client.py::test_initialize_discovery_call_json_and_sse tests/test_case_study_reports.py::test_tiger_delivery_and_price_bands_do_not_invent_detection_time tests/test_tiger_competitors.py::test_explicit_planning_requires_tiger_squad_and_never_uses_a_model
```

The full runner invokes `.github/scripts/offline_suite.py` unchanged: main, tiger_g5 and zenas_regulation_alerts, with its normal quarantine/exclusions and strict offline socket rules. It prepares the CI database names on disposable loopback postgres:16 with trust authentication and removes that container afterward; no production DSN is used. Local settings are four workers and the script's supported budget scale of two. The first full attempt hit Errno 122 in the shared temporary directory; the subsequent attempt used TMPDIR inside this checkout and has the limitations listed above. Python requirements, Forge's hash-pinned requirements and workspace npm packages were installed before the run. The earlier missing-TypeScript/browser-local failures are historical evidence only, not a reason to accept failing hosted tests.

## Founder-browser proof still required

Missing: Custom Nation's chosen two or three Source links saved in Tiger Plugins; tiger.match Confirm/$0 receipt with returned page/barcode evidence in /chats; tiger.position after ordinary checks with prices, stock, sources, check times, rank and difference; another tenant seeing none of those rows. No founder screenshots exist, and synthetic tests do not satisfy live acceptance. The Tiger page remains deferred to approved Figma page “9 · Tiger price position”.
