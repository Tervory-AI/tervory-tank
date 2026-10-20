# Z8: Turn loaded decided cases into worked matters, so the self-test has cases

> Written 19 Oct 2026, 03:20 PT by Claude, from the first live self-test. Both regions ran the held-out test on **0 cases**: decided cases are in the pool (SA: ConCourt 10, SCA 6, CAC 8, Special Tribunal 8 and more; US: CAP 9, more once CourtListener is keyed), but nothing turns them into `agent_zenas.worked_matters`. Today a worked matter is only made by a direct `POST /cases/facts` call.

**Files you may change:** `agents/zenas/core/` (a new `convert.py` and the call sites), `agents/zenas/pool/nightly.py`, `agents/zenas/app.py` (one new founder route), `agents/zenas/schema.sql` (additive), `tank/main.py` (only add `cases/convert` to `_ZENAS_PATH`, and to the ZA founder-link allow-list with `home_region=za`), `workspace/app/zenas/feeds/` and `workspace/app/api/zenas/` (a "Convert cases" button and its route), tests.

## Do
1. **Convert job, per region.** For every decided case in this box's pool that has no worked matter yet, run `zenas.case_facts` (facts as the court stated them, the question, the elements, the holding) and store a worked matter with its citation. The same stable hash as Z7 marks 20% `holdout`. US cases only on Boston, SA cases only on the ZA box; nothing crosses.
2. **When it runs:** nightly after the pool load, low priority (batch), at most N cases per night (`ZENAS_CONVERT_MAX`, default 200), and on demand from a founder button on `/zenas/feeds` ("Convert cases", per region).
3. **Quality gate:** a worked matter is stored only if `zenas.cite_check` passes on its citations. Failures are logged with the reason and retried next night.
4. **Report:** `/zenas/feeds` shows per region: decided cases loaded, converted, held out, failed.

## Done when
CI green; fixture decided cases become worked matters with about 1 in 5 held out (tested); a US conversion never reads an SA case and the reverse (tested); a case that fails cite-check is not stored (tested); after merge Claude presses Convert in both regions and runs the self-test again with real cases.
