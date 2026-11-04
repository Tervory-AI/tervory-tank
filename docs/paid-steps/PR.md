# Per-tenant paid-step approval

Free work continues automatically. A reached paid step defaults to Ask, creates a durable pending approval, and resumes only after its tenant administrator confirms it in the existing /chats card. Auto is stored for that tenant and exact task/model seat or vendor step. The platform-owned Pause all paid work control is checked again on every admission, including approved and Auto runs.

Approval grants are bound to tenant, run, step and request fingerprint. Denials retain actor, reason and time. Settings changes have an append-only log. Receipts retain the step and approved/automatic provenance. Completed paid call results are replayed when later steps pause; an uncertain dispatched call is refused rather than repeated. Base record calls have stable identities across room restarts. Tank background continuations retain their original run identity; failed continuations remain inspectable.

No approved skill package was edited. Tank gates existing model routes, agent SDK calls, Research, Brave/Places and Rig GPU reservations. Gateway fallbacks are disabled during each dispatch; Tank walks the existing configured order and separately admits every fallback. Existing privacy, region, skill approval, token and spend limits remain in force. No provider, credential or paid service was added.

## Deployment impact

Tank changes deploy Boston and ZA through existing deployment selection. Shared chassis/brain changes affect their consuming rooms; Base and Rig adapters deploy those rooms. Schema additions are idempotent. Tenant tables follow the existing RLS rollout; bootstrap grants target only the authenticated tenant role, never PUBLIC. No Compose, environment, sign-in or approved skill version changes.

## Registry audit

| Product | Existing free path | Existing paid boundary and source |
| --- | --- | --- |
| Base | Code/cache, own search/browser, approved skills | `base.find_site` Brave and Places in approved 1.7.1; `agents/base/sources/context_dev.py` credits; configured extraction/verification models and agent brain via Tank |
| Tiger | Local extraction, diffs, own browser | Configured Tank model escalation, including screenshot/model interpretation; `agents/tiger/` and shared chassis |
| Market Lab | Public feeds and local calculations | `tank/research.py` configured Research model/preset, with itemized model/search/fetch receipts; configured model tasks through shared chassis |
| Rig | Code geometry, checks and local tools | Agent model seats via `tank/agent_skills.py`; distinct photogrammetry and trellis2 GPU reservations in `tank/rig_forge_routes.py` |
| Tisan | Figma read, scaffold, local quality checks | Configured Tank build/repair models through shared chassis |
| Radix | Local repository scanners and rules | Configured Tank model escalation through shared chassis/brain |
| Zenas | Public statutes, citation loaders, code checks | Configured Tank model tasks; keys for free public loaders are not classified as paid merely because they are keys |
| Trigger | Code checks and free writing rules | Configured Tank writing/revision models through shared chassis |
| Autumbra | Local observation, public feeds and rule-based signals | Existing Ghost/Autumbra Tank model tasks; `ghost` ownership maps to `autumbra`; paid feeds remain disabled |
| Model routing | Cache/code/zero-priced models | Exact task/model pairs, configured fallbacks, shadow candidates, judges, benchmark and revalidation seats |

The registry reads visible tenant/global policies and local configured fallback metadata. Runtime admission registers newly reached exact seats. A model switch does not authorize another model or another task. Unknown prices are treated as paid. A configured Context.dev free pass bypasses approval; a missing quote never grants spending permission. Apollo price-book metadata is not a runnable vendor rung and has no phantom switch.

## Gate 1 validation

Offline disposable Postgres: `PAID_STEPS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:<test-port>/postgres python -m pytest tests/test_paid_steps.py -n 2 -q` — 34 passed. Includes ten actual `main.run_route` product paths, approval cards, denial, RLS, master stop, receipt provenance, no repeated paid dispatch, actual approved Base Brave function through the Base client, and synchronous SDK wait/deny/foreign-tenant checks. External provider traffic uses in-process fixtures only.

`python -m pytest tests/test_command.py -n 2 -q` — 38 passed, 48 skipped (existing optional integration prerequisites).

`python -m pytest tests/test_base_context_dev.py tests/test_perplexity_research.py -n 2 -q` — 62 passed, 1 skipped. These protocol tests explicitly configure an admission fixture; default-Ask behavior is tested separately against real Postgres.

`ruff check tank tests --select E9,F --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"` — passed.

`workspace/node_modules/.bin/tsc --project workspace/tsconfig.json --noEmit` — passed.

Precheck and final-head CI results will be appended after completion. No live acceptance or production configuration change is claimed.

Local Semgrep reached its 900-second limit (`TimeoutExpired`, result `incomplete`). Per the founder's instruction, the next precheck uses `PRECHECK_SKIP_SEMGREP=1`; CI still runs Semgrep. No finding was waived and no scanner exception was added.

`PYTHONPATH=tank python -m pytest tests/test_moa_integration.py tests/test_core1_proof.py -n 2 -q` — 39 passed, 25 skipped. Optional Postgres integration prerequisites were not enabled in this run.

Latest focused regressions: 59 passed, 4 skipped before the final no-op chat snapshot fix; the remaining rejected-receipt snapshot regression is included in the current rerun. Direct Research-card approval and denial continuations: 2 passed. Task-worker approve/resume and deny: 2 passed. The paid-step backend contract: 1 passed. Final precheck results are recorded below once complete.

Local regression repairs: the reader email matcher now bounds token lengths to avoid quadratic matching on long plain-text tool results; a copied flat Base app under repo-local TMPDIR no longer discovers the parent repository's skill packages. Both existing regression cases pass. Chat snapshot reads only enter an edit transaction when an approval card needs an update.

Current focused validation: 58 passed, 4 skipped (paid runtime, ten HTTP acceptance rows, settings transport and command cross-lane regressions); two direct Research-card continuation cases passed separately after their addition. Off-peak hold/dispatch and provider-batch receipt/tenant-isolation checks: 2 passed. Settings browser/transport at 375, 390 and 1440: 4 passed. Workspace typecheck passed.

The broad precheck found a room-corridor protocol fixture missing explicit admission setup; its shared fixture now checks the real master stop before its fixture model dispatch. A separate room topology run hit the existing 30-second seal-check subprocess limit under host load; no seal-check behavior or timeout has been changed. Full precheck and CI status remain pending; no green full-suite result is claimed.

## Gate 2: settings

PR #685 landed while this task was running. `/settings/paid-steps` implements its desktop/mobile Ask/Auto layout with real tenant step records, not the sample inventory. Founder and tenant-admin authorization uses existing identity checks on both page and Tank API. The global pause retains its existing founder-only action. Each save changes only the selected step; partial errors never report a successful save. Empty/loading/error/paused/saved states use the frame text. The onboarding CSV retains only its previously approved prefix, removing the obsolete no-waits claim.

`python -m pytest tests/test_paid_steps_settings.py -n 2 -q` — 4 passed; browser tests use the real React component, existing Next webpack and local fonts, intercept every HTTP request, and refuse every non-loopback host. Tested 375, 390 and 1440px without horizontal scroll, loading, empty, save/error, master pause and tenant-admin presentation. `workspace/node_modules/.bin/tsc --project workspace/tsconfig.json --noEmit` — passed. See [frame register and screenshots](FRAMES.md).

## Gate 3: product testing sheets

Ten product paid-rung rows (Base, Tiger, Market Lab, Rig, Tisan, Radix, Zenas, Trigger, Autumbra and Tank/model routing) have ten matching offline HTTP cases and a row/case guard. Each exercises Ask → existing confirmation card → approved receipt, idempotent replay, Auto → automatic receipt, and master pause → no paid dispatch. `python -m pytest tests/acceptance/test_paid_steps.py -n 2 -q` — 11 passed, also included in the 58-case focused run above.

Final focused settings/runtime check: `PAID_STEPS_TEST_DATABASE_URL=<loopback throwaway Postgres> PYTHONPATH=tank:tests python -m pytest tests/test_paid_steps.py tests/test_paid_steps_settings.py -n 2 -q --assert=plain --timeout=600 --disable-socket --allow-unix-socket --allow-hosts=localhost,127.0.0.1,::1` — **49 passed**. The same flags on `tests/acceptance/test_paid_steps.py` — **11 passed**, including actual task/model names in confirmation cards. Registry task/model display columns are additive; stable authorization IDs do not change. Final Workspace typecheck passed.
