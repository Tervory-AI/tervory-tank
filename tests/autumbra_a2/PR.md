# PR #608 review fixes — 3 November 2026

All seven review items at `c5afd368` are fixed on the same branch. CI's **Tank job on the final PR head** is the full-suite test of record; the earlier build-box full-suite results below are historical, not the acceptance result for this review.

## Changes and proof locations

1. `agents/ghost/smtp_email.py:23`: normalize every exception from address/port parsing to `ValueError("mail_not_configured")`. Partially configured or malformed SMTP reports `unavailable`, with `/health` still 200. `tests/test_autumbra_a2.py:371` covers empty FROM and two malformed FROM values with HOST set.
2. `agents/ghost/smtp_email.py:35`, `agents/ghost/app.py:278`: persist the first valid SMTP availability moment in Watch's own `owner-email-availability.json`, under the existing atomic file-lock pattern. Health can establish this moment before the scheduler starts. Only action receipts strictly newer than it are eligible. The `act:` + receipt ID claim remains unchanged across restarts. Each action email is built from that action's receipt, retaining its own signed Undo link. `tests/test_autumbra_a2.py:384` proves old receipts produce zero emails, one new receipt sends once, and reopening Watch's state does not resend.
3. `agents/ghost/webhooks.py:210`, `agents/ghost/app.py:866`: explicitly distinguish verified HMAC and native envelopes. Native Cloudflare/Google/Google Workspace events store only the latest verified metadata per provider (provider, byte count, body hash, verification time) in Watch's own folder and always return `accepted=true`, `queued=false`. They never use body-supplied tenant/site/address to authorize an action. Raw bodies and credentials are not stored. The HMAC queue path is preserved. `tests/test_autumbra_a2.py:432` and `:463` cover all three native names with another tenant's ID and the still-working HMAC path.
4. `ops/seal-check.sh:279`: require all Enforce companion services for every app containing an `enforce` service, regardless of Coolify name. `tests/test_room_seal.py:619` covers both the usual name and `agent-placeholder-custom`, with complete services and each missing companion.
5. `ops/seal-check.sh:142`: execute Enforce's exactly-one-internal-network check before the per-project branch can continue. The existing project/label/internal-flag checks also remain. Extra-network tests assert this check's actual rejection message. `docs/ops/AUTUMBRA-ENFORCE-ISOLATION.md:15` describes the checks that execute.
6. `ops/seal-check.sh:41`, `:89`, `:259`: keep the four original rooms and Watch mandatory; require Enforce only when an app containing Enforce is present. Presence tracking also works with another Coolify name. `tests/test_room_seal.py:605` proves a Watch host without Enforce passes; the unsealed-Enforce regression and both resource-name cases still fail when required isolation/services are absent.
7. `.github/workflows/tenant-rls.yml:4`: remove `codex/autumbra-a2-hardening` from the push trigger. Pull-request checks remain enabled.

No page, product copy, network attachment, new outbound host or setting value was added. The durable cap, shared Rig mailer, Google verification/key path, CI compose probe and Market Lab read remain intact. No live-host probe, live provider push, SMTP send or production SQL was used for these review checks.

## Exact commands and results

Working directory: `/workspace/codex-autumbra-a2`. All focused pytest commands below used the exact prefix:

```bash
PYTHONPATH=.proof/python:tank TMPDIR=/workspace/codex-autumbra-a2/.proof/tmp /tmp/base-reliability-venv/bin/python -m pytest
```

| Arguments following that prefix | Result |
| --- | --- |
| `-q tests/test_autumbra_a2.py -k 'smtp or no_smtp'` | 4 passed, 18 deselected, 2.82s |
| `-q tests/test_autumbra_webhooks_redteam.py` | 5 passed, 2.05s |
| `-q tests/test_autumbra_a2.py::test_cloudflare_dashboard_test_hits_native_watch_route tests/test_autumbra_webhooks_redteam.py` | 6 passed, 2.37s |
| `-q tests/test_room_seal.py::test_seal_check_reports_sealed_rooms tests/test_autumbra_cloudflare_live.py::test_seal_checks_enforce_observer_and_both_proxies` | 7 passed, 24.42s |
| `-q tests/test_autumbra_a2.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1` | 30 passed, 14 warnings, 11.82s |
| `-q tests/test_room_seal.py` | 106 passed, 149.01s |
| `-q tests/test_autumbra_a2.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1` after the required main merge | 30 passed, 14 warnings, 6.72s |

The combined affected check includes every existing Ghost/Autumbra test, the one-door check and all seal regressions. Its source tree includes main `3c336a75` and the seven review fixes:

```bash
env -i PATH="$PATH" LANG=C.UTF-8 TMPDIR=/workspace/codex-autumbra-a2/.proof/tmp PYTHONPATH=/workspace/codex-autumbra-a2/.proof/python:/workspace/codex-autumbra-a2/tank DATA_DIR=/workspace/codex-autumbra-a2/.proof/placeholder-review608 /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_ghost_*.py tests/test_autumbra_*.py tests/test_tank_one_door.py tests/test_room_seal.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 > .proof/review608-affected.txt 2>&1
```

**Exit 0: 644 passed, 3 skipped, 15 warnings in 280.13s.** The three existing skips include the opt-in cloud/CI checks; local tests never arm the Enforce compose probe on the live builder host.

```bash
PYTHONPATH=.proof/python /tmp/base-reliability-venv/bin/python -m ruff check --select E9,F agents/ghost/smtp_email.py agents/ghost/webhooks.py agents/ghost/app.py tests/test_autumbra_a2.py tests/test_room_seal.py
bash -n ops/seal-check.sh
git diff --check
```

All exited 0; Ruff printed `All checks passed!`. `yaml.safe_load(Path('.github/workflows/tenant-rls.yml').read_text())` also passed (`tenant-rls.yml: valid YAML`).

Started with `git fetch origin && git merge origin/main`. Repeated `git fetch origin && git merge origin/main` before every sequential `git push origin HEAD:codex/autumbra-a2-hardening`. A later main merge to `3c336a75` conflicted only in `.env.example`; retained both A2 Watch names and Trigger bot names, ran the 30 A2 tests, committed the merge and pushed successfully. No push failed and none ran in parallel.

## Final-head CI record

[PR #608 checks](https://github.com/Tervory-AI/tervory-tank/pull/608/checks) are the full-suite record. The exact final head, Tank conclusion, run URL and test summaries are recorded in [the PR description](https://github.com/Tervory-AI/tervory-tank/pull/608) after this evidence commit, so recording CI does not change the tested head. This file does not predict a CI result before the final push. No further source changes follow the final-head result.

---

The original implementation evidence follows unchanged. Its earlier local failures and pre-review CI links describe those earlier snapshots, not the final review head.

# Autumbra A2 hardening

Autumbra now persists its per-tenant hourly cap, claims owner-email delivery durably before using the existing Rig/Tiger SMTP sender, verifies native Cloudflare and Google push authentication, includes Watch/Enforce in the seal audit, and consumes the existing Market Lab contract through Tank. No UI, visible product wording, production schema, live control, Enforce egress or network placement changes are included.

## Changes for review

- `agents/ghost/durable_state.py:11`, `never_block.py:138`, `enforce_app.py`, `threat_queue.py`: the existing atomic JSON replacement plus a stable file lock serializes cap claims across processes. Each tenant retains the same limit, sliding hour and messages after restart. Unreadable state refuses an action.
- `agents/ghost/smtp_email.py:35`, `owner_email.py`, `owner_email_jobs.py:306`, `app.py:249`: reuse Rig's `SmtpMailer`, including its existing TLS behavior. Claim tenant/message identity before sending. Interrupted/uncertain attempts are never automatically sent again. Weekly identity is stable for the UTC week; act identity is the receipt ID. Only Watch sends SMTP, from worker threads; Enforce remains closed and emits receipts. Bodies and recipients are absent from durable attempt metadata. Emails use the existing receipt-only builder and copy.
- `tank/autumbra_google_keys.py:23`, `tank/ghost_routes.py`: Tank alone discovers/fetches Google's public keys through `access.public_get`, honors Cache-Control/Age and coalesces refreshes without holding the shared lock during HTTP. Unknown-kid refresh is limited to once per minute. The GET signing-key route accepts only Autumbra's room key and returns only public keys. No token, claims, body or other Watch data travels to it.
- `agents/ghost/native_webhooks.py:33`, `webhooks.py`: Cloudflare checks `cf-webhook-auth`; Google checks RS256, key ID, issuer, exact audience, expiry, exact service-account email and verified-email claim. Missing settings or unavailable keys refuse native pushes. Existing HMAC callers retain their existing path. Replay metadata is durable: Google uses authenticated subscription/message identity for at least the token lifetime, allowing one token to authenticate different messages. Cloudflare provides a static secret, not a signed timestamp; duplicate-body suppression lasts ten minutes and cannot prove arbitrary historical freshness.
- `ops/seal-check.sh:41`, `tests/test_room_seal.py`: the original four required rooms remain, with Watch and Enforce added. Watch/browser must have only their declared corridor; Enforce only one internal network. Missing required services and any extra attachment fail.
- `.github/workflows/tenant-rls.yml:94`, `tests/autumbra_a2/test_compose_probe.py:15`, `docker-compose.probe.yml`: run the unchanged probe on disposable, internal-only GitHub CI compose networks. Confirm both isolation success and failure after attaching the synthetic hub. Refuse armed execution outside GitHub. No probe ran on the live Boston host.
- `agents/ghost/app.py:303`: reuse ML3's scheduled Tank consumer and existing validator, catalog and source-credit receipt builder. Deduplicate per-tenant bundle receipts. Missing ML3 returns unavailable health and preserves the current catalog; there is no live fixture fallback.
- `agents/ghost/Dockerfile`, `requirements.txt`, `docker-compose.yml`, `.env.example`: package the existing Rig sender and pinned JWT dependencies; add Watch setting names only. Compose networks, volumes, ports and deployment mode are unchanged. Cloudflare connected-edge work is untouched.
- `docs/ops/AUTUMBRA-ENFORCE-ISOLATION.md:5`: founder's read-only, post-deployment live check. The Enforce memory cap remains unchanged.

## Settings (names only)

Watch: `AUTUMBRA_SMTP_HOST`, `AUTUMBRA_SMTP_PORT`, `AUTUMBRA_SMTP_FROM`, `AUTUMBRA_SMTP_USER`, `AUTUMBRA_SMTP_PASSWORD`; `AUTUMBRA_CLOUDFLARE_WEBHOOK_SECRET`; `AUTUMBRA_GOOGLE_PUSH_AUDIENCE`, `AUTUMBRA_GOOGLE_PUSH_SERVICE_ACCOUNT`. Existing `AUTUMBRA_EDGE_WEBHOOK_SECRET` and `AUTUMBRA_MAILBOX_WEBHOOK_SECRET` remain available to legacy HMAC callers. The founder supplies all values in Coolify. No values were read, created, committed, logged or included in receipts.

With no SMTP settings health says `fixture`; partial invalid settings say `unavailable`. Native Google/Cloudflare refuse when their required configuration is absent. Real delivery also needs the existing permitted SMTP path; no new egress is added by this branch. A durable `sending`/`uncertain` claim intentionally needs manual investigation, never automatic resend.

## Provider contract sources

- [Cloudflare notification webhooks](https://developers.cloudflare.com/notifications/get-started/configure-webhooks/): configure the same secret in Cloudflare; it arrives in `cf-webhook-auth`. The dashboard's Save and Test is founder acceptance, not simulated evidence.
- [Google authenticated Pub/Sub push](https://cloud.google.com/pubsub/docs/authenticate-push-subscriptions): signature, audience and service-account email validation; Google can reuse tokens for multiple deliveries.
- [Google Alert Center notifications](https://developers.google.com/workspace/admin/alertcenter/guides/notifications): configure Pub/Sub notification settings and the Alert Center publisher. Authentication belongs to the Pub/Sub push delivery.
- [Google OIDC discovery](https://accounts.google.com/.well-known/openid-configuration): Tank reads `jwks_uri`; Watch never fetches externally.

ML3 had not landed on main when wired. The implementation reuses the consumer from `origin/codex/market-lab-ml3`; its current fetched head is `e2732ab09b1660804d05c51d92f08ae0c5533e0a`. Its contract is GET `/v1/market-lab/intel` with the Autumbra room key, returning a direct `market_lab.ioc.v1` bundle. Tests supply a synthetic contract bundle only; real availability awaits that route's deployment.

## Validation and limitations

No production SQL or permanent data change was made. Full-suite SQL targets only a disposable PostgreSQL 17 container with synthetic databases. Local tests are offline; the suite disables sockets except loopback/Unix. No provider, SMTP or model calls check this work. Docker isolation proof runs only on GitHub.

### Exact validation commands

Commands ran in `/workspace/codex-autumbra-a2` unless a different working directory is shown. `.proof/python` is this checkout's private dependency target; `/tmp/base-reliability-venv/bin/python` supplies the interpreter. No shared dependency target was modified.

```bash
# Private offline test dependencies (all installs exited 0).
/tmp/base-reliability-venv/bin/python -m pip install --target .proof/python --upgrade --no-cache-dir --index-url https://pypi.org/simple -r tank/requirements.txt -r tank/requirements-dev.txt
/tmp/base-reliability-venv/bin/python -m pip install --target .proof/python --upgrade --no-cache-dir --index-url https://pypi.org/simple boto3==1.40.47 botocore==1.40.76 trimesh==4.9.0
npm ci --prefix workspace --ignore-scripts --no-audit --no-fund

# Final affected suite; values here are synthetic test paths only.
env -i PATH="$PATH" LANG=C.UTF-8 TMPDIR=/workspace/codex-autumbra-a2/.proof/tmp PYTHONPATH=/workspace/codex-autumbra-a2/.proof/python:/workspace/codex-autumbra-a2/tank DATA_DIR=/workspace/codex-autumbra-a2/.proof/placeholder-a2-final /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_ghost_*.py tests/test_autumbra_*.py tests/test_tank_one_door.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1

PYTHONPATH=.proof/python /tmp/base-reliability-venv/bin/python -m ruff check --select E9,F agents/ghost/durable_state.py agents/ghost/smtp_email.py agents/ghost/native_webhooks.py tank/autumbra_google_keys.py tests/test_autumbra_a2.py tests/autumbra_a2/test_compose_probe.py
bash -n ops/seal-check.sh ops/autumbra-enforce-isolation-check.sh
git diff --check
```

Ruff printed `All checks passed!`; shell/whitespace checks exited 0. `yaml.safe_load(Path(name).read_text())` passed for Ghost's two existing compose files, the CI probe compose file and the changed workflow. `tests/test_room_seal.py` passed 97 tests in 90.70s. `tests/test_autumbra_a2.py` passed 22 tests in 6.77s. The affected-suite final result is recorded below.

The whole suite runs from a **detached test worktree** at `5ddd01bbf8e448ab87f6a7c343a73300148b9f10`, so required later merges cannot modify files during tests. This creates no second development branch. Working directory: `/workspace/codex-autumbra-a2/.proof/full-suite`.

```bash
git -C .proof/full-suite checkout --detach 5ddd01bb
# Only our disposable PostgreSQL container, never a production database:
docker exec autumbra-a2-placeholder-9a947e97-pg psql -U postgres -d placeholder -v ON_ERROR_STOP=1 -c 'CREATE DATABASE placeholder_full' -c 'CREATE DATABASE placeholder_full_test'

env -i PATH="$PATH" LANG=C.UTF-8 TMPDIR=/workspace/codex-autumbra-a2/.proof/tmp PYTHONPATH=/workspace/codex-autumbra-a2/.proof/python:/workspace/codex-autumbra-a2/.proof/full-suite/tank PLAYWRIGHT_BROWSERS_PATH=/workspace/codex-autumbra-a2/.proof/browsers DATA_DIR=/workspace/codex-autumbra-a2/.proof/placeholder-full-snapshot DATABASE_URL=postgresql://postgres@127.0.0.1:32836/placeholder_full_test POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32836/placeholder_full RLS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32836/placeholder_full RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32836/placeholder_full RADIX_PASSIVE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32836/radix_passive_test SUITE_WORKERS=2 SUITE_BUDGET_SCALE=2 /tmp/base-reliability-venv/bin/python .github/scripts/offline_suite.py
```

The suite runner executes main, `tests/tiger_g5`, and `tests/zenas_regulation_alerts` separately. Its existing exclusions are `tests/ci_security` and `tests/test_live_check.py`, which have separate workflows. Two workers and doubled wall-clock budgets limit load on the host; per-test timeouts stay unchanged.

### Earlier runs and corrections

- Initial A2 run: 1 failed, 15 passed. Corrected the concurrent unknown-key refresh race; the later run passed 20 tests, then 22 after replay-lifetime and act-email coverage.
- Initial broad affected run: 1 failed, 383 passed, 3 skipped, 1 teardown error. Restored legacy missing-signature rejection counts and made the existing Starlette fixture cleanup idempotent. Next run exposed a persistent cap-test directory (1 failed, same 383 passed/3 skipped and teardown error); isolated it with `tmp_path`. The pinned rerun passed 384, skipped 3.
- Initial seal run: 1 failed, 97 passed. Removed the unsolicited raw-compose deployment-mode marker because it would affect live volume naming; final run passed 97. Deployment mode remains unchanged; actual extra attachments are reported as leaks.
- Initial full-suite run: interrupted with exit 130 when a required main merge changed files beneath the running checkout. Partial result: 2,183 passed, 5 skipped, 11 errors in 400.27s. Five collection errors were missing existing Forge dependencies; six errors were the test contract's required `radix_passive_test` database name. Installed the existing Forge pins into the private target, corrected the synthetic database name, and moved the final run to a fixed detached worktree.
- A final affected-suite command initially named the nonexistent `tests/test_one_door.py`: no tests ran, exit 4. Reran with the existing `tests/test_tank_one_door.py`.
- `gh run view 41647761964 --log` initially could not write its temporary cache (`disk quota exceeded`). Reran with `TMPDIR` inside this checkout and retrieved the log successfully; no shared files were removed.

### GitHub CI proof

[Run 41647761964](https://github.com/Tervory-AI/tervory-tank/actions/runs/41647761964), head `5ddd01bbf8e448ab87f6a7c343a73300148b9f10`, completed successfully:

- `autumbra-isolation`: `python -m pytest -q -s tests/autumbra_a2/test_compose_probe.py` — **1 passed in 21.92s**, including the deliberately leaked synthetic network rejection. Artifact: `autumbra-isolation`.
- `isolation`: **393 passed in 159.57s**. RLS matrix: 230 actual tables across 13 schemas; read/insert/update/delete, missing/empty/reused tenant and founder bypass passed.
- `nonroot-services`: successful build/start of all four existing services without root or external network.

The fake-Docker seal sample (not the live host) returned exit 0:

```text
tervory-tankmain (tankuuid): not a room, skipped
agent-base (baseuuid): sealed
agent-radix (radixuuid): sealed
agent-tiger (tigeruuid): sealed
agent-rig (riguuid): sealed
agent-ghost (placeholder-watch): sealed
autumbra-enforce (placeholder-enforce): sealed
```

## Founder acceptance still required

No founder browser/inbox/dashboard screenshots are available, and no live result is claimed. After deployment and founder-supplied settings, the founder must verify the same hour's cap survives a restart, receive the weekly owner email built from real receipts, and use Cloudflare's dashboard test to verify an authentic notification passes while a forged one is refused. Attach the founder's screenshots and observed results to the PR. The founder alone runs the documented live isolation check; Claude opens the PR and the founder merges.

### Main merge during validation

`origin/main` advanced to `63fbb176` (Cloudflare hand #566). Fetch succeeded; merging produced conflicts only in `.env.example` and `ops/seal-check.sh`. Kept both settings groups, A2's mandatory Watch/browser services, and main's mandatory Enforce/egress-proxy/health-observer/health-egress-proxy services with their exact labelled network placements. Updated fake-Docker fixtures to represent that existing main topology. No connected-edge implementation was changed by the conflict resolution.

Merge seal run: 96 passed, 1 failed in 159.45s; the rejection was correct but the test expected the former `NOT SEALED` wording rather than main's `LEAK:` wording. Corrected that assertion. The targeted test plus the probe-docstring regression passed: **2 passed in 5.37s**. The earlier full affected rerun had **385 passed, 3 skipped, 1 failed** in 185.35s because the probe docstring omitted its module command; restored that command without changing runtime behavior, and its direct rerun passed in 0.99s.

```bash
PYTHONPATH=.proof/python:tank TMPDIR=/workspace/codex-autumbra-a2/.proof/tmp /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_room_seal.py::test_autumbra_enforce_without_internal_network_fails tests/test_autumbra_third_review_18.py::test_18_isolation_doc_probe_honesty
git fetch origin
git merge origin/main
git push origin HEAD:codex/autumbra-a2-hardening

env -i PATH="$PATH" LANG=C.UTF-8 TMPDIR=/workspace/codex-autumbra-a2/.proof/tmp PYTHONPATH=/workspace/codex-autumbra-a2/.proof/python:/workspace/codex-autumbra-a2/tank DATA_DIR=/workspace/codex-autumbra-a2/.proof/placeholder-a2-merged /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_ghost_*.py tests/test_autumbra_*.py tests/test_tank_one_door.py tests/test_room_seal.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
```

Push succeeded (`5ddd01bb..1e0d7613`). Every push was sequential and preceded by a main merge. `90732449` is an ancestor of this branch; the previously rejected push did not lose those commits.

Post-merge CI [run 41650602599](https://github.com/Tervory-AI/tervory-tank/actions/runs/41650602599), head `1e0d7613a8a7ef52dde5d444a70c804bd0a81bb6`, also passed all three jobs: Enforce probe **1 passed in 22.16s**, database isolation **393 passed in 164.44s**, and nonroot services successful.

Post-merge combined affected suite: **616 passed, 3 skipped, 1 failed in 358.09s**. The failing newly landed main test `test_seal_checks_enforce_observer_and_both_proxies[None]` represented the four original rooms and Enforce but omitted mandatory Watch. Added only Watch/browser to that synthetic sample. Its six fault variants then passed in 11.49s; no connected-edge runtime changed. Pushed as `41c60b69` after another fetch/main merge. The final combined rerun uses a fresh synthetic data directory `.proof/placeholder-a2-complete` (otherwise the same exact combined command above).

## Final local results

- Final merged affected command: **617 passed, 3 skipped, 15 warnings in 323.63s**, exit 0. Complete output: [affected-suite.txt](affected-suite.txt).
- Full offline runner at the fixed source snapshot: **main: 20 failed, 6,541 passed, 131 skipped, 137 warnings, 1,799 subtests passed in 1,894.31s**; Tiger G5: **46 passed, 28 warnings in 48.77s**; Zenas regulation alerts: **40 passed, 14 warnings in 25.19s**. Runner exit 1, total 1,978s. Complete output, all failures/skips/durations: [full-suite.txt](full-suite.txt). This run is **not green**.
- The full snapshot still contains the old probe docstring; its failure was fixed and is covered by the green 617-test affected run. Other failed tests are outside Autumbra; their causes are not all established as pre-existing. No unrelated implementation was changed to conceal those failures.
- Full-run failures include absent `manifold3d`/`feedparser` and unavailable Trigger checker dependencies, the Tiger alert test's 2-second latency threshold, a detached-worktree worker-runner case, Base engine/sweep checks, skill offline evaluations, and three local Market Lab service-startup checks. See the complete output for exact assertions; pending startup failures are not claimed resolved.

A subsequent required main merge advanced to `8cd286c7` (Trigger work). `.env.example` was the only conflict; retained both A2's Watch setting names and Trigger's new setting names. `tests/test_autumbra_a2.py` plus all six connected-seal variants passed **28 tests in 17.43s** after the merge. Pushed `df8a4853e364dd9bd3bd7d49ee989e430af14f94`. No A2 runtime changes followed the green 617-test run.

The missing existing test dependencies were then installed into this checkout's private target, exit 0:

```bash
/tmp/base-reliability-venv/bin/python -m pip install --target .proof/python --upgrade --no-cache-dir --index-url https://pypi.org/simple manifold3d==3.2.1 feedparser==6.0.14 proselint==0.16.0
```

### Original-main comparison

A detached checkout of the snapshot's original main commit `ecef216b` ran the same 16 failed test IDs, excluding the already-fixed A2 docstring and three Market Lab local startup cases: **15 failed, 1 passed in 84.20s**, exit 1. The passing rerun was Tiger's timing test. The other 15 failures reproduce outside this branch; this establishes reproduction in this test environment, not a diagnosis of all underlying causes. Complete selected IDs/assertions: [baseline.txt](baseline.txt). Three local Market Lab startup failures remain unclassified.

Exact comparison command (working directory `.proof/main-baseline`):

```bash
env -i PATH="/workspace/codex-autumbra-a2/.proof/python/bin:$PATH" LANG=C.UTF-8 TMPDIR=/workspace/codex-autumbra-a2/.proof/tmp PYTHONPATH=/workspace/codex-autumbra-a2/.proof/python:/workspace/codex-autumbra-a2/.proof/main-baseline/tank DATA_DIR=/workspace/codex-autumbra-a2/.proof/placeholder-baseline /tmp/base-reliability-venv/bin/python - <<'PY'
import re, subprocess, sys
from pathlib import Path
log = Path('/workspace/codex-autumbra-a2/.proof/full-tank-suite-final.txt').read_text()
ids = re.findall(r'^FAILED (\S+)', log, re.M)
ids = [i for i in ids if 'test_autumbra_' not in i and 'test_market_lab_' not in i]
raise SystemExit(subprocess.call([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '--disable-socket', '--allow-unix-socket', '--allow-hosts=127.0.0.1,localhost,::1', *ids]))
PY
```

Latest code-bearing merge CI [run 41654115219](https://github.com/Tervory-AI/tervory-tank/actions/runs/41654115219), source head `df8a4853e364dd9bd3bd7d49ee989e430af14f94`: **success**, all three jobs green. Subsequent commits add evidence only. No claim that the full offline run is green follows from the green isolation workflow.

Cleanup: `docker stop autumbra-a2-placeholder-9a947e97-pg` exited 0. The disposable container used `--rm`, so its synthetic database storage was removed. No live container was stopped and no production data was accessed.

## Changed-file line anchors

These are the actual changed hunks relative to merged `origin/main` at `8cd286c7`, not a claim of live deployment. Evidence files start at line 1.

| File | Changed line anchors |
| --- | --- |
| `.env.example` | 509 |
| `.github/workflows/tenant-rls.yml` | 4, 94 |
| `agents/ghost/Dockerfile` | 4, 8 |
| `agents/ghost/app.py` | 6, 49, 52, 270, 276, 368, 392, 850, 852, 1269 |
| `agents/ghost/docker-compose.yml` | 21 |
| `agents/ghost/durable_state.py` | 1 |
| `agents/ghost/enforce_app.py` | 228, 310, 343 |
| `agents/ghost/enforce_isolation_probe.py` | 3, 6 |
| `agents/ghost/native_webhooks.py` | 1 |
| `agents/ghost/never_block.py` | 10, 139, 141, 144, 151, 163, 167 |
| `agents/ghost/owner_email.py` | 308, 314 |
| `agents/ghost/owner_email_jobs.py` | 16, 323, 377 |
| `agents/ghost/requirements.txt` | 1 |
| `agents/ghost/smtp_email.py` | 1 |
| `agents/ghost/threat_queue.py` | 488 |
| `agents/ghost/webhooks.py` | 201 |
| `docs/ops/AUTUMBRA-ENFORCE-ISOLATION.md` | 5, 118 |
| `ops/autumbra-enforce-isolation-check.sh` | 3 |
| `ops/seal-check.sh` | 30, 41, 122, 173, 194, 207, 212, 243, 267, 301 |
| `tank/autumbra_google_keys.py` | 1 |
| `tank/ghost_routes.py` | 18, 27, 41 |
| `tests/autumbra_a2/affected-suite.txt` | 1 |
| `tests/autumbra_a2/baseline.txt` | 1 |
| `tests/autumbra_a2/docker-compose.probe.yml` | 1 |
| `tests/autumbra_a2/full-suite.txt` | 1 |
| `tests/autumbra_a2/test_compose_probe.py` | 1 |
| `tests/test_autumbra_a2.py` | 1 |
| `tests/test_autumbra_cloudflare_live.py` | 205 |
| `tests/test_autumbra_never_block.py` | 30, 37 |
| `tests/test_ghost_routes.py` | 49 |
| `tests/test_room_seal.py` | 27, 219, 223, 246, 265, 278, 279, 302, 335, 336, 349, 350, 364, 475, 539 |
| `tests/autumbra_a2/PR.md` | 1 |
