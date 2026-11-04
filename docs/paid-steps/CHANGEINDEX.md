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
| `cli/src/client.mjs` | [360](../../cli/src/client.mjs#L360), [388](../../cli/src/client.mjs#L388), [404](../../cli/src/client.mjs#L404) | Paid-step approval integration and validation. |
| `cli/test/client.test.mjs` | [452](../../cli/test/client.test.mjs#L452) | Paid-step approval integration and validation. |
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
| `tank/agent_skills.py` | [23](../../tank/agent_skills.py#L23), [25](../../tank/agent_skills.py#L25), [90](../../tank/agent_skills.py#L90), [110](../../tank/agent_skills.py#L110), [177](../../tank/agent_skills.py#L177), [199](../../tank/agent_skills.py#L199), [201](../../tank/agent_skills.py#L201), [232](../../tank/agent_skills.py#L232), [242](../../tank/agent_skills.py#L242), [317](../../tank/agent_skills.py#L317), [333](../../tank/agent_skills.py#L333) | Gate the existing agent model route and persist provenance in both ledger and SDK receipt. |
| `tank/base_product.py` | [78](../../tank/base_product.py#L78), [427](../../tank/base_product.py#L427), [441](../../tank/base_product.py#L441) | Validate Context.dev approval and link it to the vendor receipt, including idempotent retries. |
| `tank/bench.py` | [210](../../tank/bench.py#L210), [239](../../tank/bench.py#L239), [269](../../tank/bench.py#L269) | Gate benchmarks before calls and record their authorization; persist waiting work. |
| `tank/command.py` | [128](../../tank/command.py#L128), [173](../../tank/command.py#L173), [255](../../tank/command.py#L255), [269](../../tank/command.py#L269), [413](../../tank/command.py#L413), [585](../../tank/command.py#L585), [634](../../tank/command.py#L634), [769](../../tank/command.py#L769), [776](../../tank/command.py#L776), [1908](../../tank/command.py#L1908), [1921](../../tank/command.py#L1921), [2141](../../tank/command.py#L2141) | Expose paid confirmations to administrators, pause/resume turns, and present receipt provenance. |
| `tank/controls.py` | [38](../../tank/controls.py#L38), [70](../../tank/controls.py#L70), [89](../../tank/controls.py#L89), [91](../../tank/controls.py#L91) | Read/audit the platform master stop in platform scope; admit vendor calls before metering. |
| `tank/main.py` | [590](../../tank/main.py#L590), [670](../../tank/main.py#L670), [688](../../tank/main.py#L688), [808](../../tank/main.py#L808), [827](../../tank/main.py#L827), [832](../../tank/main.py#L832), [1250](../../tank/main.py#L1250), [1366](../../tank/main.py#L1366), [1490](../../tank/main.py#L1490), [1506](../../tank/main.py#L1506), [1508](../../tank/main.py#L1508), [1512](../../tank/main.py#L1512), [1522](../../tank/main.py#L1522), [1558](../../tank/main.py#L1558), [1580](../../tank/main.py#L1580), [1647](../../tank/main.py#L1647), [1695](../../tank/main.py#L1695), [1755](../../tank/main.py#L1755), [1761](../../tank/main.py#L1761), [1970](../../tank/main.py#L1970), [2027](../../tank/main.py#L2027), [2040](../../tank/main.py#L2040), [2050](../../tank/main.py#L2050), [2399](../../tank/main.py#L2399), [2877](../../tank/main.py#L2877), [2886](../../tank/main.py#L2886), [2940](../../tank/main.py#L2940), [2948](../../tank/main.py#L2948), [2967](../../tank/main.py#L2967), [3151](../../tank/main.py#L3151), [3162](../../tank/main.py#L3162), [3175](../../tank/main.py#L3175), [3184](../../tank/main.py#L3184), [3245](../../tank/main.py#L3245), [3262](../../tank/main.py#L3262), [3282](../../tank/main.py#L3282), [3285](../../tank/main.py#L3285), [3291](../../tank/main.py#L3291), [3294](../../tank/main.py#L3294), [3309](../../tank/main.py#L3309), [3672](../../tank/main.py#L3672), [5005](../../tank/main.py#L5005) | Admit routed models; separately gate configured fallbacks; replay paid results; resume background work; attach paid-step receipt provenance. |
| `tank/moa.py` | [461](../../tank/moa.py#L461), [527](../../tank/moa.py#L527), [638](../../tank/moa.py#L638), [658](../../tank/moa.py#L658), [664](../../tank/moa.py#L664), [691](../../tank/moa.py#L691), [699](../../tank/moa.py#L699), [746](../../tank/moa.py#L746), [753](../../tank/moa.py#L753), [802](../../tank/moa.py#L802) | Give each model seat its own admission/checkpoint and stable retry identity; suspend benchmark/shadow work. |
| `tank/paid_http.py` | [1](../../tank/paid_http.py#L1) | Checkpoint vendor HTTP reads before billing hooks; refuse uncertain repeats. |
| `tank/paid_steps.py` | [1](../../tank/paid_steps.py#L1) | Tenant registry, Ask/Auto persistence, approvals, admin cards, durable continuations, run identities and call checkpoints. |
| `tank/priority_queue.py` | [33](../../tank/priority_queue.py#L33), [164](../../tank/priority_queue.py#L164), [221](../../tank/priority_queue.py#L221) | Keep approval waits queued; distinguish an unspent closed-window refusal. |
| `tank/research.py` | [37](../../tank/research.py#L37), [247](../../tank/research.py#L247), [250](../../tank/research.py#L250), [252](../../tank/research.py#L252) | Admit Research after existing guards; checkpoint its measured response and receipts. |
| `tank/rig_forge_routes.py` | [61](../../tank/rig_forge_routes.py#L61), [89](../../tank/rig_forge_routes.py#L89), [96](../../tank/rig_forge_routes.py#L96), [110](../../tank/rig_forge_routes.py#L110), [124](../../tank/rig_forge_routes.py#L124), [130](../../tank/rig_forge_routes.py#L130), [136](../../tank/rig_forge_routes.py#L136), [151](../../tank/rig_forge_routes.py#L151) | Gate GPU reserve/claim; retain approval metadata through completion and legacy reservations. |
| `tank/routellm_shadow.py` | [180](../../tank/routellm_shadow.py#L180) | Reuse paid model receipts without duplicate spend; scope tenant evidence separately. |
| `tank/schema.sql` | [3102](../../tank/schema.sql#L3102) | Add registry, tenant preferences/audit, approval/continuation and call-journal tables; RLS and receipt metadata. |
| `tank/skala_revalidation.py` | [45](../../tank/skala_revalidation.py#L45), [73](../../tank/skala_revalidation.py#L73), [176](../../tank/skala_revalidation.py#L176) | Keep pending evaluations queued and reuse their stable paid-run identity. |
| `tank/vendor_meter.py` | [234](../../tank/vendor_meter.py#L234), [280](../../tank/vendor_meter.py#L280) | Give Base skill requests trusted stable run identities with their private record attribution. |
| `tests/acceptance/test_paid_steps.py` | [1](../../tests/acceptance/test_paid_steps.py#L1) | Ten real HTTP/card/receipt fixture paths plus one-row-one-case guard. |
| `tests/paid_steps_browser_build.cjs` | [1](../../tests/paid_steps_browser_build.cjs#L1) | Bundle real React modules with existing Next webpack; fixture only identity/navigation and transport. |
| `tests/paid_steps_fixtures.py` | [1](../../tests/paid_steps_fixtures.py#L1) | Paid-step approval integration and validation. |
| `tests/paid_steps_settings.cjs` | [1](../../tests/paid_steps_settings.cjs#L1) | Execute the real Next API with authenticated fixture boundaries. |
| `tests/tenant_rls/run_route.pinned` | [1](../../tests/tenant_rls/run_route.pinned#L1), [4](../../tests/tenant_rls/run_route.pinned#L4), [6](../../tests/tenant_rls/run_route.pinned#L6), [12](../../tests/tenant_rls/run_route.pinned#L12), [15](../../tests/tenant_rls/run_route.pinned#L15) | Paid-step approval integration and validation. |
| `tests/tenant_rls/run_task.pinned` | [1](../../tests/tenant_rls/run_task.pinned#L1) | Paid-step approval integration and validation. |
| `tests/test_agent1_brain_route.py` | [42](../../tests/test_agent1_brain_route.py#L42), [137](../../tests/test_agent1_brain_route.py#L137) | Explicit SDK protocol admission fixture; verify the paid-step master refusal audit path. |
| `tests/test_base_context_dev.py` | [19](../../tests/test_base_context_dev.py#L19) | Explicit admission fixture for vendor protocol tests. |
| `tests/test_bf2_tank_guards.py` | [17](../../tests/test_bf2_tank_guards.py#L17) | Paid-step approval integration and validation. |
| `tests/test_command.py` | [819](../../tests/test_command.py#L819), [1164](../../tests/test_command.py#L1164) | Make legacy router protocol fixtures explicitly automatic while retaining the master-stop check. |
| `tests/test_command_streaming.py` | [97](../../tests/test_command_streaming.py#L97), [126](../../tests/test_command_streaming.py#L126), [155](../../tests/test_command_streaming.py#L155), [242](../../tests/test_command_streaming.py#L242) | Paid-step approval integration and validation. |
| `tests/test_core1_proof.py` | [278](../../tests/test_core1_proof.py#L278) | Paid-step approval integration and validation. |
| `tests/test_dashboards.py` | [10](../../tests/test_dashboards.py#L10), [205](../../tests/test_dashboards.py#L205) | Paid-step approval integration and validation. |
| `tests/test_ledger_sql_param.py` | [19](../../tests/test_ledger_sql_param.py#L19), [56](../../tests/test_ledger_sql_param.py#L56) | Paid-step approval integration and validation. |
| `tests/test_moa_integration.py` | [21](../../tests/test_moa_integration.py#L21) | Explicit admission/journal fixture for existing MoA protocol and guard tests. |
| `tests/test_paid_steps.py` | [1](../../tests/test_paid_steps.py#L1) | Disposable-Postgres approval, tenancy, card, receipt, replay, fallback, vendor and product-router proofs. |
| `tests/test_paid_steps_chats.py` | [1](../../tests/test_paid_steps_chats.py#L1) | Paid-step approval integration and validation. |
| `tests/test_paid_steps_settings.py` | [1](../../tests/test_paid_steps_settings.py#L1) | Backend contract and actual browser at 375, 390 and 1440; check independent switches, states, labels, saves and no external requests. |
| `tests/test_perplexity_research.py` | [159](../../tests/test_perplexity_research.py#L159) | Explicit admission/journal fixture for Research protocol tests. |
| `tests/test_read1.py` | [144](../../tests/test_read1.py#L144) | Paid-step approval integration and validation. |
| `tests/test_rig_box_tank.py` | [48](../../tests/test_rig_box_tank.py#L48), [91](../../tests/test_rig_box_tank.py#L91) | Paid-step approval integration and validation. |
| `tests/test_rig_forge_tank.py` | [25](../../tests/test_rig_forge_tank.py#L25) | Configure existing GPU protocol fixtures explicitly as Auto. |
| `tests/test_tank_ladder.py` | [36](../../tests/test_tank_ladder.py#L36) | Paid-step approval integration and validation. |
| `tests/test_tank_one_door.py` | [275](../../tests/test_tank_one_door.py#L275) | Paid-step approval integration and validation. |
| `tests/test_tank_routellm.py` | [94](../../tests/test_tank_routellm.py#L94), [150](../../tests/test_tank_routellm.py#L150) | Paid-step approval integration and validation. |
| `tests/test_tank_routing_data.py` | [254](../../tests/test_tank_routing_data.py#L254) | Paid-step approval integration and validation. |
| `tests/test_tank_tenant_boundaries.py` | [38](../../tests/test_tank_tenant_boundaries.py#L38) | Paid-step approval integration and validation. |
| `tests/test_tenant_rls.py` | [266](../../tests/test_tenant_rls.py#L266), [268](../../tests/test_tenant_rls.py#L268) | Paid-step approval integration and validation. |
| `tests/test_train1.py` | [34](../../tests/test_train1.py#L34), [41](../../tests/test_train1.py#L41) | Paid-step approval integration and validation. |
| `tests/test_vendor_ledger_postgres.py` | [24](../../tests/test_vendor_ledger_postgres.py#L24) | Keep durable vendor receipt fixtures separate from approval integration coverage. |
| `tests/test_za_region.py` | [22](../../tests/test_za_region.py#L22) | Paid-step approval integration and validation. |
| `tests/test_zenas_z8b.py` | [20](../../tests/test_zenas_z8b.py#L20) | Paid-step approval integration and validation. |
| `tests/tiger_brain/test_tg3.py` | [92](../../tests/tiger_brain/test_tg3.py#L92) | Configure the shared room-corridor protocol fixture explicitly; retain the real master stop. |
| `workspace/app/chats/contract.ts` | [4](../../workspace/app/chats/contract.ts#L4), [8](../../workspace/app/chats/contract.ts#L8) | Carry paid-step provenance on receipt rows. |
| `workspace/app/chats/window.tsx` | [25](../../workspace/app/chats/window.tsx#L25), [226](../../workspace/app/chats/window.tsx#L226), [229](../../workspace/app/chats/window.tsx#L229) | Show step and approved/automatic receipt metadata; show confirmations before the first answer. |
| `workspace/app/onboarding/csv.ts` | [56](../../workspace/app/onboarding/csv.ts#L56) | Remove obsolete approval claim while retaining the existing sentence prefix. |
| `workspace/app/product-nav.ts` | [79](../../workspace/app/product-nav.ts#L79) | Give the settings page its own existing menu shell. |
| `workspace/app/settings/paid-steps/api/route.ts` | [1](../../workspace/app/settings/paid-steps/api/route.ts#L1) | Authenticated, same-origin, bounded settings transport; forward no browser tenant override. |
| `workspace/app/settings/paid-steps/page.tsx` | [1](../../workspace/app/settings/paid-steps/page.tsx#L1) | Founder/tenant-admin page authorization; reuse the Workspace menu and existing master state. |
| `workspace/app/settings/paid-steps/settings.css` | [1](../../workspace/app/settings/paid-steps/settings.css#L1) | Frame-based desktop/mobile content, state styling and mobile header clearance. |
| `workspace/app/settings/paid-steps/settings.tsx` | [1](../../workspace/app/settings/paid-steps/settings.tsx#L1) | Live independent Ask/Auto switches, checked saves, and source states; reuse the founder master action. |
| `workspace/app/trigger/shell.tsx` | [10](../../workspace/app/trigger/shell.tsx#L10), [13](../../workspace/app/trigger/shell.tsx#L13), [60](../../workspace/app/trigger/shell.tsx#L60), [82](../../workspace/app/trigger/shell.tsx#L82), [116](../../workspace/app/trigger/shell.tsx#L116) | Reusable menu title; preserve Trigger default behavior. |
