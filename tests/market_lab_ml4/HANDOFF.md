# Market Lab ML4 handoff — partial, waiting for ML3

Branch: `codex/market-lab-ml4`. Checkout: `/workspace/codex-market-lab-ml4`.
Prepared 3 November 2026 (Pacific). Founder merges; Claude opens the PR.

Items 1–5 are implemented and locally checked. Item 6 has NOT started: ML3 is
not on main. This is not founder browser acceptance and not a completed ML4 job.
No page, card layout, visible wording, credential setting, keyed feed, production
row, schema, approved skill package or Hermes implementation changed.

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
  Warning evidence commits first. Stable record IDs and a flag in the existing
  pair summary handle retries without another table. No automatic publication.
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

## Validation

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

No dependencies were installed during this retry. Tests used the already installed
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
   actual PR CI `tank` job URL and result, comparing failures with main before
   changing unrelated code.
3. After deployment, the founder must supply actual `/chats` screenshots showing
   patterns and their source documents, explicit founder publication and another
   tenant's matching published pattern, closed gate states, and a brief with no
   closed-cohort prediction citations. **No founder screenshots exist yet.** No
   fixture was put on a live screen, no session was impersonated, and no browser
   acceptance is claimed.
