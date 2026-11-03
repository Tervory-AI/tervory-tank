# Market Lab ML4 handoff — partial, waiting for ML3

Branch: `codex/market-lab-ml4`. PR: [#606](https://github.com/Tervory-AI/tervory-tank/pull/606).
Prepared 3 November 2026 (Pacific). Founder merges; Claude opens the PR.

Original ML4 items 1–5 are implemented and locally checked. Review fixes 1–4
are pushed; review fix 5 (verified CI evidence) is still outstanding. Item 6 has
NOT started and remains explicitly held for ML3. This is not founder browser acceptance and not a completed ML4 job.
No page, card layout, visible wording, credential setting, keyed feed, production
row, schema, approved skill package or Hermes implementation changed.

## Review follow-up — 3 November 2026 (Pacific)

Implemented the founder-approved forget-then-save path without changing Hermes.
The existing `MemoryClient.forget` always receives the exact nonempty record UUID
and tenant. Private IDs now depend only on tenant, `warning_pattern`, and pair
ID. After a successful SQL read, identical claims skip both mutations. Changed
claims forget that client record and save the new claim under the same ID.
Failures in listing, forget, or save leave `pattern_pending` true; if deletion
succeeds but saving fails, the next run inserts into the same empty ID. A returned
ID must match the requested stable ID before the flag can be cleared. A confirmed
identical stored claim also completes a lost-response retry without rewriting it.

Older pair rows lacking the flag now start pending. The tests exercise two watches
for each pair, including unchanged legacy summaries, failures at both write steps,
and a failed save response. They retain one record for each of the seven pairs.
The SQL test asserts all configured pairs fit below Hermes's existing 50-row
limit and are present in the listing. This does not add pagination to Hermes.

Malformed weather dates are skipped and counted in one warning log message for
the series load. The valid events retain their original evidence indices. Job
ledgers use `ctx.memory`; HTTP ledgers use the room's existing `app.state.memory`.
No new memory client is constructed by `_ledger`.

### Review file and line manifest

| File | Lines | Change |
| --- | --- | --- |
| `agents/market_lab/core/warnings.py` | 117 | Missing pending flag means pending. |
| `agents/market_lab/core/patterns.py` | 30 | Pair-stable IDs, SQL equality check, exact scoped forget then save, durable retries. |
| `agents/market_lab/core/warning_store.py` | 22, 69, 111 | Validate dates, skip malformed events, log their count. |
| `agents/market_lab/app.py` | 47, 68, 73, 88, 108, 124, 138, 156, 169 | Reuse job/room memory. |
| `tests/test_market_lab_ml4.py` | 189, 223, 320, 336 | Identity, retry, legacy row, two-watch, malformed event and context tests. |
| `tests/test_market_lab_ml4_memory.py` | 39 | Actual Hermes routes/Records with fake encoder and disposable Postgres; published copy survives replacement; all seven pairs listed. |
| `tests/test_market_lab_gate2.py` | 130, 145 | Research fixture supplies and checks its room memory context. |
| `tests/market_lab_ml4/review-results.txt` | 1 | Exact local commands, results, startup excerpt and the initial corrected test failure. |
| `tests/market_lab_ml4/HANDOFF.md` | 1 | This follow-up and honest CI limitation. |

### Local proof and CI limitation

Code head tested: `76a727b308eb86b3bf5f166476796435b2402626`. Later commits only
record this evidence. See [review-results.txt](review-results.txt) for commands.

- Focused ML4 unit tests: **30 passed**.
- Memory/publication tests with disposable Postgres: **8 passed, none skipped**.
- Market Lab selection with the memory test database: **239 passed, 6 skipped**.
  The six skips are other opt-in service/database checks. Two real-Tank tests
  were then run explicitly with `DATABASE_URL`: **2 passed**.
- CI's exact Ruff command, changed-agent Ruff check, and diff check: passed.
- Actual Tank `main:app` started and the existing warning job completed locally.
  The local publisher test uses Hermes's real save/forget/list/publication code,
  its existing fake encoder and SQL store. No model weights or provider used.

The requested named test **did execute locally**:

```text
tests/test_market_lab_ml4_memory.py::test_private_save_fake_encoder_founder_only_publish_and_other_tenant_sql_reads PASSED [100%]
```

**This is not a CI log line. Review fix 5 is not complete.** The public
[Tank job for code head 76a727b](https://github.com/Tervory-AI/tervory-tank/actions/runs/41650676148/job/125967924379)
was in progress when inspected and displays **“Sign in to view logs”**. No login,
GitHub API, CI rerun or empty push was used. The required CI test line and completed
Tank result for the final pushed head cannot be verified from this session.
[PR checks](https://github.com/Tervory-AI/tervory-tank/pull/606/checks) show the
current head; later evidence-only pushes supersede earlier runs normally. CI's
Tank job remains the full-suite result of record, with no pass claimed here.

### Decisions I made

- An absent memory record is inserted directly. An existing changed record is
  replaced using the approved exact-ID forget operation; a failed forget never
  proceeds to save. Identical claims retain the existing evidence unchanged, as
  required by the instruction to skip both mutations.
- A missing-date count is diagnostic log data only. There is no new page text or
  API field. Dates must parse before contributing to the weather series.
- Tests stay offline and run on the managed cloud machine with a disposable
  local database. Published memory is compared before and after replacement,
  including its platform owner, claim and ID. Other-tenant private reads stay empty.
- Item 6 stays untouched. No new route or command tool, Hermes edit, approved
  skill edit, production mutation, page change, or founder-browser claim.

## Founder encoder ruling

The founder explicitly allowed Hermes's existing pinned in-container encoder for
indexing a saved record through `MemoryClient.remember → Records.save`.
“No model call” here forbids Tank's model gateway, providers, and models deciding
or writing claims. Tests fail on the chassis model gateway, inject #410's fake
encoder for SQL integration, and download no model. There is no SQL-only write
path, embedding search or recall query. Published reads use `GET /records?tier=platform`
with the requesting tenant; private records use the same SQL listing with client tier.

## Resulting behavior

- FFL supply, demand, population, costs, bindings and warning plans are data in
  `supply_map.json`. Both original plans matched byte-for-byte before the explicit
  additions; frozen SHA-256 checks retain that proof. Loading rejects unknown or
  missing fields, duplicate JSON keys, invalid thresholds, unknown pair sources,
  and any attempt to store FRED costs.
- New pairs: NYNJ loaded imports (drop), World Bank lead/copper/zinc (surge),
  and national stored NOAA alert count (surge), each followed by the existing
  watched-availability drop. Existing thresholds, source titles and outcome words
  are reused. No proposed pair was omitted for missing words. LegiScan and price
  outcomes remain excluded.
- Weather counts use existing stored severe_weather events, deduplicating one
  alert's state rows and repeated snapshots. Each count retains event citations;
  missing collection days remain missing. No additional fetch occurs.
- Changed pair summaries produce private `warning_pattern` records containing
  only pair/source/ref/downstream identifiers, lag statistics, episodes, hits and
  hit rate. The latter is rounded to six decimals so the unchanged publication
  scrubber does not mistake a long repeating decimal for a phone number.
  Warning evidence commits first. Pair-stable record IDs and a flag in the existing
  pair summary handle retries without another table. Changed claims use the
  approved scoped forget-then-save path above. No automatic publication.
- Existing founder policy, de-identification and publish routes are unchanged.
  Published records deliberately lose private warning-document IDs through #410's
  existing scrubber; another tenant never receives those private source IDs.
- The cohort gate shares calibration's resolved-original qualification and
  deduplication. It opens at 90 elapsed days from the earliest qualifying resolved
  original's issue date. It returns days covered, resolved count and closed reason.
  Missing, premature, unmeasurable and foreign outcomes cannot open it. No override.
  Stored answer facts and explicitly supplied research passages reject closed
  prediction/warning citations and missing or foreign internal source documents.

## NWS terms recheck

Checked on 3 November 2026: [NWS API documentation](https://www.weather.gov/documentation/services-web-api).
NWS permits free use of its API data for any purpose and currently requires a
User-Agent rather than a key. This job consumes stored alerts only. `NOAA_TOKEN`
remains associated with climate data; no key handling changed.

## Original implementation validation (before review fixes)

Exact verification commands, captured outputs and corrected earlier failures are
in [results.txt](results.txt).

- Final requested Market Lab selection: **234 passed, 7 skipped in 32.66s**.
- Latest new ML4 checks: **33 passed, 1 skipped in 6.35s**.
- Memory/security regression selection: **17 passed, 19 skipped in 25.01s**.
- Changed Python files: Ruff E9/F passed; `git diff --check` passed.
- Skips are existing opt-in database/service checks and the new disposable-SQL
  publication test without `MEMORY_TEST_DATABASE_URL`. That test uses the existing
  fake encoder fixture and runs in CI's configured disposable database.

Per the founder's ruling, CI's `tank` job is the full-suite result of record.
**CI: pending, no result claimed.** No PR or branch Actions run existed when checked:

```sh
gh pr list --head codex/market-lab-ml4 --state all --json number,state,url
# []
gh run list --branch codex/market-lab-ml4 --limit 10 --json databaseId,event,status,conclusion,url
# []
git cat-file -e origin/main:tank/market_lab_ml3.py 2>/dev/null
# exit 128: ML3 file absent from main
```

No dependencies were installed during the original implementation retry; the review
follow-up installed a separate cloud virtual environment, recorded above. Tests used the already installed
Python environment at `/workspace/codex-market-lab-ml3/.venv/bin/python`. Every
finished file was committed and pushed separately; no push failed. Before each
push the exact merge/push sequence was:

```sh
git fetch origin main && git merge --no-edit origin/main && git push origin HEAD
```

The initial data commit merged main without conflicts; subsequent merges reported
already up to date. No merge conflict or production command occurred.

## File and line manifest

Compared with main `b2fa83bdfca6d5788d12e11ce5230da1463a3621`. Numbers are changed-hunk starts.

| File | Lines |
| --- | --- |
| `agents/_chassis/chassis/memory.py` | 33, 41, 82 |
| `agents/market_lab/app.py` | 146, 148, 168 |
| `agents/market_lab/core/evidence.py` | 211, 338 |
| `agents/market_lab/core/jobs.py` | 324 |
| `agents/market_lab/core/patterns.py` | 1 |
| `agents/market_lab/core/predictions.py` | 59, 71, 87, 122 |
| `agents/market_lab/core/warning_store.py` | 42, 48, 89 |
| `agents/market_lab/core/warnings.py` | 37, 97, 117, 215 |
| `agents/market_lab/engines/ffl/engine.py` | 23, 27, 29, 125 |
| `agents/market_lab/engines/ffl/supply_map.json` | 1 |
| `agents/market_lab/engines/ffl/warnings.py` | 8 |
| `tests/market_lab_ml4/results.txt` | 1 |
| `tests/test_market_lab_ml4.py` | 1 |
| `tests/test_market_lab_ml4_memory.py` | 1 |

## Remaining work and founder proof

1. After the founder merges ML3 to main, merge main into this same branch and
   implement item 6 using ML3's existing READS set, reads route, room handler,
   command tools/adapters and zero-cost receipts. Do not create another route.
2. Run ML3's tests with the Market Lab selection after that merge. Record the
   actual final-head CI `tank` job URL, completed result and named publication-test
   line. The current review evidence limitation is recorded above. Compare any
   failures with main before changing unrelated code.
3. After deployment, the founder must supply actual `/chats` screenshots showing
   patterns and their source documents, explicit founder publication and another
   tenant's matching published pattern, closed gate states, and a brief with no
   closed-cohort prediction citations. **No founder screenshots exist yet.** No
   fixture was put on a live screen, no session was impersonated, and no browser
   acceptance is claimed.
