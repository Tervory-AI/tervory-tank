# Tiger TG3: optional brain and sealed sandbox, disabled by default

Tiger can provision its own pinned Hermes image and isolated executor without
starting either in a normal deployment. Its three current extraction skills
remain code: `tiger.price_extract`, `tiger.price_structured`, and
`tiger.price_ocr`. **This gate adds no caller and makes no model call.**

The existing Rig and Base task services are specific to those rooms. Tiger uses
Rig's unchanged pinned Dockerfile and `agents/_brain`, with a shared health-only
standby entrypoint rather than starting Rig's task API. The installed Hermes
runtime is present, but there is deliberately no Tiger task endpoint or agent
loop. Future escalation requires its own implementation. No
`agent.tiger.think` policy is seeded: the route retains Tank's required policy
lookup (404 when absent). Its accounting test supplies a fake policy and fake
gateway; it does not authorize a paid route.

Branch `codex/tiger-brain` starts at main
`19ff60f91572783e978d95e252a0fed8c64b7a80` in
`/workspace/codex-tiger-w3b`. No main merge, PR creation, PR label or merge was
performed. Each finished file was committed and pushed separately; all pushes
succeeded. Gate 1 remains separate in PR #629, and Gate 2 awaits Figma approval.

## Changes by file and line

| File | Change |
| --- | --- |
| `ops/box-memory.sh:7` | Read total, used and available bytes; show each running container's usage and sum every container's limit, including stopped containers. Only `free -b`, formatted non-streaming Docker stats, Docker inspect and shell builtins run. No environment values are inspected. |
| `agents/_brain/standby.py:1` | Shared health-only Tiger entrypoint; no task API or model loop. |
| `agents/tiger/docker-compose.yml:29` | Separate `TIGER_BRAIN_ENABLED` flag defaults false on agent-tiger. |
| `agents/tiger/docker-compose.yml:51` | Brain profile, 2 GiB limit, Tiger corridor and private sandbox network, own data volume, Tank/Hermes/browser/executor URLs, Tiger room key and sandbox key; no provider key. Reuses `agents/rig/Dockerfile.brain` unchanged. |
| `agents/tiger/docker-compose.yml:84` | Sandbox profile, 512 MiB limit, internal network only, read-only root, tmpfs workspaces, all capabilities dropped, no new privileges, PID limit 64, no Tank key or volume. Reuses Base's sandbox Dockerfile unchanged. |
| `.env.example:254` | Names/default only for `TIGER_BRAIN_ENABLED` and `SANDBOX_KEY_TIGER`. Use existing coolify-ops `room-setup`, room `tiger`, extra name `SANDBOX_KEY_TIGER`; no workflow invocation or credential creation was performed. |
| `tank/agent_skills.py:34` | Tiger joins the existing room allowlist and owning-key check. Chat, skills export, paid-work pause, refusal checks, tenant/task ledger and receipts follow the existing implementation. Candidate submission remains Base-only. |
| `ops/seal-check.sh:50` | Tiger brain corridor allowlist, exact brain/sandbox networks at 193/197, and required optional pair at 283. Only Tiger-specific lines change. |
| `agents/base/check_brain_isolation.py:17` | Derive validated sandbox host from the supplied container's service label; derive Base/Tiger corridor and database role from the room. Base keeps its existing probe/result. Reject foreign sandbox, provider keys and Tank key in executor. |
| `docs/cursor/ROOMS.md:169` | Provisioning, disabled defaults, pending dated Boston capacity evidence and postdeploy checks. No measured numbers have been invented. |
| `tests/test_room_seal.py:103` | Tiger sandbox joins the sealed-services expectation. |
| `tests/test_agent1_brain_route.py:96` | Unsupported-room fixture uses Radix now that Tiger is allowed. |
| `tests/test_agent1_skills.py:80` | Assert Tiger candidate submission is refused instead of refusing its newly supported skills export. |
| `tests/box_memory/test_box_memory.py:53` | Eight offline tests with fake free/Docker commands, exact allowed invocations and error propagation. |
| `tests/box_memory/PR.md:1` | Measurement prerequisite handoff, updated after founder authorized setup while disabled. |
| `tests/tiger_brain/PR.md:1` | Gate handoff, validation evidence, deployment scope and pending founder/ops checks. |
| `tests/tiger_brain/test_tg3.py:35` | 26 tests: real Compose profile selection, keys/limits/networks, standby, Tiger-only room authentication, mocked ledger/receipts/pause/refusal, Base/Tiger isolation fixtures and failing seal cases. |

No existing Tiger watch, read, watchlist, browser or page implementation changes.
No provider, dependency version, database schema or shared Dockerfile changes.

## Validation

- Broad related selection: 1,669 collected. The Docker exec client ended with
  status 143 before the terminal pytest summary; the container stayed running
  and `OOMKilled=false`. Its retained progress contains 1,591 pass markers,
  16 skips and one Rig browser failure. **This is not a clean full-suite pass.**
  See [original partial output](evidence/related-suite.txt) and the
  [exact case audit](evidence/related-cases.txt).
- The remaining 61 cases and the last boundary case were run again with output
  written inside the container: **62 passed in 92.35s**.
  See [completion](evidence/related-completion.txt).
- Rig's browser case was reproduced without the optional browser-path setting:
  `Chromium distribution 'chrome' is not found at /opt/google/chrome/chrome`.
  Setting its existing `READ1_CHROMIUM_EXECUTABLE` to bundled Chromium gives
  **1 passed in 7.19s**, without a code change. See
  [environment error](evidence/rig-browser-environment-error.txt) and
  [passing rerun](evidence/rig-browser-rerun.txt).
- Additional Tiger extraction/alert/price-history tests: **95 passed, 1 skipped
  in 85.30s**. The skip is the existing human-labelled 100-page gold set.
  See [additional Tiger tests](evidence/tiger-extra.txt).
- Isolated G5: **46 passed in 113.20s**. See [G5](evidence/tiger-g5.txt).
- Tiger tenant-event history: **2 passed in 28.67s**, using a real disposable
  loopback Tank/Postgres/Redis path. See [history](evidence/tenant-history.txt).
- Offline package/eval checks: **2 passed in 109.77s**.
  See [skills](evidence/skills-offline.txt).
- Ruff and secrets: **pass; 2 secret tests passed**.
  See [Ruff](evidence/ruff.txt) and [secret tests](evidence/secrets.txt).
- The new TG3 tests also passed standalone: **26 passed in 32.31s**.
  The memory script's standalone stdlib run was **8 passed in 0.421s**;
  see `tests/box_memory/PR.md`. These repeat checks are not additional unique
  coverage counts.

The 16 broad-run skips are enumerated in the audit: 14 opt-in cloud/container,
Hermes, Forge-image or public-render/pilot checks, and two checks requiring the
uncommitted real-supplier-cost export. These are existing opt-in and fixture
conditions. Hosted CI remains responsible for its configured
container/Forge jobs; no real supplier data was requested.

The initial setup checks above used implementation and test source at
`03df12cd`; the CI follow-up below updates the room guard and regression tests.
Local focused checks are not a substitute for hosted final-head CI.

The real Compose CLI selects exactly three services without profiles:
`agent-tiger`, `tiger-browser`, `tiger-browser-gateway`. With `--profile brain`
it selects those three plus `tiger-brain` and `tiger-sandbox`.
See [profile selection](evidence/profiles.txt). This is actual Compose model
selection, not a claim that Boston has been deployed.

Both Docker images built from tracked-only Git archives. Rig's existing build
fetches and verifies Hermes commit
`d923a5eb487a17c0a68801bba9ef0f56c81040a8` (version 0.22.2), keeps its MIT license
and removes bundled skills. See [brain build](evidence/brain-build.txt) and
[sandbox build](evidence/sandbox-build.txt).

Disposable runtime containers proved the Hermes install/license, Tiger health,
404 for `/tasks`, unauthenticated sandbox refusal and authenticated offline WASI
execution with placeholder credentials. The executed Python scratch program
could not create a socket. See [runtime](evidence/runtime.txt). These proof
containers and their private network were removed; no live room was touched.

## Reproduction

The regression suites ran with Python 3.12 in a disposable test container, the
pinned Tank dev requirements and Rig Forge's hash-pinned requirements. Node/npm,
Workspace dev packages, Chromium and Compose were available in that container.
Database tests used disposable loopback PostgreSQL 16; bus tests used a separate
disposable loopback Redis. No production DSN, user credentials or provider keys
were supplied. Socket guards restrict tests to loopback/Unix sockets.

```sh
python3 -m unittest discover -s tests/box_memory -v
bash -n ops/box-memory.sh
ruff check tank tests agents/_brain/standby.py agents/base/check_brain_isolation.py \
  --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
python -m pytest tests/test_secrets.py -q --disable-warnings

# Supply the loopback URL of a dedicated disposable PostgreSQL instance.
export POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:TEST_PORT/postgres
export TIGER_MAIL_TEST_DATABASE_URL=$POOL_SCHEMA_DATABASE_URL
export BASE_TEST_DATABASE_URL=$POOL_SCHEMA_DATABASE_URL
export RIG_TEST_DATABASE_URL=$POOL_SCHEMA_DATABASE_URL
export MEMORY_TEST_DATABASE_URL=$POOL_SCHEMA_DATABASE_URL
export RLS_TEST_DATABASE_URL=$POOL_SCHEMA_DATABASE_URL
# This container has bundled Chromium rather than system Google Chrome.
export READ1_CHROMIUM_EXECUTABLE=/root/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome
python -m pytest tests/test_tiger*.py tests/test_tg2_tiger_watchlist.py \
  tests/test_base*.py tests/test_rig*.py tests/test_agent1*.py \
  tests/test_room_seal.py tests/tiger_brain/ tests/box_memory/ \
  -q --tb=short -rs --disable-warnings --timeout=300 \
  --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1
python -m pytest tests/tiger_playbooks tests/tiger_price_read \
  tests/tiger_alert_page tests/tiger_before_deploy tests/rig_tiger_prices \
  -q --tb=short -rs --disable-warnings --timeout=300 \
  --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1
# Run separately because bare sibling test-module names collide in one collection.
python -m pytest tests/tiger_g5 -q --tb=short -rs --disable-warnings \
  --timeout=300 --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1
export TENANT_BUS_REDIS_URL=redis://127.0.0.1:TEST_REDIS_PORT/0
python -m pytest tests/tenant_bus/test_tiger_history.py \
  -q --tb=short -rs --disable-warnings --timeout=300 \
  --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1
python -m pytest tests/test_skills_offline.py \
  -q --tb=short -rs --disable-warnings --timeout=300 \
  --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1

git archive HEAD | docker build -f agents/rig/Dockerfile.brain \
  -t codex-tiger-brain-proof:tg3 -
git archive HEAD | docker build -f agents/base/Dockerfile.sandbox \
  -t codex-tiger-sandbox-proof:tg3 -
git diff --check
git diff origin/main --check
```

## Deployment and evidence still outstanding

**This is deployment configuration: merging redeploys the Tiger room.**
The existing deploy-changed mapping also selects Base because its checker is
under `agents/base/`, and main plus the configured ZA stack because Tank changes.
No deploy was triggered here. Rig's configuration and image source are unchanged.

The founder authorized setup while disabled after reporting cleaned memory.
That report is not dated output from `ops/box-memory.sh`. As recorded in ROOMS,
Boston total/used/available bytes, per-container usage and aggregate limits are
still pending. The founder's ops thread must paste the dated output here and
into `docs/cursor/ROOMS.md`; retain both disabled defaults until it shows capacity
for the additional 2 GiB and 512 MiB limits.

After the authorized normal deploy, require host `bash ops/seal-check.sh` output
showing agent-tiger sealed and no Tiger brain/sandbox running. Founder /chats
acceptance for watch/read and TG1 list/pause/resume/remove/bulk remains a live
check, including Tiger-page observations. TG1 is not merged into this branch.

Hosted final-head Tank/Workspace/security CI and the Boston/browser evidence are
not claimed. Claude owns PR creation, labels and merge. This handoff does not
authorize enabling a brain or adding an escalation caller.

## PR #638 CI follow-up

- `tests/tiger_brain/test_tg3.py:61`: absence check covers the Tiger agent-route
  prefix; the health fixture uses `placeholder.invalid`, and the in-process
  chat fixture derives its URL from FastAPI's registered route. The one-door
  scanner and its allowlist are unchanged.
- `tank/agent_skills.py:54`: owning-key validation first uses `room_text`, so
  injected, unknown and malformed room values consistently get HTTP 403.
- `tests/test_ledger_sql_param.py:20`: replace the obsolete hostile `tiger`
  fixture with an injected Tiger value and unknown/case-variant/malformed rooms.
  Base, Rig and Tiger each exercise valid parameterized ledger, transcript,
  receipt and skills reads. Hostile values must fail before even acquiring a
  database connection.

Validation: **86 passed, 4 skipped in 43.64s**. The four skips require a
disposable Postgres for existing Rig box integration cases; the new guard,
Tiger owning-key/accounting checks and both reported CI regressions pass.
Ruff E9/F and whitespace checks pass. Raw output:
[CI follow-up](evidence/ci638-fix.txt).

```sh
python -m pytest tests/test_tank_one_door.py tests/test_ledger_sql_param.py \
  tests/tiger_brain/test_tg3.py tests/test_agent1_brain_route.py \
  tests/test_rig_box_tank.py -q --tb=short -rs --disable-warnings --timeout=300 \
  --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,::1
```
