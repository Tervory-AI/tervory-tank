# Paid-step change index

File and line references for the current branch. Gate heads and verification status are reported separately.

| File | Changed lines | Change |
| --- | --- | --- |
| `agents/_brain/paid_approval.py` | [1](../../agents/_brain/paid_approval.py#L1) | Wait on the existing SDK transport; poll only owned approval state and never grant it. |
| `agents/_brain/reader.py` | [142](../../agents/_brain/reader.py#L142) | Bound email matching on long tool results; preserve existing redaction behavior. |
| `agents/_brain/runner.py` | [71](../../agents/_brain/runner.py#L71) | Install the Tank approval wait adapter in the existing isolated brain process. |
| `agents/_chassis/chassis/paid_steps.py` | [1](../../agents/_chassis/chassis/paid_steps.py#L1) | Resume room POSTs after administrator approval, preserving the root run handle. |
| `agents/_chassis/chassis/tank.py` | [116](../../agents/_chassis/chassis/tank.py#L116) | Use the shared approval-aware POST adapter. |
| `agents/base/pipeline.py` | [141](../../agents/base/pipeline.py#L141) | Limit repository skill fallback to the actual Base source layout; copied flat apps remain empty. |
| `agents/base/room.py` | [207](../../agents/base/room.py#L207) | Use that adapter for direct approved skill calls. |
| `agents/base/sources/context_dev.py` | [7](../../agents/base/sources/context_dev.py#L7), [111](../../agents/base/sources/context_dev.py#L111), [131](../../agents/base/sources/context_dev.py#L131), [142](../../agents/base/sources/context_dev.py#L142) | Admit paid credit lookups before reservation or vendor HTTP. |
| `agents/base/sources/vendor_ledger.py` | [24](../../agents/base/sources/vendor_ledger.py#L24), [56](../../agents/base/sources/vendor_ledger.py#L56), [62](../../agents/base/sources/vendor_ledger.py#L62), [79](../../agents/base/sources/vendor_ledger.py#L79), [96](../../agents/base/sources/vendor_ledger.py#L96) | Persist and forward credit approval identifiers. |
| `agents/rig/forge/service.py` | [83](../../agents/rig/forge/service.py#L83) | Wait for a GPU approval without giving the forge a Tank credential. |
| `agents/rig/rig_brain/forge.py` | [30](../../agents/rig/rig_brain/forge.py#L30), [135](../../agents/rig/rig_brain/forge.py#L135), [144](../../agents/rig/rig_brain/forge.py#L144), [156](../../agents/rig/rig_brain/forge.py#L156) | Relay read-only approval status through the existing forge corridor. |
| `agents/rig/rig_brain/runner.py` | [27](../../agents/rig/rig_brain/runner.py#L27) | Install the same SDK approval wait adapter. |
| `docs/acceptance/autumbra.md` | [189](../../docs/acceptance/autumbra.md#L189) | Paid-rung founder testing-sheet row. |
| `docs/acceptance/base.md` | [1](../../docs/acceptance/base.md#L1) | Paid-rung founder testing-sheet row. |
| `docs/acceptance/market_lab.md` | [103](../../docs/acceptance/market_lab.md#L103) | Paid-rung founder testing-sheet row. |
| `docs/acceptance/radix.md` | [1](../../docs/acceptance/radix.md#L1) | Paid-rung founder testing-sheet row. |
| `docs/acceptance/rig.md` | [205](../../docs/acceptance/rig.md#L205) | Paid-rung founder testing-sheet row. |
| `docs/acceptance/tank.md` | [1](../../docs/acceptance/tank.md#L1) | Paid-rung founder testing-sheet row. |
| `docs/acceptance/tiger.md` | [1](../../docs/acceptance/tiger.md#L1) | Paid-rung founder testing-sheet row. |
| `docs/acceptance/tisan.md` | [151](../../docs/acceptance/tisan.md#L151) | Paid-rung founder testing-sheet row. |
| `docs/acceptance/trigger.md` | [1](../../docs/acceptance/trigger.md#L1) | Paid-rung founder testing-sheet row. |
| `docs/acceptance/zenas.md` | [1](../../docs/acceptance/zenas.md#L1) | Paid-rung founder testing-sheet row. |
| `docs/ops/FOUNDER-SETTINGS.md` | [58](../../docs/ops/FOUNDER-SETTINGS.md#L58) | Register per-tenant Ask/Auto setting and existing platform master stop. |
| `docs/paid-steps/CHANGEINDEX.md` | [1](../../docs/paid-steps/CHANGEINDEX.md#L1) | File and line index for review. |
| `docs/paid-steps/FRAMES.md` | [1](../../docs/paid-steps/FRAMES.md#L1) | Frame IDs, implementation details, exact logo checksum and visual evidence. |
| `docs/paid-steps/PR.md` | [1](../../docs/paid-steps/PR.md#L1) | Problem, behavior, registry audit, deployment impact and validation evidence. |
| `docs/paid-steps/evidence/settings-1440.png` | [1](../../docs/paid-steps/evidence/settings-1440.png#L1) | Actual desktop settings fixture screenshot, visually checked. |
| `docs/paid-steps/evidence/settings-375.png` | [1](../../docs/paid-steps/evidence/settings-375.png#L1) | Actual mobile settings fixture screenshot, visually checked. |
| `tank/agent_skills.py` | [23](../../tank/agent_skills.py#L23), [25](../../tank/agent_skills.py#L25), [176](../../tank/agent_skills.py#L176), [197](../../tank/agent_skills.py#L197), [238](../../tank/agent_skills.py#L238), [313](../../tank/agent_skills.py#L313), [329](../../tank/agent_skills.py#L329) | Gate the existing agent model route and persist provenance in both ledger and SDK receipt. |
| `tank/base_product.py` | [78](../../tank/base_product.py#L78), [427](../../tank/base_product.py#L427), [441](../../tank/base_product.py#L441) | Validate Context.dev approval and link it to the vendor receipt, including idempotent retries. |
| `tank/bench.py` | [210](../../tank/bench.py#L210), [265](../../tank/bench.py#L265) | Gate benchmarks before calls and record their authorization; persist waiting work. |
| `tank/command.py` | [128](../../tank/command.py#L128), [173](../../tank/command.py#L173), [255](../../tank/command.py#L255), [269](../../tank/command.py#L269), [413](../../tank/command.py#L413), [585](../../tank/command.py#L585), [634](../../tank/command.py#L634), [769](../../tank/command.py#L769), [776](../../tank/command.py#L776), [1908](../../tank/command.py#L1908), [1921](../../tank/command.py#L1921), [2141](../../tank/command.py#L2141) | Expose paid confirmations to administrators, pause/resume turns, and present receipt provenance. |
| `tank/controls.py` | [38](../../tank/controls.py#L38), [70](../../tank/controls.py#L70), [89](../../tank/controls.py#L89), [91](../../tank/controls.py#L91) | Read/audit the platform master stop in platform scope; admit vendor calls before metering. |
| `tank/main.py` | [590](../../tank/main.py#L590), [670](../../tank/main.py#L670), [688](../../tank/main.py#L688), [808](../../tank/main.py#L808), [827](../../tank/main.py#L827), [832](../../tank/main.py#L832), [1250](../../tank/main.py#L1250), [1354](../../tank/main.py#L1354), [1478](../../tank/main.py#L1478), [1487](../../tank/main.py#L1487), [1489](../../tank/main.py#L1489), [1493](../../tank/main.py#L1493), [1503](../../tank/main.py#L1503), [1539](../../tank/main.py#L1539), [1561](../../tank/main.py#L1561), [1628](../../tank/main.py#L1628), [1676](../../tank/main.py#L1676), [1736](../../tank/main.py#L1736), [1742](../../tank/main.py#L1742), [1951](../../tank/main.py#L1951), [2008](../../tank/main.py#L2008), [2021](../../tank/main.py#L2021), [2031](../../tank/main.py#L2031), [2380](../../tank/main.py#L2380), [2858](../../tank/main.py#L2858), [2867](../../tank/main.py#L2867), [2921](../../tank/main.py#L2921), [2929](../../tank/main.py#L2929), [2948](../../tank/main.py#L2948), [3132](../../tank/main.py#L3132), [3143](../../tank/main.py#L3143), [3156](../../tank/main.py#L3156), [3165](../../tank/main.py#L3165), [3226](../../tank/main.py#L3226), [3243](../../tank/main.py#L3243), [3263](../../tank/main.py#L3263), [3266](../../tank/main.py#L3266), [3272](../../tank/main.py#L3272), [3275](../../tank/main.py#L3275), [3288](../../tank/main.py#L3288), [3651](../../tank/main.py#L3651), [4984](../../tank/main.py#L4984) | Admit routed models; separately gate configured fallbacks; replay paid results; resume background work; attach paid-step receipt provenance. |
| `tank/moa.py` | [461](../../tank/moa.py#L461), [527](../../tank/moa.py#L527), [638](../../tank/moa.py#L638), [658](../../tank/moa.py#L658), [664](../../tank/moa.py#L664), [691](../../tank/moa.py#L691), [699](../../tank/moa.py#L699), [746](../../tank/moa.py#L746), [753](../../tank/moa.py#L753), [802](../../tank/moa.py#L802) | Give each model seat its own admission/checkpoint and stable retry identity; suspend benchmark/shadow work. |
| `tank/paid_http.py` | [1](../../tank/paid_http.py#L1) | Checkpoint vendor HTTP reads before billing hooks; refuse uncertain repeats. |
| `tank/paid_steps.py` | [1](../../tank/paid_steps.py#L1) | Tenant registry, Ask/Auto persistence, approvals, admin cards, durable continuations, run identities and call checkpoints. |
| `tank/priority_queue.py` | [33](../../tank/priority_queue.py#L33), [164](../../tank/priority_queue.py#L164), [221](../../tank/priority_queue.py#L221) | Keep approval waits queued; distinguish an unspent closed-window refusal. |
| `tank/research.py` | [37](../../tank/research.py#L37), [247](../../tank/research.py#L247), [250](../../tank/research.py#L250), [252](../../tank/research.py#L252) | Admit Research after existing guards; checkpoint its measured response and receipts. |
| `tank/rig_forge_routes.py` | [61](../../tank/rig_forge_routes.py#L61), [96](../../tank/rig_forge_routes.py#L96), [110](../../tank/rig_forge_routes.py#L110), [124](../../tank/rig_forge_routes.py#L124), [130](../../tank/rig_forge_routes.py#L130), [136](../../tank/rig_forge_routes.py#L136), [151](../../tank/rig_forge_routes.py#L151) | Gate GPU reserve/claim; retain approval metadata through completion and legacy reservations. |
| `tank/routellm_shadow.py` | [180](../../tank/routellm_shadow.py#L180) | Reuse paid model receipts without duplicate spend; scope tenant evidence separately. |
| `tank/schema.sql` | [3152](../../tank/schema.sql#L3152) | Add registry, tenant preferences/audit, approval/continuation and call-journal tables; RLS and receipt metadata. |
| `tank/skala_revalidation.py` | [45](../../tank/skala_revalidation.py#L45), [73](../../tank/skala_revalidation.py#L73), [176](../../tank/skala_revalidation.py#L176) | Keep pending evaluations queued and reuse their stable paid-run identity. |
| `tank/vendor_meter.py` | [234](../../tank/vendor_meter.py#L234), [280](../../tank/vendor_meter.py#L280) | Give Base skill requests trusted stable run identities with their private record attribution. |
| `tests/acceptance/test_paid_steps.py` | [1](../../tests/acceptance/test_paid_steps.py#L1) | Ten real HTTP/card/receipt fixture paths plus one-row-one-case guard. |
| `tests/paid_steps_browser_build.cjs` | [1](../../tests/paid_steps_browser_build.cjs#L1) | Bundle real React modules with existing Next webpack; fixture only identity/navigation and transport. |
| `tests/paid_steps_settings.cjs` | [1](../../tests/paid_steps_settings.cjs#L1) | Execute the real Next API with authenticated fixture boundaries. |
| `tests/test_agent1_brain_route.py` | [42](../../tests/test_agent1_brain_route.py#L42), [137](../../tests/test_agent1_brain_route.py#L137) | Explicit SDK protocol admission fixture; verify the paid-step master refusal audit path. |
| `tests/test_base_context_dev.py` | [19](../../tests/test_base_context_dev.py#L19) | Explicit admission fixture for vendor protocol tests. |
| `tests/test_command.py` | [819](../../tests/test_command.py#L819), [1164](../../tests/test_command.py#L1164) | Make legacy router protocol fixtures explicitly automatic while retaining the master-stop check. |
| `tests/test_moa_integration.py` | [21](../../tests/test_moa_integration.py#L21) | Explicit admission/journal fixture for existing MoA protocol and guard tests. |
| `tests/test_paid_steps.py` | [1](../../tests/test_paid_steps.py#L1) | Disposable-Postgres approval, tenancy, card, receipt, replay, fallback, vendor and product-router proofs. |
| `tests/test_paid_steps_settings.py` | [1](../../tests/test_paid_steps_settings.py#L1) | Backend contract and actual browser at 375, 390 and 1440; check independent switches, states, labels, saves and no external requests. |
| `tests/test_perplexity_research.py` | [159](../../tests/test_perplexity_research.py#L159) | Explicit admission/journal fixture for Research protocol tests. |
| `tests/test_rig_forge_tank.py` | [25](../../tests/test_rig_forge_tank.py#L25) | Configure existing GPU protocol fixtures explicitly as Auto. |
| `tests/test_tank_ladder.py` | [36](../../tests/test_tank_ladder.py#L36) | Paid-step approval integration and validation. |
| `tests/test_vendor_ledger_postgres.py` | [24](../../tests/test_vendor_ledger_postgres.py#L24) | Keep durable vendor receipt fixtures separate from approval integration coverage. |
| `tests/tiger_brain/test_tg3.py` | [92](../../tests/tiger_brain/test_tg3.py#L92) | Configure the shared room-corridor protocol fixture explicitly; retain the real master stop. |
| `workspace/app/chats/contract.ts` | [4](../../workspace/app/chats/contract.ts#L4) | Carry paid-step provenance on receipt rows. |
| `workspace/app/chats/window.tsx` | [25](../../workspace/app/chats/window.tsx#L25) | Show step and approved/automatic receipt metadata; show confirmations before the first answer. |
| `workspace/app/onboarding/csv.ts` | [56](../../workspace/app/onboarding/csv.ts#L56) | Remove obsolete approval claim while retaining the existing sentence prefix. |
| `workspace/app/product-nav.ts` | [79](../../workspace/app/product-nav.ts#L79) | Give the settings page its own existing menu shell. |
| `workspace/app/settings/paid-steps/api/route.ts` | [1](../../workspace/app/settings/paid-steps/api/route.ts#L1) | Authenticated, same-origin, bounded settings transport; forward no browser tenant override. |
| `workspace/app/settings/paid-steps/page.tsx` | [1](../../workspace/app/settings/paid-steps/page.tsx#L1) | Founder/tenant-admin page authorization; reuse the Workspace menu and existing master state. |
| `workspace/app/settings/paid-steps/settings.css` | [1](../../workspace/app/settings/paid-steps/settings.css#L1) | Frame-based desktop/mobile content, state styling and mobile header clearance. |
| `workspace/app/settings/paid-steps/settings.tsx` | [1](../../workspace/app/settings/paid-steps/settings.tsx#L1) | Live independent Ask/Auto switches, checked saves, and source states; reuse the founder master action. |
| `workspace/app/trigger/shell.tsx` | [10](../../workspace/app/trigger/shell.tsx#L10), [13](../../workspace/app/trigger/shell.tsx#L13), [60](../../workspace/app/trigger/shell.tsx#L60), [82](../../workspace/app/trigger/shell.tsx#L82), [116](../../workspace/app/trigger/shell.tsx#L116) | Reusable menu title; preserve Trigger default behavior. |
