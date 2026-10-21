# Z11: South African case law from the official court sites, full back catalogue

> Written 19 Oct 2026, 15:50 PT. Founder: South Africa comes first (no Harvey-like product there, and a smaller corpus is cheaper to train on). Live on the ZA box today: 91 decided cases in total (ConCourt 13, SCA 9, CAC 15, Special Tribunal 15, SARS Tax Court 13, Labour Court 8, LAC 7, CompTrib 6, Land Court 3, OCJ High Court 2). SAFLII returns a challenge page, so it gives 0. The loaders only read each site's newest listing page.

**Files you may change:** `agents/zenas/pool/adapters/za_*.py` (the existing official-court adapters), `agents/zenas/pool/catalogue.py`, `agents/zenas/pool/nightly.py`, `agents/zenas/pool/schema.sql` (additive), tests with saved real listing pages and judgments as fixtures.

## Do
1. **Walk each official site's whole archive**, not just the newest page: every year and every listing page the site publishes, for ConCourt, SCA, CAC, Competition Tribunal (judgments only, not merger approval letters), SARS Tax Court, Labour Court, Labour Appeal Court, Land Court, Special Tribunal, and the OCJ High Court judgments pages for every division that publishes them.
2. **Same rules as today:** official government or court hosts only; no SAFLII until AfricanLII/UCT says yes in writing; criminal captions ("S v …", DPP, NPA) dropped at load; one request at a time per host, a descriptive User-Agent, backoff on errors, a challenge page logged and never stored; unchanged documents not re-downloaded (hash).
3. **Resumable and capped:** remember the last page done per site and year; `ZENAS_ZA_ARCHIVE_MAX` (default 2,000 documents per run) so one press cannot fill the disk. Runs as a FIX-4 background job.
4. **Feeds page:** per site, years covered, documents loaded, skipped by reason (criminal, not a judgment, unchanged, challenge page).
5. **ZA box only.** Nothing crosses to Boston.

## Done when
CI green; saved real archive pages for two sites walk past page one and load older judgments (tested); a criminal caption and a merger approval letter are skipped (tested); a resumed run adds no duplicates (tested). After merge Claude presses Load on each site on the ZA box, then runs Convert and reports counts.
