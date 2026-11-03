# Tisan J5 — gate 3: offline k6 smoke

Every successful baseline Tisan build now runs k6 after Q1's accessibility, mobile Lighthouse, links/assets and secret checks. Three virtual users run for three seconds against every route returned by Q1's manifest reader, on Q1's existing production Next server. Every request must return 200. Per-page request counts, failures and p95 milliseconds are saved in the existing checks list. A failed or unavailable smoke fails the build and prevents its archive. Existing build memory stores the complete check automatically; no new memory schema, UI, model call, email or page was introduced.

The one authorized `git fetch origin && git merge origin/main` completed as `3aadec73` and was pushed before implementation. Both sides were retained. `run_checks` contains all four Q1 quality gates; no second main merge was performed. This extends the existing room image; deploy-on-merge continues to redeploy the Tisan room through its existing Compose file. Radix's Dockerfile, proxy implementation and the room's restored Compose settings are unchanged in this gate.

## Changes by file and line

- `agents/tisan/Dockerfile:19`: pin k6 **1.8.2** (AGPL-3.0) for amd64 and arm64. `:37` verifies the release archive's hardcoded SHA-256 before installing only the executable, then removes the download. Upstream checksum source: [k6 1.8.2 checksums](https://github.com/grafana/k6/releases/download/v1.8.2/k6-v1.8.2-checksums.txt). No runtime download is used.
- `agents/tisan/templates/next-site/scripts/smoke.k6.js:1`: builtin k6 modules only; fixed numeric loopback origin; reject off-origin/ambiguous manifest paths before requests; disable redirects; require every page at 200, with nonzero requests and a p95 timing. No external URLs are followed or fetched.
- `agents/tisan/templates/next-site/scripts/quality-check.cjs:276`: run the smoke with an explicit empty config and a minimal environment; disable usage reporting and dashboard, bind the k6 API to ephemeral loopback, enforce a deadline and validate the complete report. `:377` runs it before Q1 closes its existing local Next server. Missing binary/report, incomplete pages and nonzero exit fail closed.
- `agents/tisan/scaffold.py:36` and `:298`: exclude transient smoke reports from project files/archives. `:456` includes k6 in the existing card result rows. `:511` completes the tenant-scoped secret scan before the browser runner's final k6 stage, then returns Q1 rows followed by k6. Existing build failure and memory paths remain unchanged.
- `tests/test_tisan_k6.py:85`: real k6 against isolated loopback fixtures: multiple pages, 200, 500, redirected response, nonlocal origins/paths, poisoned inherited proxy/output settings and per-page timings. `:109` feeds the actual failed smoke through `run_checks` and `builder.execute`, verifies the failed sidecar and no archive. `:140` verifies successful and failing memory claims retain the full check. `:156` verifies all Q1 checks precede the smoke.
- `tests/test_tisan_quality.py:143`: the opt-in real clean-template build now requires all nine checks, both manifest pages at 200 with p95 values, and five existing presenter result rows.
- `.github/workflows/ci.yml:192`: install the same Dockerfile-pinned, checksum-verified binary during CI setup, so all real k6 tests run in the offline Tank suite rather than skipping for a missing executable. No duplicate version/checksum constants.
- `.gitleaksignore:58`: eight exact historical fingerprints for the copied 1.1.0 Figma eval identifiers. The current first six cases remain byte-identical to 1.0.1 as required by the review. These are the same already-reviewed file identifiers (which grant no access), not credentials. No rule, prefix or path-wide exception was added. The full branch scan is clean.
- `tests/tisan_j5/results.json:1`: actual clean-template checks and existing presenter result rows.
- `tests/tisan_j5/image.json:1`: measured image delta and a runtime smoke with Docker networking disabled; source hashes match the current files.
- `tests/tisan_j5/PR.md:1`: gate evidence and founder acceptance boundary.

## Local validation

All commands below ran in `/workspace/codex-tisan-w3`. Test binaries, npm cache and Chromium live in this branch's ignored `.venv` directory; Postgres is a separately named disposable container with tmpfs storage and a loopback-only published port. No production data was changed. The scanner engine is real in the clean-template test; Tank transport and approval are isolated test doubles as in Q1.

```sh
PATH="$PWD/.venv/k6-v1.8.2-linux-amd64:$PATH" .venv/bin/python -m pytest tests/test_tisan_k6.py -q --disable-socket --allow-hosts=127.0.0.1,localhost
# 11 passed in 17.25s; actual pinned k6, not a fake executable.

PATH="$PWD/.venv/k6-v1.8.2-linux-amd64:$PATH" TMPDIR="$PWD/.venv/j5-tmp" J4_TEST_POSTGRES_PORT=32877 POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32877/postgres TISAN_TEST_PLAYWRIGHT="$PWD/.venv/tisan-browser/node_modules/playwright" PLAYWRIGHT_BROWSERS_PATH="$PWD/.venv/j5-browser" .venv/bin/python -m pytest tests/test_tisan_*.py tests/tisan_promotion/ tests/test_c10_rooms.py tests/test_secrets.py -q -rs --disable-socket --allow-hosts=127.0.0.1,localhost --maxfail=3
# 496 passed, 3 skipped, 15 existing warnings in 208.76s.
# Skips: the two existing opt-in build tests and Q1's opt-in clean build,
# which is run separately below.

PATH="$PWD/.venv/k6-v1.8.2-linux-amd64:$PATH" TMPDIR="$PWD/.venv/j5-tmp" TISAN_RUN_QUALITY_BUILD=1 TISAN_NPM_OFFLINE=1 TISAN_NPM_CACHE="$PWD/.venv/j5-npm-cache" TISAN_QUALITY_PROOF="$PWD/.venv/j5-quality-proof.json" PLAYWRIGHT_BROWSERS_PATH="$PWD/.venv/j5-browser" .venv/bin/python -m pytest tests/test_tisan_quality.py::test_real_clean_template_passes_all_four_quality_gates -q --disable-socket --allow-hosts=127.0.0.1,localhost
# 1 passed in 241.97s; all nine checks passed.

# From agents/tisan/templates/next-site, using the pinned cached dependencies:
npm run lint
# ESLint and Prettier passed; the initially reported anonymous-default warning
# was removed by naming the k6 entrypoint.
npm test
# 56 passed across 7 files.
npx tsc --noEmit
# Exit 0.

.venv/bin/ruff check tests/test_tisan_k6.py agents/tisan/scaffold.py --select E9,F
# All checks passed.
PATH="$PWD/.venv/j5-tools:$PATH" python3 -m unittest discover -s tests/ci_security -p test_security.py -q
# 41 passed.
.venv/j5-tools/gitleaks git . --no-banner --redact=100 --config .gitleaks.toml --gitleaks-ignore-path .gitleaksignore --ignore-gitleaks-allow --log-opts origin/main..HEAD --report-format json --report-path .venv/j5-gitleaks-final.json
# Exit 0; no findings. Scanner diagnostics were redirected to an ignored local log.
git diff --check
# Exit 0.
```

Initial attempts with the former shared Chromium cache failed because that cache was absent after host cleanup. The successful regression run uses Chromium copied from the existing Q1 image into this task's own directory. The initial security-policy run also required adding the local pinned gitleaks directory to PATH; the corrected run passes all 41 cases. Neither issue required weakening a check.

The clean template returned 200 on all **84** k6 requests: `/contact` 42 requests, p95 **77.70 ms**; `/privacy` 42 requests, p95 **46.48 ms**. Both pages passed all existing Q1 budgets; secrets scanned 60 generated text files without findings. [results.json](results.json) records the complete checks and existing card result rows.

The CI setup step was also executed directly from the parsed workflow. It downloaded the release archive, verified the Dockerfile's SHA-256, extracted only the named executable and returned `k6 v1.8.2`. CI setup may install dependencies; the smoke itself uses only loopback and disables usage reporting.

## Image measurement and CI

The baseline is the merged pre-J5 context (`3aadec73`). Docker's uncompressed image size is **3,711,284,276 bytes**. The final image is **3,815,972,011 bytes**, a change of **+104,687,735 bytes** (about 99.84 MiB). The final image runtime context is `78d3a084`; later commits only change tests, CI and evidence, and all Docker COPY inputs are unchanged. [image.json](image.json) records image IDs, exact sizes, source hashes and the actual network-disabled smoke. Final-head CI results are recorded in the gate handoff comment on PR #627. CI's `tank (1)`, `tank (2)`, `tank (3)` and `workspace` jobs are the full-suite test of record; local focused checks do not substitute for those results.

```sh
mkdir -p .venv/j5
# Baseline context exported before J5 changes:
git archive 3aadec73 | tar -xf - -C .venv/j5
docker build -f agents/tisan/Dockerfile -t codex-tisan-w3-j5:before .venv/j5
# Exit 0.
git archive 78d3a084 | tar -xf - -C .venv/j5-final
docker build -f agents/tisan/Dockerfile -t codex-tisan-w3-j5:final .venv/j5-final
# Exit 0.
docker image inspect codex-tisan-w3-j5:before codex-tisan-w3-j5:final --format '{{.RepoTags}} {{.Size}}'
# before: 3711284276; final: 3815972011.
docker run --rm --network none --memory 512m --cpus 0.5 --entrypoint python -i codex-tisan-w3-j5:final - < .venv/j5-image-proof.py
# Exit 0. The stdlib loopback fixture returned 200 on all 45 clean requests;
# all 45 requests to the isolated 500 fixture failed the check as required.
# Actual installed k6 1.8.2; no Docker network; current source hashes verified.
```

The final image was rebuilt after formatting/name-only script changes so its source hashes match the current branch exactly. An earlier completed intermediate image was not used for the final measurement. The disposable Postgres container was stopped and automatically removed after the regression run.

## Founder acceptance after merge/deploy

The founder still needs to run `tisan.build` on his own test site in `/chats`, confirm the existing card lists k6 with every page at 200, and confirm that run's build memory contains the k6 check. This gate does not claim that live acceptance or deployment has happened. Q1's existing scanner approval requirement still applies. The founder merges; no PR merge, production SQL, paid service or model call was performed here.
