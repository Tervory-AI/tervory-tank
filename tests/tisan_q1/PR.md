# Tisan Q1 quality checks

Builds now run accessibility, mobile Lighthouse, local links/assets and Radix secret checks after the existing four checks. A failure remains `ok: false`, persists its manifest, and supplies rows to the existing `/chats` card presenter. No page design or presenter layout changed. No new npm packages or model calls were added.

## Changes for review

- `agents/tisan/templates/next-site/scripts/quality-check.cjs:35`: enumerate content/static and built routes; serve production Next locally; run axe at 390/1440; check internal links/assets, including CSS references; list external URLs without fetching them. The browser proxy refuses all origins except that local server.
- `agents/tisan/templates/next-site/scripts/quality-check.cjs:228`: invoke `npm run lhci`, retain every run's scores, compare medians and report missing pages as failures.
- `agents/tisan/templates/next-site/lighthouserc.cjs:6`: founder-editable budgets 0.90/0.95/0.90/0.90; mobile preset; Playwright's pinned Chromium; local filesystem reports.
- `agents/tisan/scaffold.py:455`: manifest/card rows and four quality results. `:461` submits `{files: [{path, text}]}` through the existing Tank client and `/v1/skala/scan.secrets/run`, with no version pin. Findings expose file, line and rule only. Missing approval, incomplete reports and unavailable scans fail closed. Inputs beyond the scanner's line coverage also fail closed. The canonical fake-key fixture is excluded from generated sites.
- `agents/tisan/builder.py:253`: tenant-scoped checks, failed manifests and existing card results. Promotion's existing refusal of non-ok builds is preserved.
- `agents/tisan/Dockerfile:59`: expose the existing image-installed browser cache to runtime. Installation already uses the template's pinned Playwright dependency; both axe and Lighthouse use it.
- `tank/skills/scan.secrets/1.1.0/skill.yaml:4`: share the Radix skill with Tisan. Engine and runner are byte-identical to 1.0.1; previous versions are untouched. Includes changelog and six passing evals.
- `tests/test_tisan_quality.py:47`: actual scanner engine behind a mocked Tank approval transport, clean/fake-key, no-approval, safe-error, manifest/card, browser-cache and coverage tests. `:127` is the separate real template integration.
- `tests/test_tisan_builder.py:186`: a failed quality build saves its failed sidecar, returns its link location and creates no archive.
- `tests/tisan_quality_card.test.cjs:1` and `tests/test_tisan_quality_card.py:6`: exercise the unchanged Workspace presenter for passing results and the named broken link.
- `agents/tisan/templates/next-site/tests/quality-browser.cjs:1`: actual Chromium/axe/Lighthouse negative cases against isolated local HTML fixtures; these are never live routes.

## Validation

Commands below ran from `/workspace/codex-tisan-q1`, except the template commands which ran from `agents/tisan/templates/next-site`. The machine's shared `/tmp` returned quota error 122 during an exploratory rerun; the successful runs used the task's own temporary directory. This was a host limitation, not a template change.

```sh
.git/venv/bin/python -m pytest -q tests/test_tisan_*
# 212 passed, 10 skipped, 14 warnings. Existing opt-in/environment tests remain skipped.

TMPDIR=/workspace/codex-tisan-q1/.git/tmp TISAN_RUN_QUALITY_BUILD=1 TISAN_NPM_OFFLINE=1 TISAN_NPM_CACHE=/home/ammosync/.npm TISAN_QUALITY_PROOF=/workspace/codex-tisan-q1/.git/quality-full-build.json .git/venv/bin/python -m pytest -q -s tests/test_tisan_quality.py::test_real_clean_template_passes_all_four_quality_gates
# 1 passed in 181.27s. All eight checks passed.

TMPDIR=/workspace/codex-tisan-q1/.git/tmp npm test
# 56 passed across 7 files.
npm run lint
# ESLint and Prettier passed.
npx tsc --noEmit
# Exit 0.
TMPDIR=/workspace/codex-tisan-q1/.git/tmp node tests/quality-browser.cjs --lighthouse
# Exit 0; actual missing-alt, broken-link and performance-budget failures asserted.

.git/venv/bin/ruff check agents/tisan/scaffold.py agents/tisan/builder.py tests/test_tisan_quality.py tests/test_tisan_quality_card.py tests/test_tisan_builder.py
# All checks passed.
git diff --check origin/main...HEAD
# Exit 0.
```

The six `scan.secrets/1.1.0/evals/cases.jsonl` cases were also run directly with the unchanged engine; every expected field matched. No secret values were printed:

```sh
.git/venv/bin/python - <<'PY'
import importlib.util,json
from pathlib import Path
root=Path('tank/skills/scan.secrets/1.1.0')
spec=importlib.util.spec_from_file_location('scan_eval',root/'engine.py'); mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
cases=[json.loads(line) for line in (root/'evals/cases.jsonl').read_text().splitlines()]
for case in cases:
    actual=mod.run_skill(case['input'])
    assert all(actual.get(k)==v for k,v in case['expected'].items()),case['name']
print(f'{len(cases)} scan.secrets evals passed; no values printed')
PY
# 6 scan.secrets evals passed; no values printed
```

Machine-readable local results are in [results.json](results.json). Clean template scores (performance/accessibility/best practices/SEO): `/contact` **0.96/1.00/1.00/0.90**, `/privacy` **0.97/1.00/1.00/0.90**. Axe passed both widths. All 16 local links/assets returned 200. The actual scanner engine passed 59 generated text files. Tank's transport/approval in this test is mocked; this is not a live Tank approval claim.

Negative evidence: `image-alt` names `img` on `/missing-alt` at both widths; `/missing-test-link` returns 404 from `/broken`; the slow page's median performance is **0.55**, below 0.90. External URLs were listed and the forbidden external test server received zero requests. The canonical fake-key case fails secrets and returns location fields only.

## Room image

Both images were built on the same host. Baseline: **3,711,090,052 bytes**; final: **3,711,127,878 bytes**; change: **+37,826 bytes** (Docker `.Size`, uncompressed). [image.json](image.json) records the runtime result. The final image context is commit `05733d2b`; later commits only add tests/evidence outside the Docker COPY inputs.

```sh
docker build -f agents/tisan/Dockerfile -t codex-tisan-q1:before .git/q1-before
# Exit 0; original main context.
docker build -f agents/tisan/Dockerfile -t codex-tisan-q1:after .git/q1-final-image
# Exit 0; final completed build and cached confirmation.
docker image inspect codex-tisan-q1:before codex-tisan-q1:after --format '{{.RepoTags}} {{.Size}}'
# [codex-tisan-q1:before] 3711090052
# [codex-tisan-q1:after] 3711127878
docker run --rm --network none --entrypoint node -e NODE_PATH=/opt/tisan-check/node_modules codex-tisan-q1:after -e 'const fs=require("node:fs"); const crypto=require("node:crypto"); const {chromium}=require("@playwright/test"); (async()=>{const p=JSON.parse(fs.readFileSync("/app/templates/next-site/package-lock.json"));const version=require("@playwright/test/package.json").version;if(version!==p.packages["node_modules/@playwright/test"].version)throw Error("version mismatch");const browser=await chromium.launch({args:["--no-sandbox"]});const page=await browser.newPage();await page.setContent("<html lang=en><title>Browser runtime test</title><main>Browser runtime test</main></html>");console.log(JSON.stringify({playwright:version,chromium:browser.version(),executable:chromium.executablePath(),runtimeHash:crypto.createHash("sha256").update(fs.readFileSync("/app/scaffold.py")).digest("hex"),network:"none",launch:"passed"}));await browser.close();})().catch(()=>process.exit(1));'
# Exit 0: Playwright 1.64.1; Chromium 156.0.8078.4;
# /opt/tisan-browser/chromium-1248/chrome-linux64/chrome; launch passed.
```

An obsolete intermediate image build was canceled when the lint-only source cleanup required a final image rebuild. The measured and launched image is the completed final build; its scaffold SHA-256 matches the final source.

## Founder acceptance still outstanding

- The founder approves **`scan.secrets 1.1.0` in `/skala`**. Live approval state has not been queried or changed in this task. A mocked 409 test proves the build refuses an unapproved scan and names `/skala`.
- The current section registry deliberately renders no visuals. A separate local Lighthouse probe of a planned empty home route fails `NO_FCP`; no text/design was fabricated to pass it. The successful clean-template test covers the existing contact/privacy routes. A full site's home page needs its separately approved renderer before that site can pass Lighthouse.
- No founder `/chats` browser test or founder screenshots have been captured. After founder merge/deployment and scanner approval, record the passing four-check card and the failing build card naming the broken internal link. Local tests and presenter tests are evidence, not completion of that acceptance criterion.
- Claude opens the PR from `codex/tisan-q1-quality-checks`; the founder merges. Every push was preceded by fetching and merging `origin/main`. No push to main or production data mutation was performed.
