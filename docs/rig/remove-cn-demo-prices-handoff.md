Rig currently ships offline catalogues and reads store behaviour from their publish files. This change removes that runtime dependency: each store's existing uploaded catalogue stays in its database, and shop behaviour comes only from `agent_rig.retailers.shop`. The founder-approved Archon settings carry-over preserves today's behaviour without adding admin controls or copy.

This branch is `rig/remove-cn-demo-prices`. Claude opens the PR; the founder reviews and merges. No deploy or production SQL was run from this job. The only approved future data change is the conditional carry-over below when the existing schema application runs after deployment.

## Changes and evidence locations

| File and line | Change |
| --- | --- |
| `agents/rig/schema.sql:169` | Add `shop jsonb NOT NULL DEFAULT '{}'`; carry over the exact old Archon object only where `slug='archon' AND shop='{}'`. Nonempty settings are preserved. |
| `agents/rig/rigbox/service.py:1004` | `_shop` reads only the retailer record. The disk loader, publish lookup, legacy catalogue importer and publish application move out of runtime. |
| `agents/rig/rigbox/store.py:395` and `:987` | Preserve the in-memory store's shop object across unrelated setting saves; select/decode the database column. No shop-setting write endpoint is introduced. |
| `agents/rig/app.py:154` | Room-key gold reads require an explicit tenant and use the region of this box. Only uploaded active products and approved fits can label candidates. Rows remain tenant-private; the unscoped platform collector gets an empty list rather than promoting store data to public training. |
| `agents/rig/app.py:374` | Remove startup folder loading. Existing database tenants still receive feed-refresh and quote-retry schedules. |
| `agents/rig/gold_sources.py:21` | Build gold candidates from the scoped store; exclude sample/demo flags and non-uploaded products. Approved content changes produce a new deterministic label family. No model calls. |
| `agents/rig/Dockerfile:17`, `agents/rig/docker-compose.yml` | Remove the catalogue COPY and CATALOGUE_DIR default. The Rig Docker build context does not contain `tests/fixtures`. |
| `workspace/app/rig/search-view.tsx:228` and `:356` | Delete only the example clauses: placeholders become `Search a brand, model or part` and `Ask a follow-up`. |
| `agents/rig/rigbox/quotes/widget/manifest.json`, `docs/rig/widget-source.patch` | Rebuild the pinned UMD from upstream `f382f8da90944a3176c1bd43cfc77f14e78c6a0f`, preserving the existing source patch and removing the Staccato example clause and chip. Keep only the manifest-referenced bundle. Rebuild script now reads its patch from docs, outside the image. |
| `tests/fixtures/rig_catalogues/`, `tests/fixtures/rig_feed_formats/` | Offline regression catalogues and feed samples. Branded catalogue folders are Aurora and LumaWorks; Staccato fixture copy becomes the invented LumaWorks brand. Historical Archon product/SKU labels remain only as offline regression inputs for the deliberately unchanged search rules. Example/second are already invented fixture stores. |
| `tests/fixtures/rig_three_d/`, `tests/fixtures/rig_quote_sample.py`, `tests/fixtures/rig_forge_models/`, `tests/fixtures/rig_sample_suppliers.json` | Move sample 3D apps, seeding, StubForge, models, quote server and unused supplier prices outside runtime. Test imports and explicit isolated seeding replace runtime startup seeding. No fixture is copied into an image. |
| `tests/test_rig_runtime_catalogues.py:19` | On throwaway Postgres, start with the old retailers table, apply the schema twice, verify each slug, then preserve an existing nonempty Archon setting on reapply. |
| `tests/test_rig_runtime_catalogues.py:61` | Guard every runtime file against catalogue CSVs, publish.json, Staccato and literal rk_pub_ test keys; assert the old loader/importer methods are absent. |
| `tests/test_rig_gold.py:71` | Real Postgres tenant isolation and approved/uploaded-only gold; API authentication and empty unscoped reads. |

## Exact approved carry-over

| Existing slug | Key | Value |
| --- | --- | --- |
| `archon` | `search` | `true` |
| `archon` | `mail_reservations` | `true` |
| `archon` | `centre_sku` | `"ARCHON-TYPE-B"` |
| `archon` | `not_stocked` | `[{"name":"Glock","also":["glok","glock"]},{"name":"Sig","also":["sig","sigsauer"]},{"name":"CZ","also":["cz"]}]` |
| `customnation` | none | `{}`; no settings carried |
| `example` | none | `{}`; no settings carried |
| `second` | none | `{}`; no settings carried |

No product prices or catalogue rows are migrated or deleted from live data by this PR. Applying the migration twice does not change the carried object; an existing nonempty object is never overwritten.

## Figma item deferred by founder decision

Founder-only Rig admin editing of `search`, `mail_reservations`, `centre_sku`, and `not_stocked` needs an approved frame and exact wording. This PR adds no admin controls, new UI words, new empty states or new error text on a page.

## Deliberately unchanged Archon search behaviour

`agents/rig/rigbox/cn.py` retains its hard-coded `archon` token handling at lines 513, 516, 543, 546, 1441, 2123, 2125 and 2129. This includes variant context, make recognition/fuzzy matching, filler removal and implicit context. The founder decides their future disposition. The only change to cn.py is removal of a stale demo-catalogue sentence in its module docstring.

## Exact verification commands and results

All database commands used a new local container with no production mounts or credentials:

```bash
docker run --detach --name rig-demo-removal-pg --publish 127.0.0.1::5432 --env POSTGRES_HOST_AUTH_METHOD=trust postgres:16
docker port rig-demo-removal-pg 5432
```

Result: PostgreSQL 16 listening only on `127.0.0.1:32781`; tests create/drop their own uniquely named databases. No production connection.

The initial runtime lacked several dependencies. Reused the existing complete `venv-ci` and existing read-only Workspace node_modules rather than installing replacements:

```bash
ln -s /home/ammosync/.codex/tervory-acceptance-20261101/workspace/node_modules workspace/node_modules
```

The link is local and excluded from Git. It is not part of this branch or an image.

Final full suite command:

```bash
TMPDIR=/workspace/rig-remove-cn-demo-prices/.rig-validation RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32781/postgres POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32781/postgres READ1_CHROMIUM_EXECUTABLE=/opt/google/chrome/chrome PLAYWRIGHT_BROWSERS_PATH=/home/ammosync/.cache/ms-playwright /home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python -m pytest tests/test_rig*.py tests/rig_tiger_prices tests/custom_nation_rig -q --tb=short --continue-on-collection-errors --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
```

Result: **722 passed, 11 skipped, 14 warnings in 162.94 seconds**, exit 0. Raw full-suite output is committed in `docs/rig/remove-cn-demo-prices-validation.txt`.

The skipped checks require explicitly enabled Docker/Hermes images, absent Forge executables, or the uncommitted private Custom Nation cost export; no real Hermes or other model call was enabled. Browser/API tests used isolated test fixtures only. External sockets and nonlocal DNS were blocked by the existing test harness.

Focused migration, gold, startup, UI regression and label-family command:

```bash
TMPDIR=/workspace/rig-remove-cn-demo-prices/.rig-validation RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32781/postgres POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32781/postgres READ1_CHROMIUM_EXECUTABLE=/opt/google/chrome/chrome /home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python -m pytest tests/test_rig_runtime_catalogues.py tests/test_rig_gold.py tests/test_rig_postgres.py tests/test_rig_no_live_demo.py tests/test_rig_v5_page.py tests/test_labels1_families.py -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
```

Result: **40 passed** (before the final fixture-folder-only rename; the full final suite covers the renamed paths).

```bash
/home/ammosync/trigger-crm-venv312/bin/ruff check agents/rig tests/rig_fixture_loader.py tests/test_rig_gold.py tests/test_rig_runtime_catalogues.py --select E9,F
git diff --check origin/main
```

Result: lint passed and no whitespace errors.

Widget rebuild and source replay:

```bash
git clone --quiet --local /home/ammosync/.codex/rig-inspection-20261101 .rig-validation/widget-source
git -C .rig-validation/widget-source apply --unidiff-zero ../../agents/rig/rigbox/quotes/widget-source.patch
# Source patch was then extended with the two deletions and moved to docs/rig/widget-source.patch.
cd .rig-validation/widget-source
npm ci --no-audit --no-fund
npm run build
npx vitest run
node scripts/package-widget.mjs ../../agents/rig/rigbox/quotes/widget
cd ../..
git clone --quiet --local .rig-validation/widget-source .rig-validation/widget-replay
git -C .rig-validation/widget-replay apply --check --unidiff-zero ../../docs/rig/widget-source.patch
git -C .rig-validation/widget-replay apply --unidiff-zero ../../docs/rig/widget-source.patch
```

Results: build and bundle guard passed, **25 widget tests passed**, patch replay passed and all 12 replayed changed source files match the build inputs byte for byte. The committed bundle is `tervory-rig.a9325028a2360f3016f334cc692d943ecbcb39ca6c90792def64531754307c7a.umd.js` (**17,718 bytes gzip**); the old bundle is removed.

```bash
docker build --file agents/rig/Dockerfile --tag rig-remove-cn-demo-prices:validation agents
docker run --rm --network none --entrypoint python rig-remove-cn-demo-prices:validation -c 'from pathlib import Path; import re; root=Path("/app"); bad=[]; forbidden={"sample.py","demo.py","publish.json"}; paths=[p for p in (root/"rigbox").rglob("*") if p.is_file() and "__pycache__" not in p.parts]; paths += [root/"app.py",root/"gold_sources.py"]; bad=[str(p) for p in paths if p.name in forbidden or p.suffix==".csv" or b"Staccato" in p.read_bytes() or re.search(rb"rk_pub_[A-Za-z0-9][A-Za-z0-9_-]*",p.read_bytes())]; assert not bad,bad; assert not (root/"catalogues").exists(); assert not (root/"tests").exists(); from rigbox.service import Service; assert not hasattr(Service,"load_folder"); assert not hasattr(Service,"_apply_publish"); print("PASS: image contains no catalogue CSV, publish file, demo server, branded example, test key, fixture tree or legacy importer")'
git grep -n -i -E 'demo catalogue|demo price|Staccato|publish\.json|rk_pub_[A-Za-z0-9][A-Za-z0-9_-]*' -- agents/rig
```

Results: image built; filesystem/import guard printed PASS. Git grep has **no matches** (exit 1, the expected result).

The standalone offline browser harness import was also checked without running its browser main:

```bash
/home/ammosync/.codex/tervory-integration-closure-evidence-20261101/venv-ci/bin/python -c 'import runpy; runpy.run_path("tests/rig_no_live_demo/browser.py", run_name="rig_browser_import_check"); print("PASS: standalone offline browser harness imports")'
```

Result: PASS.

## Deployment and founder proof still pending

This is runtime work, not a CI-only PR. Under the existing deploy-on-main workflow, the `workspace/` edit selects the main and ZA stacks, and `agents/rig/` selects Rig and regional copies (subject to the existing ZA_OFFLINE setting). The founder alone merges; this thread did not trigger deployment or change Coolify settings.

After deployment, the founder runs the **same ten searches on the same live store and uploaded price lists** used before this change. Record the ten inputs, expected/actual results and screenshots of that actual browser test here. Those screenshots and the live comparison are **pending**, not supplied by synthetic browser tests. The task is not claimed done until the founder sees those results and the no-demo runtime grep remains empty.
