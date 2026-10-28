# Radix verified-domain passive scans and Tisan gate (job 8, I2/I8)

Radix now issues tenant-bound public DNS TXT challenges and permits a passive assessment only after the sealed room's egress peer verifies the persisted challenge. Scanners can tunnel only to that run's exact verified HTTPS host. ZAP runs a passive baseline automation plan; Nuclei runs one checksum-pinned upstream GET/header template, with no active attack templates, OAST, discovery or runtime updates.

The gate reads the newest persisted assessment for the exact tenant, target and immutable commit/image identity. Missing, pending, failed, stale, future-dated or high/critical results deny promotion. Tisan owns the server-side staging revision checks and its promotion integration on `codex/tisan-promotion`; it must keep the deployed artifact stable across browser check, scan and gate. Merge this Radix branch first. There is no passing stub.

## Publication and acceptance

Claude opens the PR; the founder merges. No PR has been opened by this builder. No live scan, production SQL, migration, deployment, settings-value inspection, model call, founder screenshot or inbox proof occurred. Founder acceptance remains pending: prove one founder-owned domain via TXT and view its real passive findings. This report is backend/offline proof only.

## Append-only checkpoint history

### 2026-10-28 16:42:59 PDT (UTC-07:00) / 2026-10-28 23:42:59 UTC

- Branch: `codex/radix-passive-gate`; local implementation head `ce44c65a4b94107ce8008998d2aa3c9d53d3bc04`; fetched remote `369c908e867da194f77ebf77cceed7869699e3ee`; main `7a13687de256896c488a0f28e0906fbcbce5b046`.
- Recovery authorized by the founder after the earlier push-stop. `git status --short` was empty; `git fetch origin codex/radix-passive-gate main` succeeded; `git merge-base --is-ancestor origin/codex/radix-passive-gate HEAD` exited 0. Exactly one preserved local commit is ahead: maintenance retries after temporary database outages. No divergent commit or reset/force push.
- Earlier publication failure is preserved: two pushes overlapped. The second was rejected because the ref was at `369c908e` while it expected `d43a0de0`. No alternate API publish or retry occurred before new founder authorization. Recovery publication is pending this report checkpoint.
- Available final combined result, executed against local `ce44c65a`: `RADIX_PASSIVE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32768/radix_passive_test PYTHONPATH=agents/_chassis /tmp/radix-passive-py312/bin/python -m pytest -q tests/test_radix_passive.py agents/radix/tests tests/test_bucket1_radix.py` => **156 passed in 11.10s**, exit 0. The database is an explicitly named disposable loopback container, not production.
- `PYTHONPATH=agents/_chassis /tmp/radix-passive-py312/bin/python -m pytest -q tests/test_tank_one_door.py tests/test_secrets.py` => **29 passed in 23.78s**, exit 0 (before the final listener/maintenance-only changes). An earlier new-test literal triggered the secret regex; it was replaced by an explicit dummy placeholder, with no scanner suppression or real credential involved.
- `docker build --pull=false --progress=plain -f agents/radix/Dockerfile -t radix-passive-proof:final agents` => exit 0; image `sha256:14303e9b72d01207d684b0f879eff846f5c6701d76490f160d8fe1639328d851`, built from `d43a0de0` application code. The unpushed maintenance change is not claimed as image-tested.
- `docker run --rm --network none --memory 1g --cpus 1 --cap-drop ALL --security-opt no-new-privileges:true -e PYTHONPATH=/app -v /tmp/tervory-radix-passive-gate-20261028/tests/radix_passive/local_cli_smoke.py:/tmp/local-smoke.py:ro radix-passive-proof:final python /tmp/local-smoke.py` => exit 0; ZAP exit 0 / 4 parsed findings; Nuclei exit 0 / 1 confirmed request / 0 errors / 10 parsed findings. **This deliberately replaces HTTPS target/proxy with a synthetic HTTP loopback target in a network-disabled container to verify real CLI contracts. It does not exercise or bypass the production API.** Production DNS proof, HTTPS target validation and exact-host proxy behavior are tested separately with fake DNS, real loopback sockets and the disposable Postgres.
- Broader `tests/test_room_seal.py` => **72 passed, 2 failed**; both failures are unchanged Zenas Docassemble compose files. Fresh main archive at `7a13687`, targeted `python -m pytest -q tests/test_room_seal.py -k 'docassemble and test_no_room_service_would_leak'` => **2 failed, 72 deselected**. This branch does not fix or suppress them. No full-green hosted CI claim.
- Independent reviewer covered `d43a0de0` and published listener-close delta `369c908e`: both earlier tenant-cleanup/abandoned-lock findings resolved; no additional concrete defect identified. Unpushed `ce44c65a`, final report and PR/hosted checks remain pending review.
- Next: serialize the normal fast-forward push; verify the preserved maintenance retry directly; append final command/file-line evidence and notify reviewer with the exact published head. No live scans.

### 2026-10-28 16:44:23 PDT (UTC-07:00) / 2026-10-28 23:44:23 UTC

- Normal serialized recovery push succeeded: `git push origin codex/radix-passive-gate` fast-forwarded `369c908e` to `31b63130`, preserving `ce44c65a` and the initial report. No force push or reset.
- Added a focused gateway-lifespan test for both `OSError` and `asyncpg.PostgresConnectionError`: initial maintenance succeeds, a subsequent call fails, the 15-second retry resumes maintenance, raw exception details are absent from logs, and shutdown closes the pool. Test checkpoint `9824fcd3` was committed and pushed normally after the first push finished.
- Exact suite command: `RADIX_PASSIVE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32768/radix_passive_test PYTHONPATH=agents/_chassis /tmp/radix-passive-py312/bin/python -m pytest -q tests/test_radix_passive.py agents/radix/tests tests/test_bucket1_radix.py` => **158 passed in 9.72s**, exit 0. Application code tested is `ce44c65a` (identical at `9824fcd3`); the only working-tree test delta during that run is now committed in `9824fcd3`. The 158 total includes the earlier suites, not additional unique tests on top of them.
- `/tmp/radix-passive-py312/bin/ruff check agents/radix/passive_*.py tank/radix_passive_routes.py tests/test_radix_passive.py tests/radix_passive/local_cli_smoke.py --select E9,F` => `All checks passed!`, exit 0.
- Independent reviewer has now covered recovered `ce44c65a`: no new actionable code defect. Current exact head `9824fcd3` adds only targeted tests after the dated report. Final image rebuild, final guard output and proof assembly are in progress. Founder acceptance and hosted PR checks remain pending.

### 2026-10-28 16:47:28 PDT (UTC-07:00) / 2026-10-28 23:47:28 UTC — final implementation/proof handoff

- Published before this report: `43649291df15060c4921197a601aa9e8a5df8f1f`, branch `codex/radix-passive-gate`. Application code is unchanged from `ce44c65a4b94107ce8008998d2aa3c9d53d3bc04`; `git diff --exit-code ce44c65a -- agents/radix tank/main.py tank/radix_passive_routes.py tank/requirements-dev.txt` exited 0. Later commits add tests and append-only evidence. The ensuing report commit/head will be sent to the independent reviewer after its serialized push succeeds.
- **158 tests passed in 9.72s** (39 focused passive tests + 119 existing Radix regressions). The committed outage retry was additionally checked at `9824fcd3`: `/tmp/radix-passive-py312/bin/python -m pytest -q tests/test_radix_passive.py -k gateway_maintenance` => **2 passed, 37 deselected in 0.57s**.
- Latest guard command `PYTHONPATH=agents/_chassis /tmp/radix-passive-py312/bin/python -m pytest -q tests/test_tank_one_door.py tests/test_secrets.py` => **29 passed in 24.53s**, exit 0. Ruff, `git diff --check` and `sh -n agents/radix/install-passive-tools.sh` passed. These overlap earlier runs; no inflated unique-test total is claimed.
- Recovered-source image build: `docker build --pull=false --progress=plain -f agents/radix/Dockerfile -t radix-passive-proof:recovered agents` => exit 0, image `sha256:3ade8f2eb16f980abf0e499f508201c6d685abb2704b630fb9418c3b6fe7defe`. This image includes the recovered application code; no deployment occurred.
- Real recovered-image CLI proof: `docker run --rm --network none --memory 1g --cpus 1 --cap-drop ALL --security-opt no-new-privileges:true -e PYTHONPATH=/app -v /tmp/tervory-radix-passive-gate-20261028/tests/radix_passive/local_cli_smoke.py:/tmp/local-smoke.py:ro radix-passive-proof:recovered python /tmp/local-smoke.py` => exit 0; ZAP exit 0, 4 parsed findings; Nuclei exit 0, 1 request, 0 errors, 10 parsed findings. This is synthetic HTTP loopback with the test-only proxy override inside `--network none`, **not** the production HTTPS/TXT/proxy path. Separate tests cover that path's DNS and tenant authorization, pinned public-address tunnel, redirect/other-host/storage refusal and expired leases. No public DNS/site lookup or live scan occurred during tests.
- Recovered image imports and OpenAPI route schemas passed in `docker run --rm --network none --memory 256m --cpus 0.5 radix-passive-proof:recovered ...`; exact command/output is in [PROOF.txt](PROOF.txt). An initial helper assumed every FastAPI route had `.path`; it was corrected to inspect OpenAPI. No production code change was required.
- [PROOF.txt](PROOF.txt) contains exact commands, outputs and output digests, including the full recovered image build log, initial failing CLI diagnostic, initial dummy-auth regex rejection, and both inherited Zenas seal failures plus their fresh-main reproduction. **The broad seal suite is not green (72 pass, 2 fail). No hosted CI result is asserted.**
- The owned disposable `radix-passive-proof-pg` database was stopped/removed with `docker stop radix-passive-proof-pg` (exit 0). No production container, data or setting was changed.

#### What changed (reviewable file/line)

| File:line | Behavior |
| --- | --- |
| `agents/radix/passive_store.py:10` | Additive room-local proof/run tables; one globally running scan. |
| `agents/radix/passive_store.py:31`, `:42`, `:51` | Exact public domain/HTTPS root and immutable artifact validation. |
| `agents/radix/passive_store.py:61`, `:72`, `:85` | Per-tenant DNS challenge and pending scan; no default tenant or reused proof. |
| `agents/radix/passive_store.py:99` | Independent gateway administration reaps expired leases by their persisted tenant/id, rechecking expiry. |
| `agents/radix/passive_store.py:118`, `:137`, `:152` | Atomic findings/receipt completion; existing best-effort bus; latest exact assessment/freshness gate. |
| `agents/radix/passive_gateway.py:27`, `:35`, `:95` | Exact TXT proof, short-lived no-storage single-host tunnel and outage-tolerant maintenance. |
| `agents/radix/egress.py:133`, `:164`, `:178`, `:377` | Reuse public-address DNS pinning, CONNECT policy and limits; expire old tunnels; release listener before reuse. Existing fixed-host/R2 path remains separate. |
| `agents/radix/passive_tools.py:24`, `:42`, `:62`, `:72`, `:128` | Passive-only ZAP plan, one pinned Nuclei template, fixed proxy/rate limits, credential-free child environment and fail-closed complete reports. |
| `agents/radix/passive_routes.py:49`, `:76` | Authenticated issue/scan/gate/findings APIs; failures remain failed, never clean. |
| `tank/radix_passive_routes.py:21`, `tank/main.py:4205` | Single Tank corridor with room/Workspace authorization, tenant, region and product checks; one router registration, no model/worker/cache changes. |
| `agents/radix/install-passive-tools.sh:1`, `agents/radix/Dockerfile:52` | Verified official tool/template installation at build time; no runtime update/download. |
| `agents/radix/docker-compose.yml:27`, `:92`, `agents/radix/app.py:74` | Mount API; sealed scanner stays off internet; separate proof/egress peer; JVM scan memory cap requires 1 GiB container limit. |
| `tank/requirements-dev.txt:32` | DNS test pin matches Radix runtime. |
| `tests/test_radix_passive.py:71`, `:133`, `:155`, `:185`, `:257`, `:371` | Authorization, cross-tenant isolation, expiry/restart, findings/bus, gate denial and transient maintenance retry. |
| `tests/radix_passive/local_cli_smoke.py:1` | Real tools against a synthetic localhost page only, with external networking disabled. |

#### API contract agreed with Tisan

`POST /v1/radix/passive/scans` (up to 360 seconds) then `POST /v1/radix/passive/gate` (15 seconds), each with `{tenant_id,target:"https://exact-host/",artifact:"commit:<40hex>"}` (image `sha256:<64hex>` also supported). Tisan sends its existing room key internally plus `X-Tervory-Tenant`, `X-Tervory-Squad: tisan`, and `X-Tervory-Region` matching this server. Response HTTP 200 has top-level `allowed,scan_id,tenant_id,target,artifact,status,high,critical,completed_at`; scan response also has sanitized `findings`. No caller pass boolean is accepted. Workspace challenge issuance requires Radix enabled for that tenant. No new credential names or values.

Tisan must use its server-stored staging revision, check it remains the same across live-check/scan/gate, and refuse missing/error/stale/high/critical/mismatched results. A client-supplied artifact string alone does not prove what a site serves. Merge job 8 before job 11; absent APIs fail closed.

#### Pins and primary references

- ZAP **2.17.0** Linux archive SHA256 `efe799aaa3627db683b43f00c9c210aea0b75c00cc8f0a0f0434d12bb3ddde5a`, read from [official release metadata](https://github.com/zaproxy/zaproxy/releases/tag/v2.17.0). [Baseline behavior](https://www.zaproxy.org/docs/docker/baseline-scan/) and [automation environment](https://www.zaproxy.org/docs/desktop/addons/automation-framework/environment/); network option names checked against official `zap-extensions` source and real CLI execution.
- Nuclei **3.11.1** Linux amd64 archive SHA256 `ea63d4ae232808cd7c6bc00d0142428e231fab59dae01042246097d195835ab6`, from [official release metadata](https://github.com/projectdiscovery/nuclei/releases/tag/v3.11.1). [Official execution/template documentation](https://docs.projectdiscovery.io/opensource/nuclei/running). Installer fails closed on unsupported architectures.
- Only upstream `http/misconfiguration/http-missing-security-headers.yaml` at commit `e0a55a87832e85fe25635ab78e3a5bb4a3f61c0a`, SHA256 `7f45803f73ac6810b9b302df6be2c472a82d9164a7807328614efa83e6eac275`. GET root only; broad tags/directories, exploits, active templates, headless, fuzzing and OAST are excluded. Raw traffic, cookies and response evidence are discarded; stored findings retain tool/severity/rule/verified target only.

#### Remaining acceptance and handoff

No current concrete code finding is open from independent review; final proof/test commit head is being sent for exact-head review. No PR exists yet; **Claude must open it from this branch using this report**, then hosted checks and founder review remain. Founder acceptance is still pending a real owned-domain TXT proof and real passive findings in the founder's browser. No screenshot or full-green claim is fabricated. Zenas region clarification is unchanged: US/Boston and ZA/dedicated South Africa box; this job does not change Zenas or its compose files.

### 2026-10-28 16:48:45 PDT (UTC-07:00) / 2026-10-28 23:48:45 UTC — independent review and serialized final publication

- Independent reviewer verified exact published `8fcd1061289407b9d730b3d6da1eb137491a3cb9`, application equality to reviewed `ce44c65a`, added outage tests, command/image evidence and report. **No outstanding actionable code finding. Ready for Claude's draft PR handoff.** The two main Zenas seal failures and loopback-only CLI override remain explicit limitations, not waived failures or live acceptance.
- Final documentation check at `8fcd1061`: `/tmp/radix-passive-py312/bin/python -m pytest -q tests/test_secrets.py` => **2 passed in 8.66s**, exit 0; `git diff --check` passed. This checks the newly committed report/proof as well as source; no new test suppression or real secret was used.
- This final checkpoint changes only this append-only report; application/test code and evidence are unchanged. Its serialized commit/push and exact resulting head are sent to the reviewer separately. No PR exists yet; Claude opens it using this report. Hosted CI and founder real-domain TXT/browser findings remain pending, with no production change or live scan.
