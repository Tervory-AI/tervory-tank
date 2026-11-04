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
