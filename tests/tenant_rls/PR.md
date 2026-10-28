# Tenant RLS and nonroot container handoff

## 2026-10-28 16:44 PDT (UTC-07:00) / 2026-10-28 23:44 UTC

Branch: `codex/tenant-rls`. Evidence head before this report: `722dea0`.
Base: `7a13687de256896c488a0f28e0906fbcbce5b046`. No existing duplicate RLS branch/PR was found before starting.

Opt-in migrations under `db/migrations/tenant_rls` cover 13 schemas. Each enables and forces RLS, with permissive and restrictive tenant policies using `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid` for reads and writes. Migrations are transactional, repeatable, and are never loaded by service startup. Founder applies after review/merge; nothing has been applied to production.

Tank and chassis set transaction-local tenant context on pooled checkout. Tenant role must be neither superuser nor BYPASSRLS when policies are active. Separate administrative connection settings are name-only placeholders in `.env.example`; startup validates the configured administrative role has BYPASSRLS. Existing application tenant checks remain. Task handlers use the persisted job owner; cross-tenant discovery uses the separate administrative connection.

Validation performed using disposable local PostgreSQL and pinned Python 3.12 dependencies:

- `RLS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/postgres /opt/testenv/bin/python -m pytest -q tests/test_tenant_rls.py`: 7 passed, 12 warnings, 20.05s at `e5c4406`. Actual bootstrap schemas: 207 tenant tables, each checked for own/cross reads and writes, unset/empty context, founder access; migrations run twice. Probe fixtures relax domain constraints/triggers only inside disposable databases; this proves policy isolation, not domain validity.
- Existing tests at `50e1d8b`: `/opt/testenv/bin/python -m pytest -q tests/test_agent_chassis.py tests/test_agent_roles.py tests/test_tank_ladder.py tests/test_tank_tenant_boundaries.py tests/test_tank_batches.py tests/test_tank_batch_providers.py tests/test_tank_review_regressions.py tests/test_bf2_tank_guards.py tests/test_tank_one_door.py tests/test_command.py tests/test_secrets.py`: 239 passed, 23 warnings, 153.31s. Both POOL_SCHEMA_DATABASE_URL and RIG_TEST_DATABASE_URL pointed only at the disposable localhost database above.
- `python tests/tenant_rls/container_smoke.py`: all four images built and started with network disabled; health HTTP 200; litellm uid10001, searxng uid977, site uid1000, tiger uid1000. Uses an empty model list and an explicit local no-key development switch only in the smoke fixture; Searx fixture removes the unavailable Ferry proxy. No model calls or live scans.

Open findings / gaps: Rig key authentication needs a narrowly scoped administrative bootstrap lookup before the tenant can be known; authenticated public/internal Rig routes then need to activate the accepted tenant context. Final runtime coverage review and CI workflow publication are pending. Do not activate production RLS yet. Existing site `/data` volumes require suitable ownership before a nonroot container can write. Full repository/model integration suites have not been run.

Publication: branch pushed; no PR opened (Claude owns PR creation), no main push or merge. Founder acceptance pending. No live screenshots or customer proof created. Zenas US means Boston; ZA means the dedicated South Africa host.

## 2026-10-28 16:48:24 PDT (UTC-07:00) / 2026-10-28 23:48:24 UTC

Evidence head `37b2a00`; branch remains `codex/tenant-rls`. Rig bootstrap, public/internal accepted tenant activation, trusted room query/body scope, configured shopper owner, authenticated legacy admin discovery and administrative schedule discovery are implemented. Tank request middleware resets dependency context, and vault authorization scopes its already accepted workspace before the squad lookup.

New RLS suite on code `add001d` plus the subsequently committed test `594bb43`: `docker exec -e RLS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/postgres tervory-rls-python /opt/testenv/bin/python -m pytest -q tests/test_tenant_rls.py`: **8 passed, 12 warnings, 24.89s**. Added real RLS Rig key bootstrap/authentication, two owners, accepted origin and rejected origin, request reset and empty-context checks. Prior combined RLS + six existing Rig files: **71 passed, 12 warnings, 30.50s** on `51a659c`. These fixtures use synthetic credentials locally only.

Workflow `.github/workflows/tenant-rls.yml` pushed and running; no hosted green result claimed yet. Independent reviewer confirmed the actual table matrix and inspected helper/bootstrap fixes with no new finding, requesting final head/inventory/CI proof. Outbound reviewer update encountered a local connector transport failure; no commit/push failure.

Tenant sources: Tank route/task/batch request models; vendor/feedback/skill/configuration bodies; typed product bodies across Base/Tiger/Tisan/Trigger/Zenas and included Tank routers are scoped after existing dependencies accept them. `BatchRequest.tenant_id` is first persisted request owner and existing homogeneous checks remain. Explicit query/path tenant wins body fallback; authenticated dependency Actor wins both. Raw Rig room reads validate query/body UUID agreement, retailer operations validate the existing internal credential and body UUID; public API uses the key-table owner, never shopper body. Chassis handlers use persisted job owner; founder/global discovery uses a separately configured administrative pool. Ghost is file-backed with no DATABASE_URL; its body tenant sources are retained in the source audit below and do not imply SQL pooling.

The following conservative static source inventory includes body accesses, typed tenant-bearing parameters and supporting helpers (not all entries are endpoints). Actor/Scope/Reviewer entries are accepted dependency/context objects, not raw request bodies. This is a source audit, not proof of every route under live RLS. Nested enclosing functions may repeat child accesses. Current known remaining activation audit gaps include background platform/training loops and raw-body paths outside the explicitly tested routes. Production activation remains blocked until manual role provisioning and that audit; no SQL has run in production.

| Location | Function | Tenant source |
|---|---|---|
| `agents/_chassis/chassis/app.py:50` | `create_app` | `body.tenant_id` |
| `agents/_chassis/chassis/app.py:143` | `enqueue` | `body.tenant_id` |
| `agents/base/app.py:146` | `context_trial` | `body.tenant_id`, `body: ContextTrial` |
| `agents/base/app.py:172` | `_context_trial` | `body.tenant_id`, `body: ContextTrial` |
| `agents/base/app.py:269` | `base_run` | `body.tenant_id`, `body: BaseRun` |
| `agents/base/app.py:316` | `base_retry` | `body.tenant_id`, `body: BaseRetry` |
| `agents/base/app.py:327` | `base_rerun` | `body.tenant_id`, `body: BaseRerun` |
| `agents/ghost/app.py:277` | `create_app` | `data.get('tenant_id')`, `data['tenant_id']`, `payload.get('tenant_id')` |
| `agents/ghost/app.py:725` | `autumbra_hands_set` | `data.get('tenant_id')` |
| `agents/ghost/app.py:755` | `autumbra_intel_consume` | `data.get('tenant_id')` |
| `agents/ghost/app.py:779` | `autumbra_webhook` | `data.get('tenant_id')` |
| `agents/ghost/app.py:859` | `autumbra_exercise_run` | `data.get('tenant_id')` |
| `agents/ghost/app.py:882` | `autumbra_queue_fixture_attack` | `data.get('tenant_id')` |
| `agents/ghost/app.py:939` | `autumbra_queue_undo` | `data['tenant_id']` |
| `agents/ghost/app.py:1011` | `autumbra_queue_approve` | `data['tenant_id']` |
| `agents/ghost/app.py:1061` | `autumbra_weekly_receipt_page` | `payload.get('tenant_id')` |
| `agents/ghost/app.py:1131` | `autumbra_enforce_plan_create` | `data['tenant_id']` |
| `agents/ghost/app.py:1154` | `autumbra_enforce_plan_destroy` | `data['tenant_id']` |
| `agents/ghost/app.py:1172` | `autumbra_owner_update` | `data.get('tenant_id')` |
| `agents/rig/app.py:284` | `_room_read` | `body.get('tenant_id')` |
| `agents/rig/rigbox/retailer_api.py:21` | `retailer_operation` | `body['tenant_id']` |
| `agents/rig/rigbox/three_d/api.py:114` | `entitlement` | `body.tenant_id`, `body: Entitlement` |
| `agents/tiger/app.py:239` | `_fields` | `body.tenant_id` |
| `agents/tiger/app.py:268` | `create_watch` | `body: WatchIn` |
| `agents/tiger/app.py:291` | `update_watch` | `body.tenant_id`, `body: WatchPatch` |
| `agents/tisan/app.py:123` | `eval_case` | `body.tenant_id`, `body: EvalCase` |
| `agents/trigger/app.py:93` | `voice_operation` | `body.tenant_id`, `body: VoiceOperation` |
| `agents/zenas/app.py:315` | `post_consent` | `body.tenant_id`, `body: ConsentIn` |
| `agents/zenas/app.py:348` | `post_matter` | `body.tenant_id`, `body: MatterIn` |
| `agents/zenas/app.py:369` | `post_document` | `body.tenant_id`, `body: DocumentIn` |
| `agents/zenas/app.py:391` | `post_review` | `body.tenant_id`, `body: ReviewIn` |
| `agents/zenas/app.py:528` | `post_retrieve` | `body.tenant_id`, `body: RetrieveIn` |
| `agents/zenas/app.py:549` | `post_cite_check` | `body.tenant_id`, `body: CiteIn` |
| `agents/zenas/app.py:565` | `post_rule_card` | `body.tenant_id`, `body: RuleCardIn` |
| `agents/zenas/app.py:598` | `post_approve_card` | `body.tenant_id`, `body: ApproveCardIn` |
| `agents/zenas/app.py:651` | `post_case_facts` | `body.tenant_id`, `body: CaseFactsIn` |
| `agents/zenas/app.py:679` | `post_match` | `body.tenant_id`, `body: MatchIn` |
| `agents/zenas/app.py:698` | `post_apply` | `body.tenant_id`, `body: ApplyIn` |
| `agents/zenas/app.py:718` | `post_compose` | `body.tenant_id`, `body: ApplyIn` |
| `agents/zenas/app.py:739` | `post_plain` | `body.tenant_id`, `body: PlainIn` |
| `agents/zenas/app.py:757` | `post_release` | `body.tenant_id`, `body: ReleaseIn` |
| `agents/zenas/app.py:791` | `post_tenant` | `body.tenant_id`, `body: TenantIn` |
| `agents/zenas/app.py:820` | `post_clause` | `body.tenant_id`, `body: ClauseIn` |
| `agents/zenas/app.py:851` | `post_playbook` | `body.tenant_id`, `body: PlaybookIn` |
| `agents/zenas/app.py:879` | `post_draft` | `body.tenant_id`, `body: DraftIn` |
| `agents/zenas/app.py:910` | `post_contract_review` | `body.tenant_id`, `body: ContractReviewIn` |
| `agents/zenas/app.py:954` | `post_answer` | `body.tenant_id`, `body: AnswerIn` |
| `tank/access.py:344` | `browser_rpc` | `data['tenant_id']` |
| `tank/access.py:433` | `human_action` | `body.tenant_id` |
| `tank/access.py:998` | `rig_tiger_update` | `body.tenant_id` |
| `tank/access.py:1076` | `archived_page` | `body.tenant_id` |
| `tank/access.py:1138` | `social_page` | `body.tenant_id` |
| `tank/admin.py:1262` | `put_price_book` | `body.tenant_id`, `body: PriceBody` |
| `tank/agent_skills.py:327` | `candidate_files` | `body: Candidate` |
| `tank/agent_skills.py:380` | `submit` | `body.tenant_id`, `body: Candidate` |
| `tank/agent_skills.py:500` | `guard_base_run` | `body.tenant_id` |
| `tank/agent_skills.py:539` | `candidate` | `body: Candidate` |
| `tank/base_product.py:103` | `build_router` | `body.tenant_id` |
| `tank/base_product.py:165` | `start` | `body.tenant_id`, `body: Selection` |
| `tank/base_product.py:182` | `upload` | `body.tenant_id` |
| `tank/base_product.py:295` | `import_apollo` | `body.tenant_id`, `body: ApolloUpload` |
| `tank/base_product.py:340` | `create_audit` | `body.tenant_id`, `body: AuditSample` |
| `tank/base_product.py:353` | `review_audit` | `body.tenant_id`, `body: AuditReview` |
| `tank/base_product.py:403` | `context_receipt` | `body.tenant_id`, `body: CreditReceipt` |
| `tank/command.py:98` | `allowed_tools` | `actor: Actor` |
| `tank/command.py:106` | `require_tool` | `actor: Actor` |
| `tank/command.py:165` | `owned` | `actor: Actor` |
| `tank/command.py:176` | `editing` | `actor: Actor` |
| `tank/command.py:247` | `tools` | `actor: Actor` |
| `tank/command.py:251` | `require_founder` | `actor: Actor` |
| `tank/command.py:257` | `list_squads` | `actor: Actor` |
| `tank/command.py:267` | `set_squad` | `actor: Actor` |
| `tank/command.py:288` | `squad_log` | `actor: Actor` |
| `tank/command.py:297` | `create_thread` | `actor: Actor` |
| `tank/command.py:309` | `list_threads` | `actor: Actor` |
| `tank/command.py:326` | `get_thread` | `actor: Actor` |
| `tank/command.py:340` | `rename_thread` | `actor: Actor` |
| `tank/command.py:351` | `replay` | `actor: Actor` |
| `tank/command.py:376` | `events` | `actor: Actor` |
| `tank/command.py:383` | `route_turn` | `actor: Actor` |
| `tank/command.py:417` | `finish_turn` | `actor: Actor` |
| `tank/command.py:502` | `turn` | `actor: Actor` |
| `tank/command.py:570` | `propose_build` | `actor: Actor` |
| `tank/command.py:579` | `card_action` | `actor: Actor` |
| `tank/command.py:731` | `add_followup` | `actor: Actor` |
| `tank/command.py:806` | `repo_prs` | `actor: Actor` |
| `tank/command.py:812` | `repo_pr` | `actor: Actor` |
| `tank/command.py:819` | `repo_file` | `actor: Actor` |
| `tank/command.py:1018` | `validate_action` | `actor: Actor` |
| `tank/command.py:1034` | `parse_plan` | `actor: Actor` |
| `tank/command.py:1050` | `planning_message` | `actor: Actor` |
| `tank/command.py:1082` | `current_actor` | `actor: Actor` |
| `tank/command.py:1088` | `authorized_actor` | `actor: Actor` |
| `tank/command.py:1099` | `adapter_request` | `actor: Actor` |
| `tank/command.py:1129` | `dispatch_action` | `actor: Actor` |
| `tank/command.py:1253` | `refresh_action_receipts` | `actor: Actor` |
| `tank/command.py:1269` | `execute_card` | `actor: Actor` |
| `tank/command.py:1335` | `upload_attachment` | `actor: Actor` |
| `tank/command.py:1366` | `download_attachment` | `actor: Actor` |
| `tank/command.py:1379` | `resolve_attachments` | `actor: Actor` |
| `tank/command.py:1411` | `repeat_messages` | `actor: Actor` |
| `tank/event_bus.py:259` | `publish` | `actor: Scope` |
| `tank/event_bus.py:274` | `receive` | `actor: Scope` |
| `tank/event_bus.py:284` | `settle` | `actor: Scope` |
| `tank/event_bus.py:151` | `publish` | `scope: Scope` |
| `tank/event_bus.py:161` | `receive` | `scope: Scope` |
| `tank/event_bus.py:192` | `settle` | `scope: Scope` |
| `tank/gold.py:75` | `allowed_agent` | `actor: Reviewer` |
| `tank/gold.py:125` | `summary` | `actor: Reviewer` |
| `tank/gold.py:233` | `sample_queue` | `actor: Reviewer` |
| `tank/gold.py:249` | `next_example` | `actor: Reviewer` |
| `tank/gold.py:267` | `check` | `actor: Reviewer` |
| `tank/gold.py:391` | `final_check` | `actor: Reviewer` |
| `tank/main.py:808` | `put_policy` | `body.tenant_id`, `body: PolicyRow` |
| `tank/main.py:969` | `_refuse_input` | `req: RouteRequest` |
| `tank/main.py:978` | `_preflight_mask` | `req: RouteRequest` |
| `tank/main.py:990` | `_check_route_task` | `req.tenant_id`, `req: RouteRequest` |
| `tank/main.py:1007` | `_record_local` | `req.tenant_id`, `req: RouteRequest` |
| `tank/main.py:1035` | `_cache_identity` | `req: RouteRequest` |
| `tank/main.py:1047` | `_cache_read` | `req.tenant_id`, `req: RouteRequest` |
| `tank/main.py:1075` | `_cache_write` | `req.tenant_id`, `req: RouteRequest` |
| `tank/main.py:1092` | `run_route` | `req.tenant_id`, `req: RouteRequest` |
| `tank/main.py:1558` | `_run_code_candidate` | `req.tenant_id`, `req: RouteRequest` |
| `tank/main.py:1586` | `_shadow` | `req.tenant_id`, `req: RouteRequest` |
| `tank/main.py:2400` | `route` | `body.tenant_id`, `body: RouteRequest` |
| `tank/main.py:2576` | `_batch_fallback` | `req.tenant_id` |
| `tank/main.py:2613` | `_batch_result` | `req.tenant_id` |
| `tank/main.py:2653` | `_process_batch` | `req.tenant_id` |
| `tank/main.py:2759` | `_run_task` | `req: RouteRequest` |
| `tank/main.py:2785` | `create_task` | `body.tenant_id`, `body: TaskCreate` |
| `tank/main.py:2949` | `vendor_ledger` | `body.tenant_id`, `body: VendorCall` |
| `tank/main.py:3155` | `run_one_skill` | `body: SkillRun` |
| `tank/main.py:3172` | `_run_one_skill` | `body.tenant_id`, `body: SkillRun` |
| `tank/main.py:3492` | `ledger_feedback` | `body.tenant_id`, `body: Feedback` |
| `tank/main.py:3635` | `_tiger_tenant` | `body.get('tenant_id')`, `body['tenant_id']` |
| `tank/main.py:3660` | `_tiger_keep` | `payload.get('tenant_id')` |
| `tank/main.py:3969` | `_rig_tenant` | `body.get('tenant_id')`, `body['tenant_id']` |
| `tank/market_lab_routes.py:129` | `_warning_routes` | `body.tenant_id` |
| `tank/market_lab_routes.py:27` | `call` | `body: MarketRequest` |
| `tank/market_lab_routes.py:68` | `research` | `body: ResearchRequest` |
| `tank/market_lab_routes.py:85` | `search` | `body: ResearchRequest` |
| `tank/market_lab_routes.py:154` | `workspace` | `body: WarningRequest` |
| `tank/market_lab_routes.py:160` | `training` | `body.tenant_id`, `body: WarningInternal` |
| `tank/market_lab_routes.py:181` | `series` | `body.tenant_id`, `body: WarningInternal` |
| `tank/moa.py:458` | `call_adapter` | `req.tenant_id` |
| `tank/moa.py:550` | `legal_checker` | `req.tenant_id` |
| `tank/moa.py:581` | `run_mixture` | `req.tenant_id` |
| `tank/moa.py:622` | `shadow_seats` | `req.tenant_id` |
| `tank/moa.py:673` | `routed_request` | `req.tenant_id` |
| `tank/moa.py:856` | `configure` | `body.tenant_id`, `body: Configure` |
| `tank/moa.py:870` | `benchmark` | `body.tenant_id`, `body: Promote` |
| `tank/moa.py:886` | `promote` | `body.tenant_id`, `body: Promote` |
| `tank/moa.py:461` | `call` | `req.tenant_id` |
| `tank/proof.py:249` | `csv_export` | `data['tenant_id']` |
| `tank/proof.py:264` | `pdf_export` | `data['tenant_id']` |
| `tank/research.py:145` | `register` | `req.tenant_id` |
| `tank/research.py:158` | `allowed` | `req.tenant_id`, `req: ResearchRequest` |
| `tank/research.py:194` | `record` | `req.tenant_id`, `req: ResearchRequest` |
| `tank/research.py:242` | `status` | `req: ResearchRequest` |
| `tank/research.py:247` | `research` | `req: ResearchRequest` |
| `tank/rig_brain_routes.py:37` | `build_router` | `body.tenant_id` |
| `tank/rig_brain_routes.py:56` | `run_skill` | `body.tenant_id`, `body: Skill` |
| `tank/rig_brain_routes.py:73` | `step` | `body.tenant_id`, `body: Step` |
| `tank/rig_forge_routes.py:44` | `build_router` | `body.tenant_id` |
| `tank/rig_forge_routes.py:47` | `auth` | `body: Scope` |
| `tank/rig_forge_routes.py:51` | `get_job` | `body.tenant_id`, `body: Scope` |
| `tank/rig_forge_routes.py:59` | `reserve` | `body.tenant_id` |
| `tank/rig_forge_routes.py:101` | `claim` | `body.tenant_id`, `body: Scope` |
| `tank/rig_forge_routes.py:125` | `complete` | `body.tenant_id` |
| `tank/rig_forge_routes.py:151` | `step` | `body.tenant_id` |
| `tank/rig_three_d.py:10` | `build_router` | `payload.get('tenant_id')` |
| `tank/rig_three_d.py:15` | `call` | `payload.get('tenant_id')` |
| `tank/routellm_shadow.py:76` | `configure` | `body.tenant_id`, `body: Settings` |
| `tank/routellm_shadow.py:126` | `observe` | `req.tenant_id` |
| `tank/routellm_shadow.py:176` | `save` | `req.tenant_id` |
| `tank/semantic_cache.py:111` | `scope` | `req.tenant_id` |
| `tank/semantic_cache.py:126` | `lookup` | `req.tenant_id` |
| `tank/semantic_cache.py:184` | `may_serve` | `req.tenant_id` |
| `tank/semantic_cache.py:200` | `finish` | `req.tenant_id` |
| `tank/semantic_cache.py:243` | `build_router` | `body.tenant_id` |
| `tank/semantic_cache.py:260` | `approve` | `body.tenant_id`, `body: Approval` |
| `tank/skala.py:177` | `run_skill` | `ctx: SkillContext` |
| `tank/vault_routes.py:47` | `build_router` | `data.get('tenant_id')` |
| `tank/vault_routes.py:129` | `secret` | `data.get('tenant_id')` |
| `tank/vault_routes.py:143` | `resolve` | `data.get('tenant_id')` |
| `tank/vault_routes.py:159` | `link` | `data.get('tenant_id')` |
| `tank/vault_routes.py:178` | `connection` | `data.get('tenant_id')` |
| `tank/vendor_meter.py:73` | `link` | `run: Run` |
| `tank/vendor_meter.py:135` | `bind` | `run: Run` |
| `tank/vendor_meter.py:193` | `__call__` | `body['tenant_id']` |

Founder acceptance: pending. Publish state: pushed branch, Claude to open PR, founder to merge. No screenshots, production migration, live scans or model calls.

## 2026-10-28 16:54:18 PDT (UTC-07:00) / 2026-10-28 23:54:18 UTC

Branch `codex/tenant-rls`, published code head `e70871a`. Hosted workflow [40789568582](https://github.com/Tervory-AI/tervory-tank/actions/runs/40789568582) completed **success** on tested SHA `b46a5e343f903ed6c852b616bf859554f7c0b9ef`: both isolation and nonroot-services jobs green. Later code verification remains pending; this older success does not establish final-head success.

At code `346dfbc` plus the committed snapshot regression: `docker exec` using the local disposable RLS_TEST_DATABASE_URL / POOL_SCHEMA_DATABASE_URL / RIG_TEST_DATABASE_URL and `/opt/testenv/bin/python -m pytest -q tests/test_tenant_rls.py tests/test_vault_contract.py tests/test_rig_proxy.py tests/test_rig_postgres.py tests/test_rig_page.py tests/test_rig_v5_page.py`: **44 passed, 23 warnings, 24.86s**. New repeatable-read/read-only checkout test passes.

Further existing snapshot regressions exposed native asyncpg pool compatibility: Pool.acquire does not accept transaction isolation options. Added `tenant_transaction` adapter for native and scoped pools, preserving requested snapshots in Base audit/product, proof/case studies and Trigger voice history. An intermediate automated replacement introduced a syntax error in proof and omitted one Trigger import; both corrected before current verification. A subsequent focused run found standalone proof runtime lacks admin_pool; startup now supports its existing native pool fallback. Final regression rerun is still in progress; no all-green claim. Ruff fatal-error checks and AST parsing of all changed Python files pass; broader style-only Ruff findings remain.

Background fixes: training intake/revalidation startup and candidate restore use explicit administrative context; proof repricing worker does likewise. Concurrent index startup uses raw administrative pool outside tenant transactions. Base own batch loop now discovers using administrative pool and executes each persisted owner in tenant context, overriding only the preexisting cfg tenant as before. Added a real RLS regression for that loop (pending). Typed `x_tenant_id` skill header now reaches tenant scope. No model calls/live scans performed by these tests.

Activation status remains manual and pending founder acceptance/provisioning. Static inventory is not full runtime route coverage. Branch only; no PR opened or merge/main push.
