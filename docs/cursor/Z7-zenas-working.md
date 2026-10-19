# Z7 — Make Zenas work end to end: no lawyer gate, self-tested on decided cases, loaders fixed

> Written 18 Oct 2026, 19:05 PT. Founder decision: Zenas must work first. Lawyer approval is **not** a gate. Reviewing is an option the founder can switch on later.

**Files you may change:** `agents/zenas/` (core, pool, app, schema additive), `tank/skills/zenas.*` (new versions only for approved skills; candidates may be edited), policy rows appended to `tank/schema.sql` (additive), `workspace/app/zenas/` and `workspace/app/review/` (UI for the switch and the test results), `workspace/app/api/zenas/` (new routes only), new tests. Every schema change tested on an empty database, re-applied, and on a database with the current main schema and agent roles.

## 1. No lawyer gate (a founder switch, default off)
- `ZENAS_REVIEW=off|on` per region, default **off**.
- **Off:** rule cards that pass `zenas.cite_check` (every citation resolves in the pool, every quote matches the source word for word) become `active` automatically and are reused at once. Memos, drafts and reviews are delivered straight to the matter. Each output records `reviewed: false`.
- **On:** the existing review queue and release flow apply, unchanged.
- Hard checks stay on in both modes: the scope gate (no criminal law), ID protection, and cite-check (an output with a citation that does not resolve or a quote that does not match is never delivered; it is retried or returns "could not verify").

## 2. Zenas tests itself on decided cases (no lawyers needed)
- **Held-out case test (`zenas.selftest`):** take decided cases from the pool that Zenas has never used (20% of cases are held out by a stable hash and never used for reuse or training). For each: give Zenas only the facts as the court stated them and the question; Zenas runs the full ladder (rule card, match, apply, compose); compare its element findings and outcome with what the court held. Score per area and per jurisdiction: outcome agreement %, element agreement %, citations valid %, cost per case.
- **Public benchmarks:** run the legal-reasoning tasks from LegalBench (and similar public sets found in the Zenas research) that fit the launch areas; store scores.
- Results feed Tank's graduation: a cheaper route takes over only when it matches on held-out cases. Show the scores on the Zenas page (founder view) and on `/skala/gold`.
- Runs nightly and on demand, low priority.

## 3. Fix the loaders (found on the first live load, 18 Oct)
- **eCFR fails with HTTP 406 Not Acceptable:** send the correct `Accept` header (JSON or XML as the endpoint expects) and a descriptive `User-Agent`; retry with backoff.
- **FRCP loads as 1 document:** load every rule (FRCP, FRE, FRAP) as its own document with sections, not one blob; same check for every source that comes back with fewer than 10 documents.
- **Federal Register loads 0 documents:** fix the query so it returns the notices for the tracked CFR parts.
- Every source with no key must load real content on "Load now"; a test per source on a saved real response proves the parser handles it.
- Keyed sources (`GOVINFO_API_KEY`, `COURTLISTENER_API_TOKEN`, `NY_OPENLEG_API_KEY`, `LAWS_AFRICA_API_TOKEN`) stay skipped until the key is set.

## Done when
CI green; with `ZENAS_REVIEW=off` a question on loaded law returns a cited memo with no human step (tested); a planted bad citation is never delivered (tested); the self-test runs on fixture held-out cases and reports outcome and element agreement (tested); eCFR, FRCP, FRE, FRAP and Federal Register parsers load fixture copies of real responses into many documents (tested).

## After merge (Claude)
Press Load now on every keyless source, start the first self-test run, and report the scores to the founder.
