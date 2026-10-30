# Base: public reference file and fewest-first state campaigns

Implementation and local verification are complete. **Live acceptance is not complete.** The founder has not yet set the file URL and supplied browser proof. Claude opens the PR; this thread did not use the GitHub API, open a PR, merge or deploy.

Brief: `docs/build/TONIGHT-2026-10-27.md`, section 3, plus the founder's latest push/proof instructions.
Fresh base: `713dd46` from `origin/main`. Branch: `codex/base-reference-file`.

## What changed (file and line)

| File / line | Change |
| --- | --- |
| `agents/base/engines/ffl/reference.py:112` | Preserve the existing bounded reader and ATF stop; configured files use a validated, pinned public destination on each redirect and an independent source stop. |
| `agents/base/engines/ffl/reference.py:162` | `refresh` uses `BASE_REFERENCE_FILE_URL` when set. The dated filename supplies the publication month (`0926-ffl-list.csv` → 2026-09-01). Same parser, size/identity/challenge checks and snapshot format. Missing/invalid/future dates fail; current/older files are not downloaded again. URL queries are not saved as provenance. |
| `agents/base/engines/ffl/reference_source.py:6` | Reuse the existing `agents/_brain/security.py` public URL/DNS validator. Pin the checked public address, retain TLS hostname/Host, disable environment proxies. No private-address override in production. |
| `agents/base/Dockerfile:25` | Package that existing validator in Base's image. No new package dependency. |
| `tank/base_repository.py:34` | Identify sources without storing configured links in check metadata. Existing untagged check rows mean ATF. |
| `tank/base_repository.py:124` | First download checks the current source, records a configured-source attempt before I/O, then uses the existing `engine` and `install(initial=True)`. Failed/interrupted first downloads use the existing daily check interval; blocked sources remain stopped. |
| `tank/base_repository.py:193` | Persist independent source checks while preserving legacy ATF blocks. Changing the source allows a first attempt; changing it back does not erase its old block. The top-level status/message remain compatible with the existing page. |
| `tank/schema.sql:1785` | One additive, idempotent JSONB metadata column. No data-reset migration and no production SQL executed. |
| `tank/base_repository.py:307` | Persist campaign ordinals by `(len(groups[state]), state)`: fewest selected reference licences first, then the stored state name. Existing campaigns are unchanged. |
| `.env.example:3`, `docker-compose.yml:236`, `agents/base/docker-compose.yml:33` | One optional setting name, `BASE_REFERENCE_FILE_URL`, with an empty default. Set the same value on Tank and Base in Coolify. |
| `tests/test_base_reference_file.py:94` | Local-server/database proof of a file replacing a blocked initial ATF read, restart durability, parser failures, no ATF fallback, dates and public-address enforcement. |
| `tests/test_base_reference_file.py:244` | Three different state counts, equal-count name tie and repeated-confirmation/idempotency proof. |

No UI files, page text, authentication, pricing, model routes, provider settings or live data changed. No model calls were made to implement or check this work. All test records are offline fixtures; none were placed on a live screen.

## Exact commands and results

Commands ran in `/workspace/tervory-tank` in the managed cloud unless stated otherwise. The Python environment and PostgreSQL binaries already existed from the preceding task. PostgreSQL here is a disposable local test database, not production.

```sh
git fetch origin main
git switch -c codex/base-reference-file origin/main
/workspace/worker-venv/lib/python3.12/site-packages/pgserver/pginstall/bin/pg_ctl -D /workspace/worker-test-postgres -l /workspace/base-reference-postgres.log -o '-h 127.0.0.1 -p 55432' start
```

Result: fresh branch created; local PostgreSQL started. Read `AGENTS.md`, `docs/cursor/CONTEXT.md`, `docs/cursor/ROOMS.md` and the section 3 brief.

```sh
BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres /workspace/worker-venv/bin/python -m pytest -q tests/test_base_reference_file.py tests/test_base_atf_download.py tests/test_base_reference_adopt.py tests/test_base_product.py > tests/base_reference_file/source-tests.txt 2>&1
```

Result: **81 passed in 16.86s** at the Job A checkpoint. [Output](source-tests.txt).

```sh
BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres /workspace/worker-venv/bin/python -m pytest -q tests/test_base_reference_file.py tests/test_base_database.py > tests/base_reference_file/state-tests.txt 2>&1
```

Result: **29 passed in 2.53s** at the Job B checkpoint. [Output](state-tests.txt).

```sh
BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres /workspace/worker-venv/bin/python -m pytest -q tests/test_base*.py tests/test_b3*.py tests/test_bf2_tank_guards.py tests/test_c13_base_code.py tests/test_room_seal.py > tests/base_reference_file/base-tests.txt 2>&1
```

Result: **322 passed, 2 failed in 160.40s**. Both failures were missing `typescript` before the existing Workspace dependencies were installed. No application code was changed for those failures. [Original output retained](base-tests.txt).

From `/workspace/tervory-tank/workspace`:

```sh
npm install --no-package-lock --no-audit --no-fund
npm install --cache /workspace/scratch/npm-cache --no-package-lock --no-audit --no-fund > ../tests/base_reference_file/npm-install.txt 2>&1
```

The first command failed because `/home/agent/.npm/_cacache` was unavailable. The second used a writable cloud cache and succeeded: **42 packages installed**, without a package/lockfile change. [Output](npm-install.txt).

```sh
BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres /workspace/worker-venv/bin/python -m pytest -q tests/test_base_page.py::test_founder_trial_action tests/test_base_workflow.py::test_base_upload_status_download_and_two_tenants > tests/base_reference_file/base-rerun.txt 2>&1
```

Result: **2 passed in 1.13s**. All **324 distinct checks** in the Base/guard/seal selection passed across the original run and targeted rerun. [Rerun output](base-rerun.txt).

### Local equivalents of the configured CI checks

```sh
/workspace/worker-venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401' > tests/base_reference_file/lint.txt 2>&1
/workspace/worker-venv/bin/ruff check agents/base/engines/ffl/reference.py agents/base/engines/ffl/reference_source.py --select E9,F >> tests/base_reference_file/lint.txt 2>&1
git diff --check >> tests/base_reference_file/lint.txt 2>&1
PYTHONPATH=tank POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres /workspace/worker-venv/bin/python -m pytest -q tests/test_secrets.py tests/test_tank_boots.py > tests/base_reference_file/ci-tests.txt 2>&1
```

Results: **lint and whitespace checks passed; 3 CI tests passed in 11.05s**. Tank starts against an empty database and starts a second time, covering additive schema reapplication. [Lint](lint.txt), [CI tests](ci-tests.txt).

From `/workspace/tervory-tank/workspace`, using the existing workflow's non-secret test placeholders:

```sh
NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA== CLERK_SECRET_KEY=sk_test_dummy npm run build > ../tests/base_reference_file/workspace-build.txt 2>&1
```

Result: **exit 0**, compiled successfully, **38/38 static pages generated**. [Full build output](workspace-build.txt). No real credential was used. Hosted CI has not been claimed: Claude will open the PR, and this thread did not call `api.github.com`.

## Pushed checkpoints

Each checkpoint used `git push -u origin codex/base-reference-file` after committing:

- `5f78550` — scope and evidence plan, pushed early.
- `17146c7` — Job A and its tests.
- `837571d` — Job B and its tests.
- Final evidence commit — the commit containing this completed report and the saved check outputs.

## Founder test and remaining acceptance evidence

**Pending, not done.** No founder screenshot is available. No screenshot was fabricated or substituted with an offline fixture.

After Claude's review and the founder's merge, the founder supplies `BASE_REFERENCE_FILE_URL` in Coolify on both Tank and Base, pointing to his own dated ATF CSV in R2. Its basename must retain the date (for example the supplied `0926-ffl-list.csv`). The configured link and its value were neither requested nor accessed by this thread.

Required browser proof still missing:

1. `base.tervory.com` showing the reference licence count loaded and the September 2026 file date.
2. A newly created campaign showing the smallest selected state first.
3. Screenshots of those two founder-browser results.

No production SQL, file upload, live reference import, campaign creation, merge or deployment was performed here.
