# Zenas 12-hour build: one lead, three builder threads

> Written 14 Oct 2026, 18:10 PT. Window: **18:30 PT 14 Oct → 06:30 PT 15 Oct**. Founder merges in the morning and plugs in the feeds in the afternoon. Phases and rules: `docs/cursor/Z-BUILD-ALL.md`. This file sets who does what, when.

## Roles
- **Lead (Grok):** never writes code. Launches nothing itself; tells the founder which prompt to paste where. Reviews every PR with the reviewer checklist (`docs/cursor/prompts/REVIEWER.md`) and posts the report as a PR comment ending APPROVE or CHANGES NEEDED. Keeps the status table. Catches clashes between threads.
- **Thread A — Library:** everything under `agents/zenas/pool/` (US and SA sources, loaders, citation graph, pool status API).
- **Thread B — Regions and pages:** ZA box, Tank region checks and proxy, court deadlines, Workspace pages, feeds switchboard.
- **Thread C — Brain:** the legal ladder (rule cards, decided cases as worked matters, matching, apply, memos, training pairs), then drafting and contract review.

Lanes never share files. **Change from Z-BUILD-ALL:** the `za` catalogue entries move from phase 2 (B) to phase 3 (A), so only Thread A ever edits `agents/zenas/pool/`.

## Timeline (PT)

| Hours | Thread A — Library | Thread B — Regions and pages | Thread C — Brain | Lead |
|---|---|---|---|---|
| 18:30–19:00 | start phase 1 | start phase 2 | start phase 4 | reads all briefs, posts the lane table |
| 19:00–22:30 | **Phase 1** US library: USLM, eCFR, HTSUS, rules, CourtListener (bulk + API), CAP, state statutes, eyecite graph, pool-loader | **Phase 2** ZA box: `docker-compose.za.yml`, `litellm/config.za.yaml`, Tank region checks (no `za` catalogue edits) | **Phase 4a** rule cards, retrieve, cite_check, stale-on-change | checks each thread every hour for clashes |
| 22:30–23:00 | PR 1 open | PR 2 open | keeps going | **reviews PR 1 and PR 2** |
| 23:00–02:30 | **Phase 3** SA library: `za` catalogue, SAFLII, Laws.Africa API, gov.za/Gazette, court rules, SA citation parser | **Phase 6a** `zenas.deadlines` (pure code) + Tank `/v1/zenas/*` proxy | **Phase 4b** case_facts (judgments → worked matters), match, apply ladder, compose, training pairs | fixes requested go back to A or B |
| 02:30–03:00 | PR 3 open | keeps going | PR 4 open (stacked on PR 1 if needed) | **reviews PR 3 and PR 4** |
| 03:00–06:00 | **Pool status API** for the switchboard (per source: key name, key set yes/no, counts, last load, errors, start a load); then fixes from reviews | **Phase 6b** Workspace pages: Matters, Review, Zenas feeds (stacked on PR 4 for the Review page's data) | **Phase 5** drafting + contract review, Word tracked changes, templates | reviews fixes as they land |
| 06:00–06:30 | final fixes | PR 6 open | PR 5 open | **reviews PR 5 and PR 6**, posts the summary |

## Merge order for the founder (morning)
1. PR 1 (US library) → 2. PR 2 (ZA box) → 3. PR 4 (brain) → 4. PR 3 (SA library) → 5. PR 5 (drafting) → 6. PR 6 (pages and feeds).
After each merge: the deploy says **Success** and Tank stays up before the next merge (Lead confirms).

## Lead's summary at 06:30 must include
Every PR link with APPROVE / CHANGES NEEDED; the merge order; every key name to add in Coolify (US `agent-zenas`, ZA app); anything the founder must decide; what was not finished.
