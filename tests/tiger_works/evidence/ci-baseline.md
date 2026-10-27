# CI failure comparison

## Fourth review: head 61606ab

Reviewed head `61606abc1378d2d390cf95eb7335f5fff67beeb0` has a completed
[tank CI job](https://github.com/zenascapetown-code/tervory-tank/actions/runs/40422967768/job/121921702915)
that **failed: 9 failed, 3,552 passed, 26 skipped, 53 warnings, 437 subtests passed
in 911.69s**. The PR workflow tests a merge with main.

Exact main `417eaad7436da741d0f3eecce654bd09dc0470d8` has the same nine failing tests
and causes in its completed
[tank CI job](https://github.com/zenascapetown-code/tervory-tank/actions/runs/40392858977/job/121818418242):
**9 failed, 3,477 passed, 26 skipped, 53 warnings, 437 subtests passed in 798.11s**.
Both complete job logs were downloaded and compared. This is evidence from the
existing CI runs; neither workflow was retried or manually dispatched.

| Failing test | Cause on both CI runs |
| --- | --- |
| tests/test_shell_nav.py:23 — `test_pages_do_not_scroll_sideways_and_squad_does_not_grow_the_sidebar` | The Node subprocess times out loading `/fixtures/actual-1440.html` at `tests/shell_browser.ts:263`. |
| tests/test_rig_postgres.py:92 — `test_rig_startup_loads_catalogues_on_postgres` | The date assertion at line 155 expects `2026-03-01`; the committed Archon catalogue contains `2026-10-18`. |
| tests/test_room_seal.py:86 — `test_no_room_service_would_leak_when_coolify_deploys_it[agents/ghost/docker-compose.enforce.yml]` | The Ghost enforce compose file introduced on main lacks the raw-compose marker; the check reports `enforce would join non-internal <coolify app network>`. |
| tests/test_room_seal.py:242 — `test_seal_check_reports_sealed_rooms` | Main adds an extra `autumbra: no Watch/Enforce rooms running (ok until dogfood; pin EXPECTED_SEALED after first clean run)` output line; the fixture expects the previous exact lines. |
| tests/test_room_seal.py:255 — `test_seal_check_names_each_leaking_container_and_network` | Main adds an extra `autumbra: no Watch/Enforce rooms running (ok until dogfood; pin EXPECTED_SEALED after first clean run)` output line; the fixture expects the previous exact lines. |
| tests/test_room_seal.py:275 — `test_seal_check_finds_raw_compose_rooms_by_label_not_container_name` | Main adds an extra `autumbra: no Watch/Enforce rooms running (ok until dogfood; pin EXPECTED_SEALED after first clean run)` output line; the fixture expects the previous exact lines. |
| tests/test_room_seal.py:310 — `test_seal_check_reports_leaks_in_raw_compose_rooms` | Main adds an extra `autumbra: no Watch/Enforce rooms running (ok until dogfood; pin EXPECTED_SEALED after first clean run)` output line; the fixture expects the previous exact lines. |
| tests/test_room_seal.py:323 — `test_seal_check_fails_when_an_expected_room_is_missing` | Main adds an extra `autumbra: no Watch/Enforce rooms running (ok until dogfood; pin EXPECTED_SEALED after first clean run)` output line; the fixture expects the previous exact lines. |
| tests/test_room_seal.py:336 — `test_seal_check_never_passes_when_only_the_hub_is_running` | Main adds an extra `autumbra: no Watch/Enforce rooms running (ok until dogfood; pin EXPECTED_SEALED after first clean run)` output line; the fixture expects the previous exact lines. |

The seven room-seal failures reach PR CI through main's merge-ref content.
This branch does not change the room-seal tests, `ops/seal-check.sh` or the Ghost
compose file. The reviewed branch's native checkout passes `test_room_seal.py`;
the independent fourth review also confirmed that result. This revision's local
run has **68 room-seal tests passed** on the branch; exact main has **7 failed,
62 passed**, with the same seven failures as CI. The local comparison
uses an unmodified `git archive 417eaad` checkout and the same Python environment:

```sh
PYTHONPATH=tank python -m pytest -q tests/test_room_seal.py
```

The sidebar and Rig date failures were also reproduced locally on the earlier
main `65067a43a0d27d54b48633bf6db4f3fc211ec05f`. Their corresponding checks and
implementation files remain outside this change.

## Previously reviewed head e1601bb

The [tank CI job for e1601bb](https://github.com/zenascapetown-code/tervory-tank/actions/runs/40381092771/job/121777279885)
failed with **2 failed, 3,477 passed, 20 skipped, 437 subtests passed in 867.39s**.
Only the sidebar fixture load and Rig catalogue date tests failed on that head;
its completed log was downloaded. The room-seal failures above belong to the
later merge-ref run for `61606ab`. Neither savings nor Rig search speed failed
in either of these two reviewed runs.

## Founder must decide

- `client_connection` remains unchanged. A genuine client-network/session path
  after a block is outside this brief.
- Older user agents remain unchanged outside this lane: `tank/main.py:670` and
  `workspace/app/api/base/route.ts:129` identify as `TervoryBase/0.1`; root
  `tiger/app.py:36,81` appends `TervoryTiger/0.1` and rewrites the browser's
  HeadlessChrome identity. The shared browser and the agent under `agents/tiger`
  use `Tervory/1.0 (+https://tervory.com)`. Alignment of the older clients belongs
  to their owning threads.
- Deleting a watch removes only the watch. Existing observations and alerts are
  retained; alerts for removed URLs can remain visible under the hostname. The
  founder must decide retention and deletion behavior. This revision does not
  change stored data or deletion semantics.
