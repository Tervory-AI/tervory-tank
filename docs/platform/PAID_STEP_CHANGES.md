# Item 8 change index

Compared with the last Wave 4 head before item 8: `c248b5ed23642f38666e2e8cdfe082da4e251325`.
Runtime changes are separately pushed on `codex/platform-w4-paid-runtime` at `8c0362fc978428455b40cac36a6aa8772df71d91`; Claude opens its PR and lands it before the dependent backend. This index covers every changed file, including explicit fixture updates. No new provider, service or retry was added.

| File and line | Change |
| --- | --- |
| [agents/_chassis/chassis/tank.py:18](../../agents/_chassis/chassis/tank.py#L18) | Poll owning saved runs with the original key; never re-POST the paid operation. |
| [agents/base/room.py:218](../../agents/base/room.py#L218) | Resume the existing direct skill client from the approved saved response. |
| [agents/base/sources/context_dev.py:6](../../agents/base/sources/context_dev.py#L6) | Hash the exact vendor lookup before authorization. |
| [agents/base/sources/vendor_ledger.py:40](../../agents/base/sources/vendor_ledger.py#L40) | Require a bound Tank grant before credit reservation and vendor dispatch. |
| [agents/ghost/Dockerfile:10](../../agents/ghost/Dockerfile#L10) | Include the already-existing shared chassis transport in the Ghost image. |
| [agents/ghost/app.py:102](../../agents/ghost/app.py#L102) | Resume the existing Ghost Tank client after approval. |
| [agents/market_lab/core/research_adapter.py:46](../../agents/market_lab/core/research_adapter.py#L46) | Resume the retained native research compatibility client after approval. |
| [agents/rig/forge/service.py:82](../../agents/rig/forge/service.py#L82) | Give approval waiting its own bound before the existing GPU execution clock starts. |
| [agents/rig/rig_brain/forge.py:105](../../agents/rig/rig_brain/forge.py#L105) | Keep Tank credentials in the brain while polling the original claim. |
| [docs/platform/PAID_STEP_RUNTIME.md:1](../../docs/platform/PAID_STEP_RUNTIME.md#L1) | Separate client prerequisite and deployment order. |
| [docs/platform/WAVE4.md:113](../../docs/platform/WAVE4.md#L113) | Behavior, tools, missing frames, runtime prerequisite and measured serial proof. |
| [researcher/app.py:144](../../researcher/app.py#L144) | Read the approved Tank completion in the isolated research adapter. |
| [researcher/paid_transport.py:1](../../researcher/paid_transport.py#L1) | Bounded isolated-image result polling with owning tenant/key. |
| [tank/agent_skills.py:211](../../tank/agent_skills.py#L211) | Gate room model dispatch and keep the original JSON/SSE completion alive through Ask. |
| [tank/bench.py:186](../../tank/bench.py#L186) | Gate benchmark model calls and scope each benchmark continuation. |
| [tank/command.py:57](../../tank/command.py#L57) | Founder tools, deterministic settings planning, approval/cancel cards, suspended turns, execution budgets and pending-card recovery. |
| [tank/controls.py:84](../../tank/controls.py#L84) | Gate Brave/Places immediately before the metered HTTP dispatch; retain the global pause. |
| [tank/main.py:1247](../../tank/main.py#L1247) | Model/LLM/batch dispatch gates; caller and post-wait policy/home checks; detached shadows; pool-free provider-batch claims; Base trial wait bound. |
| [tank/moa.py:174](../../tank/moa.py#L174) | Exclude Ask waits from active execution budgets without sharing sibling seat allowances. |
| [tank/paid_steps.py:186](../../tank/paid_steps.py#L186) | Default Ask/Auto, input-bound approvals, founder tools/inbox, one-use claims, wait-aware budgets, saved HTTP results and interrupted-run leases. |
| [tank/priority_queue.py:258](../../tank/priority_queue.py#L258) | Durable worker claims and short tenant-owned SQL checkouts while a run waits. |
| [tank/research.py:155](../../tank/research.py#L155) | Gate native research web/fetch bundles and model dispatch; preserve authenticated room ownership. |
| [tank/rig_forge_routes.py:104](../../tank/rig_forge_routes.py#L104) | Gate HF work before the immutable once-only claim and charged receipt. |
| [tank/schema.sql:2999](../../tank/schema.sql#L2999) | Additive settings, audit, approvals, saved runs, worker leases, tenant policies and queue/eval/batch claims. |
| [tank/semantic_cache.py:231](../../tank/semantic_cache.py#L231) | Give background judge/learning work independent approval scopes. |
| [tank/skala_revalidation.py:159](../../tank/skala_revalidation.py#L159) | Claim eval jobs durably, release SQL during approval, isolate jobs and never replay interrupted evidence. |
| [tests/conftest.py:33](../../tests/conftest.py#L33) | Register dedicated empty-settings tests so default Ask is tested independently. |
| [tests/market_lab_gpt_researcher/test_researcher.py:55](../../tests/market_lab_gpt_researcher/test_researcher.py#L55) | Explicitly authorize synthetic fixture models/paid tools while retaining existing routing, accounting and lifecycle assertions. |
| [tests/paid_fixture.py:1](../../tests/paid_fixture.py#L1) | Explicit Auto choices for legacy synthetic provider fixtures; no production default override. |
| [tests/skala_b3_b4/test_lifecycle.py:67](../../tests/skala_b3_b4/test_lifecycle.py#L67) | Explicitly authorize synthetic fixture models/paid tools while retaining existing routing, accounting and lifecycle assertions. |
| [tests/tenant_rls/run_route.pinned:25](../../tests/tenant_rls/run_route.pinned#L25) | Record the founder-authorized dispatch/caller/wait changes in the existing source guard. |
| [tests/test_agent1_brain_route.py:29](../../tests/test_agent1_brain_route.py#L29) | Explicitly authorize synthetic fixture models/paid tools while retaining existing routing, accounting and lifecycle assertions. |
| [tests/test_bf2_tank_guards.py:72](../../tests/test_bf2_tank_guards.py#L72) | Explicitly authorize synthetic fixture models/paid tools while retaining existing routing, accounting and lifecycle assertions. |
| [tests/test_command.py:179](../../tests/test_command.py#L179) | Explicitly authorize synthetic fixture models/paid tools while retaining existing routing, accounting and lifecycle assertions. |
| [tests/test_dashboards.py:47](../../tests/test_dashboards.py#L47) | Explicitly authorize synthetic fixture models/paid tools while retaining existing routing, accounting and lifecycle assertions. |
| [tests/test_moa_integration.py:497](../../tests/test_moa_integration.py#L497) | Explicitly authorize synthetic fixture models/paid tools while retaining existing routing, accounting and lifecycle assertions. |
| [tests/test_paid_step_clients.py:1](../../tests/test_paid_step_clients.py#L1) | Reject forged identity or destination fields in paid settings. |
| [tests/test_paid_step_transport.py:1](../../tests/test_paid_step_transport.py#L1) | One POST and owning-result polling for shared/Base/Ghost/researcher/worker transports. |
| [tests/test_paid_steps.py:1](../../tests/test_paid_steps.py#L1) | Real SQL/card/continuation, default Ask, pause, one-use, cancellation, expiry, revocation, model rung, HF, queue/pool, protocol and RLS proofs. |
| [tests/test_perplexity_research.py:149](../../tests/test_perplexity_research.py#L149) | Explicitly authorize synthetic fixture models/paid tools while retaining existing routing, accounting and lifecycle assertions. |
| [tests/test_tank_ladder.py:61](../../tests/test_tank_ladder.py#L61) | Explicitly authorize synthetic fixture models/paid tools while retaining existing routing, accounting and lifecycle assertions. |
| [tests/test_tank_one_door.py:189](../../tests/test_tank_one_door.py#L189) | Audit the one new offline inbound completion-test endpoint; no provider bypass added. |
| [tests/test_tank_routellm.py:165](../../tests/test_tank_routellm.py#L165) | Explicitly authorize synthetic fixture models/paid tools while retaining existing routing, accounting and lifecycle assertions. |
| [tests/test_tank_tenant_boundaries.py:18](../../tests/test_tank_tenant_boundaries.py#L18) | Explicitly authorize synthetic fixture models/paid tools while retaining existing routing, accounting and lifecycle assertions. |
| [tests/test_train1.py:38](../../tests/test_train1.py#L38) | Explicitly authorize synthetic fixture models/paid tools while retaining existing routing, accounting and lifecycle assertions. |
| [tests/test_vendor_ledger_postgres.py:120](../../tests/test_vendor_ledger_postgres.py#L120) | Explicitly authorize synthetic fixture models/paid tools while retaining existing routing, accounting and lifecycle assertions. |
| [tests/test_za_region.py:421](../../tests/test_za_region.py#L421) | Explicitly authorize synthetic fixture models/paid tools while retaining existing routing, accounting and lifecycle assertions. |
| [tests/test_zenas_z8b.py:341](../../tests/test_zenas_z8b.py#L341) | Explicitly authorize synthetic fixture models/paid tools while retaining existing routing, accounting and lifecycle assertions. |
| [workers/paid_transport.py:1](../../workers/paid_transport.py#L1) | Poll only the original validated Tank origin; ignore returned URLs. |
| [workers/task/__main__.py:58](../../workers/task/__main__.py#L58) | Keep the original worker request alive through its saved response. |

Missing settings/waiting frames and operational limits: [Wave 4 handoff](WAVE4.md#item-8-founder-askauto-for-every-paid-step).
