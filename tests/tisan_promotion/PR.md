# Tisan: promote a tested staging commit through Coolify

Tisan previously stopped at local build checks. This change adds founder-only API
promotion of a registered staging application's exact full Git SHA to its paired
production application. The server runs the existing browser checker and the
Radix gate, rechecks both deployment records, pins production through Coolify's
API and records the result. Explicit rollback restores the recorded previous
commit, including recovery after an acknowledged failed/cancelled deployment.
Queue acknowledgement is pending, not success. Ambiguous requests are never
silently resent.

Branch: `codex/tisan-promotion`, from main
`7a13687de256896c488a0f28e0906fbcbce5b046`. Main was rechecked and remained at that
SHA. All open PRs and Tisan/promotion branch searches were checked first; no exact
implementation existed. No existing branch was reset. Claude opens the PR and
the founder merges. No PR was opened by this builder.

## Changes and first relevant lines

| File/line | Result |
| --- | --- |
| `agents/tisan/promotion.py:45` | Tenant/site bindings and durable SQLite operation journal on the existing data volume; reservations, replay identity and history. |
| `agents/tisan/promotion.py:138` | Strict HTTPS Coolify adapter; full deployed SHA, healthy/pinned application and latest non-preview deployment checks; no proxy inheritance, redirect or raw-error forwarding. |
| `agents/tisan/promotion.py:181` | Staging live check, exact fresh Radix receipt, before/after revision checks, API pin/deploy, previous-commit rollback and terminal-failure recovery. Unknown outcomes stay quarantined. |
| `agents/tisan/promotion_api.py:33` | Reused ops browser runner, stripped child environment, bounded runtime and retained local screenshots. |
| `agents/tisan/promotion_api.py:59` | Founder + room authentication, immutable tenant/site/app registration, promote/rollback/status/history. Calls the agreed regional Radix scans/gate endpoints. |
| `agents/tisan/app.py:34` | Register dynamically loaded modules so pinned Pydantic can resolve route-model annotations. The packaged-image check caught this compatibility defect. |
| `agents/tisan/app.py:146` | Mount promotion routes in the existing room. No startup promotion or scan. |
| `ops/live_check.mjs:12` | Optional single-staging-origin mode; existing production roster and local regression mode retained. Requires a 2xx same-origin root and blocks cross-origin requests and non-GET/HEAD methods. |
| `tank/main.py:3886` | Founder-only fixed promotion corridor, existing room key, bounded body and action allowlist. No router/cache/queue change. |
| `agents/tisan/Dockerfile:1`, `Dockerfile.dockerignore:1`, `docker-compose.yml:11` | Repository-root restricted context, existing Playwright dependency/browser, cached dependency layer and new source copies; setting names only. No runtime Docker socket. |
| `.env.example:439` | Empty `TISAN_COOLIFY_URL` / `TISAN_COOLIFY_TOKEN` names. Founder supplies values. |
| `agents/tisan/PROMOTION.md:1` | Setup, HTTP contracts, ambiguity handling, official API sources and exact founder acceptance. |
| `tests/tisan_promotion/test_promotion.py:1` | Fake Coolify promotion/rollback, stale/failed/malformed gates, concurrency, scoped audit, replay, lost acknowledgement and terminal-failure recovery. |
| `tests/tisan_promotion/test_tisan_promotion_api.py:1` | Room authorization and real Tank proxy function; exact regional Radix requests and missing-gate refusal. |
| `tests/tisan_promotion/test_browser.py:1` | Real Chromium on intercepted synthetic HTTPS responses; no live host. 403/runtime failures fail; screenshots at both widths; POST and foreign-origin requests are blocked. |
| `tests/tisan_promotion/verify_image.py:1` | Compare shipped-source hashes, generate actual room OpenAPI and run tests in the isolated runtime image. |
| `tests/test_tisan_figma.py:374` | Existing COPY assertions updated for the repository build context. |

## Radix dependency and review

Job 8 must be reviewed, merged and deployed first. Its published branch is
`codex/radix-passive-gate`, checkpoint
`369c908e867da194f77ebf77cceed7869699e3ee`. Its owner reported a ref-lock push
failure and stopped; an unpushed local follow-up is not claimed as published.
This branch does not reconcile that branch or bypass the missing gate.

Agreed requests: `POST /v1/radix/passive/scans`, then `/gate`, with
`{tenant_id,target,artifact:"commit:<40hex>"}`, Tisan room authentication and exact
tenant/squad/region headers. Gate response is top-level
`{allowed,scan_id,tenant_id,target,artifact,status,high,critical,completed_at}`.
Tisan independently requires complete, exact-bound, at most one-hour-old results
and integer zero high/critical findings. No request boolean becomes proof.

Independent review found and this branch fixed:

- Preflight timeout/IO/transport failure could strand the reservation. It now
  records refused and releases it; post-mutation uncertainty remains quarantined.
- Terminal deployment failure prevented all rollback. An explicit new rollback
  now verifies that exact failed deployment/pin and restores its stored previous
  SHA. Unknown/in-flight outcomes cannot use this recovery. Regression tests pass.

The reviewer confirmed those corrections on the then-pushed head. Final-head
review is still required. Later attempts to deliver the final update to review
chat failed with a tool transport HTTP request failure / HTTP 408; no review
completion is invented.

## Exact commands and results

All commands ran on the project host, in an isolated source directory. The
founder's laptop and shared production checkout were not used.

```sh
gh api repos/Tervory-AI/tervory-tank/branches/main --jq .commit.sha
gh repo clone Tervory-AI/tervory-tank /tmp/tisan-promotion-ElpCaP/repo -- --filter=blob:none --single-branch --branch main
cd /tmp/tisan-promotion-ElpCaP/repo
git switch -c codex/tisan-promotion origin/main
git config user.name Codex
git config user.email codex@users.noreply.github.com
git config credential.helper '!gh auth git-credential'
```

Read-only main check and clone succeeded. No credential value was displayed or
copied. Every completed file was committed and pushed with real `git push` to
this one branch, not an API-only publish. The commit history preserves these
checkpoints. No push or fetch failed in this lane.

Host test setup (no repository dependency changes):

```sh
python3 -m venv /tmp/tisan-promotion-ElpCaP/venv
/tmp/tisan-promotion-ElpCaP/venv/bin/pip install httpx fastapi pytest pytest-asyncio ruff
/tmp/tisan-promotion-ElpCaP/venv/bin/pip install PyYAML==6.0.3
npm install --prefix /tmp/tisan-promotion-ElpCaP/browser --no-audit --no-fund playwright@1.64.1
/tmp/tisan-promotion-ElpCaP/browser/node_modules/.bin/playwright install chromium
```

Installed host tools: Python 3.14, httpx 0.28.1, FastAPI 0.162.0, pytest 9.2.0,
pytest-asyncio 1.4.1 and Ruff 0.17.3. The production-image verification below uses
its pinned Python 3.12 requirements and pytest 9.1.1 from the repository test pin.
An attempted host `pip install asyncpg==0.30.0` failed because this host's Python
3.14 had no wheel/compiler; no dependency was upgraded to work around it. Actual
room import is checked in the Python 3.12 image instead.

```sh
PYTHONPATH=. /tmp/tisan-promotion-ElpCaP/venv/bin/python -m pytest -q tests/tisan_promotion/test_promotion.py tests/tisan_promotion/test_api.py --tb=short
```

Final focused result: **35 passed**. Earlier checkpoints grew from 22 to 35 as
review/recovery cases were added. An initial async fixture declaration was
corrected to `pytest_asyncio.fixture`; no product assertion was weakened.

```sh
LIVE_CHECK_PLAYWRIGHT_PATH=/tmp/tisan-promotion-ElpCaP/browser/node_modules/playwright python3 tests/test_live_check.py
TISAN_TEST_PLAYWRIGHT=/tmp/tisan-promotion-ElpCaP/browser/node_modules/playwright PYTHONPATH=. /tmp/tisan-promotion-ElpCaP/venv/bin/python -m pytest -q tests/tisan_promotion/test_browser.py --tb=short
PYTHONPATH=. /tmp/tisan-promotion-ElpCaP/venv/bin/python -m pytest -q tests/test_tisan_figma.py tests/test_tisan_scaffold.py tests/test_tisan_page.py --tb=short
```

Results: **14 existing live-check tests passed** (65.125s), **3 staging-mode
browser tests passed**, **31 existing Tisan tests passed**. The first generic
checker attempt lacked Playwright in the fresh checkout; after installing the
same existing pin and preserving default Workspace module resolution, it passed.
All browser pages were local or intercepted synthetic responses, not live sites.

```sh
PYTHONPATH=. /tmp/tisan-promotion-ElpCaP/venv/bin/python -m pytest -q tests/test_secrets.py tests/test_tank_one_door.py tests/test_room_seal.py --tb=short
```

**101 passed, 2 failed**, exit 1, 64.63s. Both failures are unchanged main:
`test_no_room_service_would_leak_when_coolify_deploys_it` for
`agents/zenas/docker-compose.docassemble.yml` and
`agents/zenas/docker-compose.docassemble.za.yml`. Each reports
`docassemble would join non-internal <coolify app network>`.
[Actual safety output](evidence/safety-tests.txt).

Reproduced on an exported unchanged main tree:

```sh
mkdir -p /tmp/tisan-promotion-ElpCaP/baseline
git archive origin/main agents tests/test_room_seal.py | tar -x -C /tmp/tisan-promotion-ElpCaP/baseline
git archive origin/main docker-compose.yml | tar -x -C /tmp/tisan-promotion-ElpCaP/baseline
/tmp/tisan-promotion-ElpCaP/venv/bin/python -m pytest -q /tmp/tisan-promotion-ElpCaP/baseline/tests/test_room_seal.py -k docassemble --tb=short
```

**Same 2 failures, 72 deselected**, 0.18s.
[Baseline output](evidence/baseline-room-seal.txt). The first baseline attempt
omitted root `docker-compose.yml`; it was supplied from the same main commit
before the reported comparison. No Zenas file changed in this branch.

Static checks:

```python
import subprocess
paths = subprocess.check_output(['git','diff','--name-only','origin/main','--','*.py'], text=True).splitlines()
raise SystemExit(subprocess.run(['/tmp/tisan-promotion-ElpCaP/venv/bin/ruff','check',*paths,'--select','E9,F']).returncode)
```

```sh
node --check ops/live_check.mjs
git diff --check
docker compose --env-file /dev/null -f agents/tisan/docker-compose.yml config --no-interpolate --quiet
```

All exited 0. The Compose command reads no founder environment file and does not
create or update a service.

## Packaged-image verification

The final production image built successfully. Its local image ID is
`sha256:1d75808b3afbc83703df08edbe5bf26631dcfe1ec7c83a1691ef56447713e391`.
This is a local build identifier, not a deployed production claim.

```sh
/tmp/tisan-promotion-ElpCaP/venv/bin/pip download --dest /tmp/tisan-promotion-ElpCaP/test-wheels --only-binary=:all: pytest==9.1.1 pytest-asyncio==1.4.1
/tmp/tisan-promotion-ElpCaP/venv/bin/pip download --dest /tmp/tisan-promotion-ElpCaP/test-wheels --only-binary=:all: typing-extensions==4.16.0
docker build --progress=plain -f agents/tisan/Dockerfile -t tisan-promotion-offline:job11-final .
docker run --rm --network none --read-only --memory=1g --cpus=1 --cap-drop ALL --security-opt no-new-privileges --tmpfs /tmp:rw,size=1g,mode=1777 --tmpfs /data:rw,size=64m,mode=1777 -v /tmp/tisan-promotion-ElpCaP/repo:/source:ro -v /tmp/tisan-promotion-ElpCaP/test-wheels:/wheels:ro -w /source -e PYTHONPATH=/tmp/test-packages:/source:/app -e PYTHONDONTWRITEBYTECODE=1 -e PLAYWRIGHT_BROWSERS_PATH=/opt/tisan-browser -e TISAN_TEST_PLAYWRIGHT=/opt/tisan-check/node_modules/playwright -e TISAN_TEST_CHECKER=/app/ops/live_check.mjs tisan-promotion-offline:job11-final sh -c 'python -m pip install --no-index --no-cache-dir --disable-pip-version-check --find-links=/wheels --target=/tmp/test-packages pytest==9.1.1 pytest-asyncio==1.4.1 && python tests/tisan_promotion/verify_image.py'
```

Build exit 0; image verification exit 0: **69 passed in 19.90s**, no skips.
Python **3.12.16**, httpx **0.28.1**, pinned Pydantic **2.10.6**, pytest **9.1.1**.
The probe checks hashes of the packaged room entry point, promotion core/API and
ops checker against the tested source, generates the actual room OpenAPI, and
runs the fake API, real Chromium and existing Tisan regressions. It uses a
network-none, read-only, non-root, capability-dropped container with no
credentials, published ports or database service. [Full output and source
hashes](evidence/image-tests.txt). [Static command output](evidence/static-checks.txt).

Earlier image-test preparation missed an offline typing-extensions wheel and
used an invalid `.path` assumption for FastAPI's included-router object; those
harness issues were corrected. The subsequent real pinned-runtime probe exposed
an actual `TypeAdapter[tisan_promotion_api.Site]` annotation-resolution error.
Registering loaded modules in `sys.modules` fixed that product issue; the final
unmodified packaged image now passes its OpenAPI and full suite. An interim
compatibility run used a read-only source-entry-point mount while rebuilding;
that interim result is not substituted for the final no-override image proof.

The final extra rollback regression covers a build that fails before Coolify
resolves its `HEAD` placeholder. Recovery requires the exact acknowledged failed
UUID and still-pinned intended commit, then deploys the previously recorded
production SHA; it never treats unresolved HEAD as a successful deployed commit.


## CI, deployment and founder proof

No GitHub Actions run, PR CI or deployment is claimed for this new branch until
Claude opens the PR and the actual checks run. No trigger-only push or CI rerun.
No model call, production SQL, real Coolify call, DNS proof, live scan, deployment
or customer-content mutation was performed.

Still needed after merge: Radix job 8 deployment; founder-owned real test site;
existing staging/production application identifiers and correct Git pins; the
founder-managed Coolify settings; Radix staging-domain authorization; successful
real promotion and rollback; and screenshots from the founder's own browser with
matching staging/production deployment SHAs and the operation audit. Those inputs
and screenshots are not supplied by an offline test. See
[the runbook](../../agents/tisan/PROMOTION.md#founder-acceptance-still-required).


## Append-only checkpoint log

### 2026-10-28 16:43:28 PDT (UTC-07:00) / 2026-10-28 23:43:28 UTC

- Branch: `codex/tisan-promotion`.
- Recorded published head **before this report-only commit**: `b795b4f50a3a611e88840fa002ae4b591bdbbd86`.
- Tested source/test SHA: `8143a8ec42ef724de2fd4163d072967643b2fe82`. Later changes before this entry are evidence-only; packaged source hashes are retained above.
- Commands/results: final network-none image command above **69 passed / exit 0**; generic live-check **14 passed**; final Ruff/Node/diff/isolated Compose checks **exit 0**. Safety comparison remains **101 passed / 2 unchanged main failures**, reproduced with the same two failures on main. No settled suite was rerun merely to refresh this report.
- Open findings: the reviewer's preflight-lock and failed-deployment rollback findings are fixed and regression-tested. Final-head independent review remains pending; review-chat sends failed with tool transport errors / HTTP 408 and will be retried under the founder's latest authorization.
- Publish state: all completed files pushed by serialized normal Git pushes; no force push, no main push, no PR exists. Claude opens the PR from this branch. The final report commit/head is reported in the handoff after push.
- Dependency: Radix job 8 is still required, with its published checkpoint recorded above; its owner's push issue is recoverable under the founder's latest instruction, but no recovery/merge/deployment is assumed here. Missing gate stays a refusal.
- Founder acceptance: **pending**. No real site, DNS authorization, Coolify setting values or founder screenshots were fabricated. No live scan, promotion, rollback, deployment or production migration occurred.

### 2026-10-28 16:44:25 PDT (UTC-07:00) / 2026-10-28 23:44:25 UTC

- Branch `codex/tisan-promotion`; published checkpoint `e2d360b656e0b3b5c7743ad0a687eacff88a7aa4` verified equal to the remote branch with `git ls-remote origin refs/heads/codex/tisan-promotion refs/heads/main`. Main remains `7a13687de256896c488a0f28e0906fbcbce5b046`; working tree was clean. This append is report-only. Tested SHA remains `8143a8ec42ef724de2fd4163d072967643b2fe82`; no code or test changed and settled checks were not repeated.
- Publication succeeded with a normal serialized fast-forward push. Claude's PR handoff is ready; no PR exists and no main merge/deploy was performed.
- Final-head review notification was retried under the founder's latest authorization. The exposed tool again failed: `Transport send error`, `HTTP request failed`, `error sending request for url (http://127.0.0.1:50375/mcp)`. This is the remaining coordination access blocker, not a Git push failure. No final-head approval is claimed. The final report-only commit SHA is included in the chat handoff.
- Open acceptance remains unchanged: real founder-owned staging/production site and DNS authorization, deployed Radix gate, founder-managed Coolify values, live promotion/rollback and founder-browser evidence. The branch retains fail-closed behavior.

### 2026-10-28 16:44:55 PDT (UTC-07:00) / 2026-10-28 23:44:55 UTC

- Branch `codex/tisan-promotion`; recorded pushed head before this report-only update: `3dd2693eacf231491a6d28422bf3304be34929f1`. Packaged tested SHA remains `8143a8ec42ef724de2fd4163d072967643b2fe82` (**69 passed**). No implementation/test changes or repeated builder checks in this checkpoint.
- Independent reviewer confirmed local=remote at reviewed published head `e2d360b656e0b3b5c7743ad0a687eacff88a7aa4`, reviewed the final code/proof including early-failed-HEAD rollback, and reported **no outstanding actionable finding**. Subsequent commits are append-only report changes. This inbound review resolves the previously pending code-review result; the earlier outgoing tool errors remain historical facts.
- Reviewer independently ran `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /tmp/tervory-priority-312/bin/python -m pytest -q -p no:cacheprovider tests/tisan_promotion/test_promotion.py --tb=short` on `e2d360b`: **33 passed in 1.02s, exit 0**. This is attributed reviewer evidence, not a command claimed to have been run by the builder. Fake Coolify only; no live API.
- Publication: branch pushed with normal Git; Claude's new PR creation and actual PR-head CI remain pending. Founder merge and Radix deployment remain required. No live/founder completion is claimed; real site/authorization/settings and browser promotion/rollback proof remain outstanding.

### 2026-10-28 16:48:17 PDT (UTC-07:00) / 2026-10-28 23:48:17 UTC

- Publication update: coordinator created draft [PR #425](https://github.com/Tervory-AI/tervory-tank/pull/425) from published head `99a443801563140ced96f21225b9475fbbf2935c`; branch remains `codex/tisan-promotion`. Earlier Claude-opening/no-PR statements above are historical handoff records, superseded by this actual publication checkpoint. Founder alone merges.
- This checkpoint is report-only; no implementation/test change. Tested SHA remains `8143a8ec42ef724de2fd4163d072967643b2fe82` with packaged **69 passed**, independent reviewed code head `e2d360b656e0b3b5c7743ad0a687eacff88a7aa4` with **33 core passed**.
- Actual PR checks at head `99a4438`: CodeQL actions/JavaScript/Python, CI security/changes and live-check are in progress; runner selection skipped. No failed result was present at this check. These are pending, not claimed green. The report-only push creates a new PR head whose actual results must be read separately. No settled offline checks rerun.
- The PR is attached to this chat. Its description is being refreshed from this report with commit-specific GitHub file/evidence links; the reviewer receives the pushed report-only head. Radix dependency remains fail-closed, and founder real-site/authorization/settings/live-browser proof remains pending. No merge, live scan or deployment.

### 2026-10-28 16:52:12 PDT (UTC-07:00) / 2026-10-28 23:52:12 UTC

- Draft [PR #425](https://github.com/Tervory-AI/tervory-tank/pull/425) attached; branch `codex/tisan-promotion`, published head before this report update `af6a01c1e599127a93f019d9e29bcd95fcd8f453`. Description updated from the report with 22 verified commit-specific file/evidence links, then read back byte-for-byte. `gh pr edit ... --body-file` failed on deprecated GraphQL `projectCards`; recovered using `gh api --method PATCH repos/Tervory-AI/tervory-tank/pulls/425 --input /tmp/tisan-promotion-ElpCaP/pr-body.json`, exit 0. Historical Claude handoffs remain historical, not current blockers.
- Concrete collection defect found while checking full CI: `PYTHONPATH=. /tmp/tisan-promotion-ElpCaP/venv/bin/python -m pytest --collect-only -q tests/tisan_promotion/test_api.py tests/zenas_za_laws_africa/test_api.py --tb=short` exited 2 with an imported-module `test_api` file mismatch. Renamed this job's file to `test_tisan_promotion_api.py` (100% unchanged test content) in `f3022aa`, and updated the image runner's selected path in `af6a01c`. No product implementation changed.
- Verification: `PYTHONPATH=. /tmp/tisan-promotion-ElpCaP/venv/bin/python -m pytest --collect-only -q tests/tisan_promotion/test_tisan_promotion_api.py tests/zenas_za_laws_africa/test_api.py --tb=short` => **18 collected, exit 0**; `PYTHONPATH=. /tmp/tisan-promotion-ElpCaP/venv/bin/python -m pytest -q tests/tisan_promotion/test_tisan_promotion_api.py --tb=short` => **2 passed in 0.42s, exit 0**. Ruff on renamed test/runner passed and the runner path exists. A redundant `git add` of the removed filename printed a pathspec error; `git mv` had already staged the exact rename, and the intended commit and normal push succeeded.
- Settled packaged **69 passed** at source/test SHA `8143a8ec42ef724de2fd4163d072967643b2fe82` and independent **33 passed** at reviewed code `e2d360b` remain historical exact-source evidence; neither broad suite was repeated. Current affected-test proof is the collection/name fix above. New PR-head CI is pending after these necessary pushes; no current-head all-green claim. Before the fix, CodeQL actions/JavaScript/Python and CI changes passed, security/Tank/Workspace/live-check were in progress.
- Radix owner reports normal serialized ref-lock recovery completed, published `8fcd1061289407b9d730b3d6da1eb137491a3cb9`, unchanged agreed API. Live GitHub read now finds [draft #426](https://github.com/Tervory-AI/tervory-tank/pull/426) at `95a5910356adabf03f035915c4e973b7affb0952`. This supersedes the old stopped-publication status, not the review/merge/deploy dependency. Tisan stays fail-closed until the real gate is available.
- Reviewer notification attempted for publication head `1e63513` and still returned the recorded tool transport failure. Final report-only head will be sent again. Founder merge, actual PR CI, Radix deployment and live founder/browser acceptance remain pending. No merge, secret values, live scan, deployment or fabricated evidence.
