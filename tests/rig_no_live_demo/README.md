# Job 5 — local proof

These screenshots are **local, offline fixture harness** evidence. They are not screenshots from the founder's browser or either deployed site. Founder verification under rule 11 remains pending deployment: open `rig.tervory.com` and `app.tervory.com/rig` with no published catalogue and confirm no catalogue results, sample/demo text, invented counts or chips. Existing labels and placeholders remain.

## What changed

- `agents/rig/app.py:368`: startup no longer imports bundled catalogues automatically, including the container's `/app/catalogues` default. An explicitly configured external catalogue directory remains supported.
- `agents/rig/rigbox/page_route.py:28`: pages use the existing `RIG_WIDGET_PUBLISHABLE_KEY` setting only when its tenant has stored products. No built-in Archon or Custom Nation key, no fallback to another tenant. The JSON fixture asset is no longer served (`:95`). No new setting or credential is introduced.
- `agents/rig/rigbox/page/v5/index.html:79` and `rig.js:131,257`: remove fixture chips, supplier loading, startup catalogue lookup and invented supplier/product/fit counts; absent catalogue or no results leaves results empty. Remove catalogue-specific demo image selection and sample wording. Existing search labels/placeholders remain.
- `workspace/app/rig/search-view.tsx:38`: empty initial results, parts, selected items, result line and conversation; no startup search or seeded C2 shortcut. Explicit searches and selected products use the existing search/graph routes. Remove the hard-coded no-match examples. Hide results and counts when no published products exist.
- `workspace/app/rig/lab.tsx:50,84,187,244,359` and `copy.ts:47`: remove demo review decisions, claimed saved date, demo prices, made-up progress entries and fixed skin counts. Empty catalogues render no numeric counts. No new visible text.

The widget, pricing/fitment implementation, catalogue fixtures and supplier JSON are unchanged. No production database changes or fixture-row deletion were performed. Existing published data is not migrated by this change.

## Test changes

- `tests/test_rig_no_live_demo.py:33,43,51,80`: live page defaults and asset restrictions; offline files preserved; two-tenant selection and empty-store isolation; actual startup lifespan with infrastructure mocked, proving bundled imports never run.
- `tests/test_rig_v5_page.py:66,102` and `tests/test_rig_page.py:117,140`: remove expectations that live pages embed fixture keys; retain explicit offline catalogue/search/fitment/quote tests.
- `tests/test_rig_agent_page.py:73`: reject the invented saved date.
- `tests/test_rig_pr90_independent.py:888,969`: reject default fixture keys; the offline classic browser journey explicitly configures its saved catalogue.
- `tests/test_rig_postgres.py:101` and `tests/test_rig_box_containers.py:21,92`: copy fixtures into an explicit disposable offline catalogue directory; tests no longer depend on the production bundled import. These opt-in integrations were skipped locally.
- `tests/test_rig_quotes_browser.py:77,85`: expect zero `SAMPLE DATA` labels, matching the already-merged widget change in #353. Both viewport tests failed on unchanged main with the stale expectation; they now pass. No widget source/bundle changes.
- `tests/rig_no_live_demo/browser.py:31` and `bundle.cjs:1`: local Chromium proof using actual v5 routes and actual Workspace Lab/SearchView components. The Workspace host/navigation and unopened Plugins boundary are stubbed; its API adapter calls the real Rig Service against explicitly loaded offline data. This does **not** test Clerk, Tank routing, deployment or the founder's session. No model calls.

## Commands and results

Repository: `/workspace/tervory-tank`; base: `62db0f8a245d5680726d280b3a1a1acd358d580f`.

Full Rig suite:

```sh
PATH=/workspace/.tervory-cloud/venv/bin:/workspace/.tervory-cloud/node-v22.23.4-linux-x64/bin:$PATH PYTHONPATH=tank READ1_CHROMIUM_EXECUTABLE=/usr/bin/chromium python -m pytest -q tests/test_rig*.py
```

**515 passed, 47 skipped, 2 failed**, 34.10s. [Full output](evidence/rig-tests.txt). The failures are `tests/test_rig_forge_pipeline.py::test_neutral_samples_pass_all_real_tools[ai-sample.glb]` and `[scan.obj]`, both stopping at `dedup`: this environment has Blender but no `gltf-transform` executable. `gltf-transform --version` exits 127 ([output](evidence/forge-tool.txt)). No Forge code changed. Skips include opt-in Docker/Postgres/tool integrations; these are not claimed as passed.

Baseline, run in a detached worktree at the exact base commit (`/workspace/rig-no-live-demo/main-baseline`):

```sh
PATH=/workspace/.tervory-cloud/venv/bin:/workspace/.tervory-cloud/node-v22.23.4-linux-x64/bin:$PATH PYTHONPATH=tank READ1_CHROMIUM_EXECUTABLE=/usr/bin/chromium python -m pytest -q tests/test_rig_forge_pipeline.py::test_neutral_samples_pass_all_real_tools tests/test_rig_quotes_browser.py
```

**4 failed, 1 passed**. The same two Forge `dedup` failures plus the two stale widget `SAMPLE DATA` assertions described above. [Baseline output](evidence/main-baseline-tests.txt).

Browser proof (esbuild 0.28.2 installed only in a scratch directory; no repository dependency change):

```sh
PATH=/workspace/.tervory-cloud/venv/bin:/workspace/.tervory-cloud/node-v22.23.4-linux-x64/bin:$PATH PYTHONPATH=tank RIG_ESBUILD_PATH=/workspace/rig-no-live-demo/npm/node_modules/esbuild READ1_CHROMIUM_EXECUTABLE=/usr/bin/chromium python tests/rig_no_live_demo/browser.py
```

[Output](evidence/browser.txt):

```text
PASS v5 root and both skins: no fixture requests, no demo text, no results, counts or chips without a published store
PASS Workspace starts empty: no startup search, products, parts, added items, opening conversation, demo decisions or invented counts on any tab
PASS submitted Workspace search uses the stored catalogue and graph; nothing is pre-added; a no-result search stays empty
```

Production build: in a temporary copy of `workspace/`, excluding existing `node_modules`, `.next`, `.env*` and TypeScript build artifacts, install the declared dependencies and run the same dummy Clerk build settings as CI:

```sh
npm install --no-audit --no-fund --no-package-lock
NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA== CLERK_SECRET_KEY=sk_test_dummy npm run build
```

**Passed**, including TypeScript validation and all routes. [Build output](evidence/workspace-build.txt). The temporary copy was removed; no lockfile/dependency/authentication changes in the repository.

Additional checks:

```sh
PATH=/workspace/.tervory-cloud/venv/bin:$PATH ruff check agents/rig/app.py agents/rig/rigbox/page_route.py tests/test_rig_no_live_demo.py tests/test_rig_agent_page.py tests/test_rig_page.py tests/test_rig_postgres.py tests/test_rig_pr90_independent.py tests/test_rig_quotes_browser.py tests/test_rig_v5_page.py tests/test_rig_box_containers.py tests/rig_no_live_demo/browser.py
node --check agents/rig/rigbox/page/v5/rig.js
PATH=/workspace/.tervory-cloud/venv/bin:$PATH PYTHONPATH=tank python -m pytest -q tests/test_secrets.py
git diff --cached --check
```

Ruff and JavaScript syntax checks passed; secret checks: **2 passed**; whitespace check passed. Saved terminal output has trailing whitespace removed only.

## Screenshots — local, offline fixture harness

No catalogue is selected in the v5 screenshots even though an offline tenant exists in the test service. The Workspace screenshots receive zero published products. The saved catalogue is used only in the explicit-search portion of the test.

| Page | Desktop (1440) | Mobile (390) |
| --- | --- | --- |
| Rig v5 | [Screenshot](evidence/local-rig-empty-1440.png) | [Screenshot](evidence/local-rig-empty-390.png) |
| Workspace Rig components | [Screenshot](evidence/local-workspace-empty-1440.png) | [Screenshot](evidence/local-workspace-empty-390.png) |

The founder's browser screenshots required for final acceptance are not available in this cloud workspace. No deployment or live acceptance is claimed.
