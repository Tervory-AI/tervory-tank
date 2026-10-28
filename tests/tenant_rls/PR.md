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
