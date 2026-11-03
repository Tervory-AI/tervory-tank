# Market Lab ML3 handoff

Branch `codex/market-lab-ml3`; checkout `/workspace/codex-market-lab-ml3`.
Prepared 3 November 2026 (Pacific). Claude opens the PR; the founder merges.
**No founder browser acceptance or CI Tank pass is claimed.**

## Where work stopped and why

`f3310a088a54e4f6883ac414ccaa967dc398400a` was pushed, but verification was
unfinished. The last attempted exact-command / bundled-runtime check hit a
60-second pgserver setup timeout and the isolated evaluator's own 60-second
subprocess timeout on the loaded host. Before final verification/handoff,
the thread moved to ML4, then the requested quota diagnosis and cleanup.
ML3 was not declared complete. No PR or CI run existed at that stop.

On resumption, current main was merged without conflicts. The previously
unfinished targeted check passed: **31 passed, 7 skipped, 1,372 subtests passed**.
Further fixes prevent an exact command with missing authoritative turn data from
falling through to a model, return setting names from the existing feed-key
registry, and ensure the existing tenant refresh/resolution schedules only when
alert delivery is explicitly confirmed. Each finished file was pushed serially.

## What changed

- Market Lab produces `market_lab.ioc.v1` from CISA KEV and GHSA advisories matching
  exact package pins in this public repository's actual lock/requirements files.
  Radix's existing parsers are reused. Test/fixture paths are excluded. Unknown OSV
  upstreams are excluded rather than assigned GitHub's licence. Size, pagination,
  public destination, pacing and blocked-site checks reuse the feed transport.
- Existing daily chassis scheduling stores the latest platform bundle in reports.
  Autumbra consumes it through Tank's room-key/founder corridor, the existing
  validator, advisory catalogue and source-naming receipt writer. No room-to-room
  call or Autumbra-owned feed registry was introduced.
- Tenant admins opt into email/webhook or turn alerts off through existing Confirm
  cards. Rig's SMTP sender and Tiger's interrupted-send guard are reused. Pending
  claims become sending before transport; interrupted/uncertain sends are not
  automatically repeated. Tenant settings and delivery claims follow the existing
  personal_tokens RLS rollout above the generated memory schema marker.
- Tank generates and encrypts the tenant webhook signing value at runtime under
  the brief's explicit exception, returns it in the first Confirm response only,
  and removes it before card/event/history persistence. HMAC-SHA256 signs the exact
  request bytes. Outbound delivery reuses the existing SSRF-safe public transport.
- The existing mounted chat view retains that single response across polling and
  discards it on chat switches. No page, visible wording, field label or layout
  was added. Placeholder-only tests inspect durable state and logs for disclosure.
- Four existing-card reads return stored warnings, predictions, calibration and
  feed state with code receipts at zero cost. Exact command planning is code.
  Feed reads return registry setting names, never values. Keyed feeds stay off
  until the founder fills their existing values.
- Feed changes were copied into new `market.series_fetch/1.3.1` with preserved
  baseline cases and new licence/transport checks. Older versions were untouched;
  the new snapshot is neither approved nor selected by policy by this branch.

## Sources and terms checked 3 November 2026

- [CISA's official KEV repository licence](https://raw.githubusercontent.com/cisagov/kev-data/develop/LICENSE): CC0.
- [OSV upstream data licences](https://google.github.io/osv.dev/data/) and
  [GitHub Advisory Database licence](https://github.com/github/advisory-database/blob/main/LICENSE.md):
  this producer redistributes only the GHSA upstream under CC BY 4.0, with source credit.
- [URLhaus](https://urlhaus.abuse.ch/api/) and [ThreatFox](https://threatfox.abuse.ch/api/)
  require Auth-Key; they were excluded.
- [Spamhaus commercial data terms](https://www.spamhaus.org/faqs/commercial-data/)
  do not establish unrestricted keyless commercial use; it was excluded.

## Verification and remaining acceptance

Exact resumed commands and their captured results are in
[resume-results.txt](resume-results.txt). Earlier regression output remains in
[regressions.txt](regressions.txt).

- Broad Market Lab / Autumbra / Ghost selection: **496 passed, 8 skipped in 177.11s**.
- Bundle-runtime / exact-command / CLI code selection: **31 passed, 7 skipped,
  1,372 subtests passed in 89.13s**.
- Newly added fail-closed/setting-name checks: **2 passed in 15.97s**.
- Explicit tenant scheduling check: **1 passed in 3.51s**.
- The final complete ML3-file result is captured in `resume-results.txt`.
- Ruff E9/F, Python compilation and `git diff --check` passed.
- Existing `_startup` role/admin-pool checks were re-read; SQL tests exercise staged
  and enforced RLS with a non-bypass test role. Only disposable test databases were used.

**CI `tank`: pending.** Both of these returned `[]`; no PR or branch CI run exists:

```sh
gh pr list --head codex/market-lab-ml3 --state all --json number,state,url
gh run list --branch codex/market-lab-ml3 --limit 10 --json databaseId,event,status,conclusion,url
```

Per the founder's later ruling, CI's Tank job is the full-suite test of record.
No new local full-suite result is claimed. The Docker image build, Workspace
TypeScript/build, and founder browser/email/live-bundle acceptance remain pending.
The cleanup removed rebuildable node_modules; no reinstall was done on this resume.

After Claude opens the PR, record its actual Tank CI job URL/result and compare
failures with main before changing unrelated code. The founder's real browser
screenshots must show all four `/chats` reads and receipts, a confirmed email opt-in
followed by an actual warning arriving, and an Autumbra receipt naming CISA/OSV
from a bundle received through Tank. No screenshots are supplied or fabricated here.
No fixture was placed on a live screen. ML4 item 6 still waits for this branch to
be merged to main by the founder.

## Runtime settings and deployment

Only names were added: `MARKET_LAB_SMTP_HOST`, `MARKET_LAB_SMTP_PORT`,
`MARKET_LAB_SMTP_USER`, `MARKET_LAB_SMTP_PASSWORD`, `MARKET_LAB_SMTP_FROM`,
`MARKET_LAB_SMTP_ALERT_ADDRESSES`. The last is the existing sender's exact
per-tenant recipient mapping. The founder supplies values; none were inspected,
created or configured by the builder. No production data changed.

Deploy-on-merge covers Tank/Workspace and regional main copies, plus changed
Market Lab, Autumbra/Ghost and Tiger room paths and their regional copies under
the repository's existing rules. No deployment was performed by this thread.

## File and line manifest

Against main `ecef216bc16d17c6337242971d117b3fbd8db854`; numbers are changed-hunk starts.

| File | Lines |
| --- | --- |
| `.env.example` | 504 |
| `agents/ghost/app.py` | 277, 341 |
| `agents/market_lab/Dockerfile` | 14 |
| `agents/market_lab/app.py` | 142, 206, 221, 225, 364 |
| `agents/market_lab/core/intel.py` | 1 |
| `agents/market_lab/core/ml3.py` | 1 |
| `agents/market_lab/docker-compose.yml` | 34 |
| `agents/market_lab/feeds/collect.py` | 111 |
| `agents/market_lab/feeds/licence.py` | 17 |
| `agents/market_lab/feeds/licences.py` | 134 |
| `agents/market_lab/feeds/live.py` | 163, 172 |
| `agents/tiger/alert_email.py` | 47, 139 |
| `tank/command.py` | 39, 113, 472, 1184, 1235, 1593, 1610, 1674 |
| `tank/market_lab_ml3.py` | 1 |
| `tank/market_lab_routes.py` | 25 |
| `tank/schema.sql` | 2444 |
| `tank/skills/market.series_fetch/1.3.1/BUNDLE.md` | 1 |
| `tank/skills/market.series_fetch/1.3.1/CHANGELOG.md` | 1 |
| `tank/skills/market.series_fetch/1.3.1/evals/cases.jsonl` | 1 |
| `tank/skills/market.series_fetch/1.3.1/evals/feed_cases.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/__init__.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/adapters.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/batch_guard.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/catalog.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/db.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/engines/__init__.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/engines/ffl/__init__.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/engines/ffl/lists.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/engines/ffl/sources.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/fetch.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/geo.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/keyless.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/keys.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/licence.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/licences.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/live.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/models.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/published.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/reader.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/runner.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/schema.sql` | 1 |
| `tank/skills/market.series_fetch/1.3.1/feeds/store.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/pure.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/run.py` | 1 |
| `tank/skills/market.series_fetch/1.3.1/skill.yaml` | 1 |
| `tank/skills/market.series_fetch/1.3.1/tests/fixtures/feeds/geo/zip_county.csv` | 1 |
| `tank/skills/market.series_fetch/1.3.1/tests/fixtures/feeds/listing/2024-01.tsv` | 1 |
| `tank/skills/market.series_fetch/1.3.1/tests/fixtures/feeds/listing/2024-02.tsv` | 1 |
| `tests/market_lab_ml3/regressions.txt` | 1 |
| `tests/market_lab_ml3/sources.json` | 1 |
| `tests/test_market_lab_ml3.py` | 1 |
| `workspace/app/chats/window.tsx` | 62, 95, 104, 172 |

## Push discipline

Each finished file was committed, then current main merged, then pushed on this
same branch. No push failed. The repeated exact sequence was:

```sh
git fetch origin main && git merge --no-edit origin/main && git push origin HEAD
```

The initial resume merge was commit `623b6740`; it auto-merged command/schema and
retained current main. Subsequent merges reported already up to date.
