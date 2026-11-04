# Remaining squad standby brains

Branch `codex/room-brains`, based on main `de113044`. One room per pushed gate.
No PR is created by this thread. Runtime configuration redeploys the named room;
Tank changes redeploy the main stack and its configured ZA counterpart. The shared
entrypoint exposes health only. No model caller is added: future model work must
use Tank, its paid-work pause, model refusal and durable tenant ledger receipts.
Base-only candidate submission is unchanged. No approved skill or paid route changes.

## Gate 1 — Market Lab

Market Lab gets its own optional brain, WASI sandbox, browser and browser gateway.
Every new service is behind `brain`; `MARKET_LAB_BRAIN_ENABLED` defaults to false.
They reuse the pinned Hermes and existing browser/sandbox builds. Roots are
read-only, capabilities dropped, privilege escalation disabled, process/memory/CPU
limits set, no socket/host mount/port and no provider key. The brain mounts only
its new data volume. The browser gets its own new browser volume and no Tank key;
the gateway holds only Market Lab's room key. The sandbox has tmpfs work and no
persistent volume or Tank key. Existing volume entries/mounts are snapshotted from
main and tested unchanged. Vault/login access is not enabled for these new browsers.

Tank's fixed room map accepts only the owning Market Lab key; hostile room values
fail before any SQL. Existing accounting and scope checks are reused. Seal checks
require the exact owning corridor and internal private networks; any added network,
missing attachment or partial optional group fails. Isolation fixtures reject foreign
executors, shared data, provider/control-plane settings and extra tool-network peers.

Capacity numbers and dated raw output are in `docs/cursor/ROOMS.md` and
`evidence/boston-memory.txt`. All new services remain off pending founder enablement.
The normal deploy must keep them absent. Enable Raw Compose Deployment before
using these sealed services, preserving the current project identity/room volumes.
No live deployment, production data mutation or volume migration is performed here.

Validation and gate heads are recorded as each room completes. Host seal checks
and actual founder enablement remain post-deployment acceptance.

Gate 1 validation: 276 collected cases accounted for: 274 passed initially; the
two failures (a fixture route-name typo and the raw-mode check's existing-volume
assumption) were corrected, with all three focused rechecks passing. These cover
real Compose profile selection, seal topology, SQL binding, Base routes, Tiger
and both Zenas regions. Runtime smoke checks used cached pinned builds with this
checkout's adapter: health-only standby and offline WASI scratch execution pass.
No full room deploy or new image build is claimed. The original and correction
logs are retained. One-door/secrets and exact lint results accompany each push.

File/line inventory for gate 1:

- `agents/market_lab/docker-compose.yml:1,17,55,110,142,178,216`: raw marker,
  disabled flag, independent brain/sandbox/browser/gateway and new volumes only.
- `agents/_brain/standby.py:1,13` and `agents/_brain/browser.py:627`: fixed room
  names for health and public browsing; no task caller or vault route added.
- `agents/base/check_brain_isolation.py:46`: own-tool topology and key/volume guards.
- `tank/agent_skills.py:35`: fixed owning-room access, existing accounting reused.
- `ops/seal-check.sh:52,201,230,309`: corridor, exact attachments and complete group.
- `.env.example:550`: flag and executor key names, no credentials.
- `docs/cursor/ROOMS.md:259`: dated Boston capacity and enable/deploy constraints.
- `tests/room_brains/test_rooms.py:1`, `rooms.json:1`, `snapshots/market_lab.json:1`:
  offline positive/negative profiles, seals, keys, receipts, data and isolation.
- `tests/test_ledger_sql_param.py:21,55,87,126`: every enabled room and hostile input.
- `tests/test_room_seal.py:157`: exact historical-volume exception, per main snapshot.
- `tests/room_brains/evidence/*`: dated memory, runtime, original and corrected tests.

## Gate 2 — Radix

Radix gets independent optional brain, sandbox, browser and gateway using the same
builds and hardening. `RADIX_BRAIN_ENABLED` defaults false. Existing data volume
`agent_radix_data`, including its external live name, is byte-for-byte unchanged.
No existing egress policy or attachment is widened: the browser remains subject
to Radix's internal corridor boundary. No model caller is added. The Tank key,
executor key, two new data volumes and private networks are Radix's own.

The isolation checker recognizes Radix's existing proxy-link attachment and its
existing passive-egress neighbour; its optional tools keep exact isolated networks.
Tests now reject the Base key on the newly enabled Radix route with 401, and still
reject hostile Radix input before SQL. Enforce remains outside the room map.

Files: `agents/radix/docker-compose.yml:35,129,184,216,252` (flag and four optional
services), `agents/_brain/standby.py:12`, `agents/_brain/browser.py:627`,
`agents/base/check_brain_isolation.py:46`, `tank/agent_skills.py:35`,
`ops/seal-check.sh` (Radix corridor/attachments/group), `.env.example` (two names),
`docs/cursor/ROOMS.md:259`, `tests/room_brains/rooms.json:1` and
`snapshots/radix.json:1`, `tests/room_brains/test_rooms.py:188` (external internal
corridors recognized from the same seal metadata), `tests/test_ledger_sql_param.py:21`
and `tests/test_agent1_brain_route.py:96` (new owning-key boundary).

Radix validation: 33 focused cases and 85 shared brain/isolation/SQL cases passed.
The final fixture uses the actual internal flag for external corridors; no network
policy was changed to satisfy it. Exact CI lint and the staged secret scan pass.

## Gate 3 — Tisan

Tisan receives independent optional brain, sandbox, browser and gateway. Its brain
has only its owning Tank/executor keys; none of the room's Figma, Coolify, R2 or DB
settings are copied. `TISAN_BRAIN_ENABLED` defaults false; all four new services
require profile `brain`. Existing Figma proxy attachments and data volume/mounts
are unchanged. Raw Compose is required by the new sealed tools, with the existing
project identity retained. No new model caller or paid route is introduced.

Files: `agents/tisan/docker-compose.yml:1,18,76,131,163,199` (marker, flag and four
optional services), `agents/tisan/README.md:63` (deployment requirement),
`agents/_brain/standby.py:12`, `agents/_brain/browser.py:627`,
`agents/base/check_brain_isolation.py:46`, `tank/agent_skills.py:35`,
`ops/seal-check.sh:56,213,246,331`, `.env.example:562`,
`docs/cursor/ROOMS.md:259`, `tests/room_brains/rooms.json:1`,
`snapshots/tisan.json:1`, and `test_rooms.py:188` (own historical Tisan fixture).
`tests/test_tisan_figma.py:379` and `tests/test_c10_rooms.py:77,115` now check the
new networks and default-service set while retaining the Figma/Radix proxy guards.
`tests/test_ledger_sql_param.py:21` covers hostile Tisan input before SQL.

Tisan's 33 focused cases pass. Related Figma, room topology, owning-key, ledger and
Base route regressions are recorded alongside exact lint and staged secret scans.

Tisan related result: 97 cases passed, including unchanged Figma proxy restrictions
and real loopback HTTPS response tests.

## Gate 4 — Trigger

Trigger gets its own optional brain, WASI sandbox, browser and gateway. All use
profile `brain`; `TRIGGER_BRAIN_ENABLED` defaults false. Existing LanguageTool
configuration, checker network and bind mount remain unchanged. The brain receives
only Trigger's room/executor keys and its own new data volume; the browser has a
separate new volume and no Tank key. No model caller is added.

Hermes previously had no Trigger corridor or key. Its existing service now also joins
the Trigger corridor and accepts `TANK_KEY_TRIGGER`, through the existing
per-room authentication and memory scope. The main-stack configuration therefore
redeploys along with Trigger. No main-stack volume or other service attachment is
changed. The isolated checker still joins only `checkers`.

Files: `agents/trigger/docker-compose.yml:13,54,109,141,177`,
`agents/trigger/README.md:7`, `docker-compose.yml:88,103`,
`agents/_brain/standby.py:12`, `agents/_brain/browser.py:627`,
`agents/base/check_brain_isolation.py:46`, `tank/agent_skills.py:35`,
`ops/seal-check.sh:58,219,254,342`, `.env.example:567`,
`docs/cursor/ROOMS.md:259`, `tests/room_brains/rooms.json:1`,
`snapshots/trigger.json:1`, `test_rooms.py:66` (Hermes corridor/key),
`tests/test_ledger_sql_param.py:21`, `tests/test_hermes_memory.py:429` and
`tests/trigger_first_build/test_trigger.py:256` (permitted memory neighbour).

Focused profile, volume, seal, accounting and isolation cases pass; related Trigger,
Hermes and SQL guard results are recorded in evidence. Existing optional integration
requirements are stated with their skips rather than claimed as executed.

Trigger validation: 33 focused and 87 related cases passed. Two existing optional
integration tests require isolated Postgres / a running LanguageTool pair and are
not claimed as run. The staged secret scan passed.

## Gate 5 — Autumbra Watch (Ghost)

Watch gets `ghost-brain` and `ghost-sandbox` behind profile `brain`, with
`GHOST_BRAIN_ENABLED` default false. It retains its existing own browser. Its new
brain mounts only `ghost_brain_data`; the room, browser and threat-queue volume
entries and mounts are byte-for-byte unchanged. Sandbox has only its own key,
read-only root and tmpfs work. The brain has no Coolify, Enforce, edge, SMTP, Undo,
DB or R2 settings. Its existing room still owns its existing tools/settings.

Hermes now accepts Watch's own key on Watch's existing corridor, with its existing
per-room memory scope. No Enforce attachment or credential is introduced. Enforce's
compose is unchanged from main; a regression keeps its internal air gap and
excludes any brain/sandbox service or setting. Its
room name is still rejected before SQL. No caller/model escalation is added.
The isolation checker accepts Watch's four-container topology and verifies its
brain/sandbox separately from the existing browser. Existing Watch tests continue
to require exactly its original default services' corridor and key restrictions.

Files: `agents/ghost/docker-compose.yml:1,15,73,126,163`,
`agents/_brain/standby.py:12`, `agents/base/check_brain_isolation.py:46`,
`tank/agent_skills.py:35`, `docker-compose.yml:89,105`,
`ops/seal-check.sh:60,224,259,350`, `.env.example:572`,
`docs/cursor/ROOMS.md:259`, `tests/room_brains/rooms.json:1`,
`snapshots/ghost.json:1`, and `test_rooms.py:85,238,259,305` (existing browser-volume
preservation, optional group seals, four-container fixture and Enforce exclusion).
`tests/test_ghost_routes.py:164`, `tests/test_ghost_inventory.py:198`,
`tests/test_hermes_memory.py:429` and `tests/test_ledger_sql_param.py:21` retain
existing service restrictions and cover the newly authorized memory neighbour/key.

## Capacity and deployment acceptance

The five optional profiles add planned caps of 21 GiB and 10.5 CPUs together,
including four new private browsers/gateways. That exceeds the dated available
memory snapshot. These are limits, not measured usage; no capacity approval is
inferred, no profile was enabled and no larger box is requested. Founder enablement
requires a fresh read-only host measurement. All flags remain false by default.

For newly raw compose resources, keep the current project identity and existing
volumes when enabling Raw Compose Deployment. Every named room redeploys on merge;
Base's isolation-checker path also selects Base, and Tank/main compose changes
redeploy the main stack and configured ZA counterpart. No deployment or existing
volume operation was performed. After authorized deployment, check the host seal;
a default deploy must run none of the new services. After founder profile approval,
run each room's isolation gate with its own container names (Watch: room, brain,
sandbox, browser; other new rooms also supply gateway). Raw Compose is required.

The live host seal checks and enabled-profile deployment acceptance remain pending.
No hosted CI result is claimed before Claude opens the PR.

## Final offline validation

The full cross-room run collected 594 cases: 590 passed, two existing optional
Trigger integration cases skipped, and two test expectations failed initially.
The original log is retained. The Watch volume comparison stripped its existing
browser volume as if it were new; the comparison now removes only Watch's new
brain volume. The normal-mode leak test listed only agent-radix; it now requires
all five sealed Radix services to be detected. Both failed cases and their seven
related cases then passed (9 focused rechecks). All 592 runnable cases are thus
accounted for without removing or skipping any new requirement.

In addition, Watch's complete focused group passed 23 cases, a 103-case fast
cross-room group passed, all 29 static compose seals passed, and all 29 one-door
and secret guards passed. The full run covers the new rooms, Base routes and
isolation, Tiger's brain, both Zenas regions, hostile SQL values, tenant ledgers,
Hermes memory and the existing Watch, Trigger, Tisan/Figma and room topology tests.
Existing integration skips require disposable Postgres / a running LanguageTool
pair; those dependencies were not provisioned. No live model/provider was used.

Evidence: `squad-initial.txt`, `squad-corrections.txt`, `ghost-tests.txt`,
`squad-fast.txt`, `static-seals.txt`, `ghost-guards.txt` and the exact lint output
under `evidence/`. Tests ran in a task-only network-disabled container with socket
access restricted to unix/loopback; helper containers had `--rm`, the
`tervory.test=1` label and `codex-room-brains` names. Temporary files stayed in this
checkout. Runtime proof used the cached shared builds with this checkout's adapter;
no fresh network-dependent image build or complete room deploy is claimed.

`tests/test_room_seal.py:101` now includes all optional Radix services in the
negative normal-mode test. This checks the required Raw Compose protection rather
than excluding the new services from the seal regression.

Prior pushed gate heads:

- Market Lab: `18621dbd9a9fa5892aa77539d569aba31c938ff4`
- Radix: `179f45bb6369c059bc7b99462f273f83abe9e7cd`
- Tisan: `833c11cca2166e09d57d141aff476779efc32be6`
- Trigger: `149d8ed60b5701f4ed6cab3aa3aa78a450180977`
- Watch: current branch head reported with the final push.

The final semantic Enforce boundary check also passes; Enforce remains on exactly
its internal network with no brain/sandbox service or setting, and its compose
has no diff from main. `evidence/enforce-boundary.txt` records the focused check.
