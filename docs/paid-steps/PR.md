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

## Validation and CI status

All paid-step provider calls use offline fixtures and disposable loopback Postgres. No live acceptance or production configuration change is claimed.

Commands run:

- `python -m pytest tests/test_paid_steps.py tests/acceptance/test_paid_steps.py tests/test_paid_steps_settings.py -n 2 -q --assert=plain --timeout=600 --disable-socket --allow-unix-socket --allow-hosts=localhost,127.0.0.1,::1`: 67 passed, including the four real-chat continuation cases (add `tests/test_paid_steps_chats.py` to the command).
- `python -m pytest tests/test_paid_steps_chats.py -n 2 -q` with those offline flags: four real /chats cases passed: approval, denial, approval before persistence, and a private member request resumed after a separate admin-thread approval.
- RouteLLM shadow/accounting: 14 passed. Batch cap/dispatch: six passed. CLI client protocol: 35 passed. Settings browser proofs cover 375, 390 and 1440px, independent switches, master pause, errors and no horizontal scroll.
- `ruff check tank tests --select E9,F --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"`: passed.
- `workspace/node_modules/.bin/tsc --project workspace/tsconfig.json --noEmit`: passed, including the final chat phase flag.
- `PRECHECK_SKIP_SEMGREP=1 scripts/precheck.sh`: latest run passed lint, Gitleaks and OSV with Semgrep skipped. Its broad test stage was interrupted after stack inspection confirmed the unchanged approved Base scrape email regex was still processing the 400 KB fixture. This is not a passing precheck. Earlier broad runs exposed fixture assumptions repaired here, a local integration DSN prerequisite, and a 600-second timeout in the unchanged approved Base scrape email matcher. No approved package or timeout suppression was changed.

Local Semgrep is stopped at the founder's direction and will not run again. An earlier local scan reached its tool timeout, not a reported finding. No scanner exception was added.

[CI run 41899625731](https://github.com/Tervory-AI/tervory-tank/actions/runs/41899625731) tested gate-3 head `e948ab5451a536ff43eb7c6cb53196fa428c710e`. Lint and Workspace passed. Tank and command-acceptance failures led to the fixes below; final-head CI remains required. The manually dispatched security job scanned full history/manifests and reported existing findings in unchanged files. CI is not claimed green.

## Runtime and regression repairs

The continuation transaction commits its pending confirmation card before ending the current /chats stream phase. Approval arriving before continuation persistence is recovered; resumption restores the original task and private thread. Denial records its reason and ends the original task. Unattended CLI callers leave paid approval pending. Completed approvals cannot starve new cards.

SDK callers retry with an opaque run identity after approval; independent identical requests remain independent. Receipt costs use numeric SQL parameters. Input/region guards run before journal access. Batch price/cap refusals remain retryable without ambiguous dispatch claims. Registry metadata grants and schema generation boundaries are tested. Existing protocol fixtures explicitly choose Auto or mock their dispatch boundary; real default-Ask proofs use Postgres. RLS function pins and the repository's one-door audit inventory reflect the changed continuation paths.

The reader email matcher bounds token lengths to avoid quadratic matching on long plain-text tool results. A copied flat Base app under repo-local TMPDIR no longer discovers its parent repository's skill packages. Neither repair edits an approved skill package.

## Gate 2: settings

PR #685 landed while this task was running. `/settings/paid-steps` implements its desktop/mobile Ask/Auto layout with real tenant step records, not the sample inventory. Founder and tenant-admin authorization uses existing identity checks on both page and Tank API. The global pause retains its existing founder-only action. Each save changes only the selected step; partial errors never report a successful save. Empty/loading/error/paused/saved states use the frame text. The onboarding CSV retains only its previously approved prefix, removing the obsolete no-waits claim.

`python -m pytest tests/test_paid_steps_settings.py -n 2 -q` — 4 passed; browser tests use the real React component, existing Next webpack and local fonts, intercept every HTTP request, and refuse every non-loopback host. Tested 375, 390 and 1440px without horizontal scroll, loading, empty, save/error, master pause and tenant-admin presentation. `workspace/node_modules/.bin/tsc --project workspace/tsconfig.json --noEmit` — passed. See [frame register and screenshots](FRAMES.md).

## Gate 3: product testing sheets

Ten product paid-rung rows (Base, Tiger, Market Lab, Rig, Tisan, Radix, Zenas, Trigger, Autumbra and Tank/model routing) have ten matching offline HTTP cases and a row/case guard. Each exercises Ask → existing confirmation card → approved receipt, idempotent replay, Auto → automatic receipt, and master pause → no paid dispatch. `python -m pytest tests/acceptance/test_paid_steps.py -n 2 -q` — 11 passed, also included in the 58-case focused run above.

Final focused settings/runtime check: `PAID_STEPS_TEST_DATABASE_URL=<loopback throwaway Postgres> PYTHONPATH=tank:tests python -m pytest tests/test_paid_steps.py tests/test_paid_steps_settings.py -n 2 -q --assert=plain --timeout=600 --disable-socket --allow-unix-socket --allow-hosts=localhost,127.0.0.1,::1` — **49 passed**. The same flags on `tests/acceptance/test_paid_steps.py` — **11 passed**, including actual task/model names in confirmation cards. Registry task/model display columns are additive; stable authorization IDs do not change. Final Workspace typecheck passed.

Final SQL parameter/tenant regression: `python -m pytest tests/test_ledger_sql_param.py -n 2 -q` with offline flags — **39 passed**. Master-pause benchmark regression — **2 passed**.

Final local limitations: repository-wide secret and one-door audit tests hit their 300-second test limits while scanning unchanged fixtures/source; no finding was returned before timeout. A core-baseline concurrency test hit its existing two-second transaction deadline; five other cases passed before stop. These limits are recorded, not suppressed or marked successful. Final-head CI is required. The paid-step focused suite (67 cases), SQL/tenant parameter suite (39), CLI protocol (35), shadow accounting (14), batch cap/dispatch (6) and Workspace typecheck passed.
