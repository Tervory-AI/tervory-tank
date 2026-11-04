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

Hermes previously had no Trigger corridor or key. Its existing service now joins
only the Trigger corridor and accepts `TANK_KEY_TRIGGER`, through the existing
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
