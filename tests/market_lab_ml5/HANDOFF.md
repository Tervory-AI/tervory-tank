# ML5: patterns and the 90-day gate in /chats

Branch: `codex/market-lab-w3`, based on `f0072e8e` from main. Claude opens the PR;
the founder merges. No main merge, production change, deployment, new schema,
frontend wording, setting, provider or approved skill change was made. ML7 stays
parked. ML6 has not started.

The exact commands `market_lab.patterns` and `market_lab.gate` now propose the
existing Confirm cards using code. Confirm dispatches through ML3's existing
reads route and room handler, then records the existing rung-3, model `code`,
zero-dollar receipt. Neither read invokes the planner or model gateway.

Patterns reuse ML4's SQL-first Hermes listing: only the requesting tenant's
private records and founder-published platform records matching the configured
pair IDs and source/ref/downstream fields survive. There is no recall, embedding
search, publication or memory write. Gates reuse ML4's qualification and original
ID deduplication. Their new `opens_at` value is 90 elapsed days after the earliest
qualifying resolved original's issue date, preserving ML4's existing rule. With
no qualifying resolved original, that date is null and the gate stays closed.

## File and line manifest

| File | Line | Change |
| --- | --- | --- |
| `agents/market_lab/core/ml3.py` | 41 | Patterns use the existing room memory and engine plan; gate uses the tenant ledger. |
| `agents/market_lab/core/predictions.py` | 11, 144 | Return the opening timestamp from the same calculation as gate eligibility. |
| `tank/market_lab_ml3.py` | 25, 48 | Extend READS (and therefore the existing exact-command allowlist); project both results into existing card fields. |
| `tank/command.py` | 44, 1357 | Add both tools and GET adapters beside ML3's reads. No confirmed-dispatch mutation set change. |
| `tests/test_market_lab_ml5.py` | 1 | Six offline cases: scoped room patterns, three fixed-clock boundary cases, and two end-to-end code proposal/Confirm/receipt cases. |
| `tests/market_lab_ml5/verification.txt` | 1 | Exact setup/test/check commands and captured results. |
| `tests/market_lab_ml5/HANDOFF.md` | 1 | Review handoff, display limitations and outstanding acceptance. |

## Existing-card display and Figma limitations

No label or layout was added to `workspace/app/chats/presentation.ts`.

- A pattern row uses Name for pair ID, Status for the stored tier (`client` or
  `platform`), Count for episodes and Total for hits. The raw validated claim is
  retained in the response, but the existing presenter does not render objects.
- A gate row uses Name for its kind/feed/horizon values, Status for open/closed,
  Summary for its ISO opening timestamp and Count for qualifying resolved
  originals. The existing outer Total is the number of returned records.
- Dedicated labels for pattern lag minimum/maximum/median, hit rate, individual
  source/ref/downstream identifiers, and evidence IDs need an approved Figma
  frame before those values can be displayed separately. The existing card
  likewise has no dedicated opening-date, horizon-unit, days-covered or closed-
  reason label. Opening dates are displayed under its existing Summary label;
  days-covered and closed reasons remain in the room's gate result only.
- The existing presenter shows the first five rows of a returned collection.
  Both tools retain ML3's existing `limit`/`page` arguments for additional rows.
  No empty-state or error wording was introduced.

## Verification

Source tested at `6ba77b7a`; subsequent commits add evidence only. Commands and
full output are in [verification.txt](verification.txt).

- New ML5 checks: **6 passed**.
- Market Lab/feed selection, including ML3 and ML4: **291 passed, 7 skipped**.
- Research/consumer/access corridor checks: **7 passed, 1 skipped**.
- Ruff E9/F on all five changed Python files and `git diff --check`: passed.

All pytest commands disable outside sockets/DNS and permit loopback/Unix sockets
for disposable pgserver tests. They use this checkout's `.tmp` as TMPDIR; no test
containers or production databases were used. The existing optional service/
database checks retained their skips; they are not claimed as executed. The
new ML5 Confirm/receipt tests ran against disposable PostgreSQL without skips.
Every finished file was committed and pushed serially; no push failed.

Read-only status checks after the source/evidence pushes:

```sh
gh pr list --repo Tervory-AI/tervory-tank --head codex/market-lab-w3 --state all --json number,state,url
# []
gh run list --repo Tervory-AI/tervory-tank --branch codex/market-lab-w3 --limit 3 --json headSha,status,conclusion,url
# []
```

CI is the full-suite result of record. Final-head CI Tank and Workspace results
are pending Claude opening the PR. This thread did not open, label or merge one.

## Founder browser acceptance still outstanding

After review, merge and deployment, the founder must type each exact command in
his own `/chats`, confirm its card, and verify his real patterns and cohort gate
states, opening dates, counts and $0 receipts. Also check additional pages when
there are more than five patterns. No live fixture, founder impersonation,
screenshot or browser acceptance has been fabricated. Attach the founder's
actual screenshots and final-head CI results to the PR before claiming DONE.
