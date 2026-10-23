# Zenas: the full breakdown, and live by Sunday evening (25 Oct)

> Written by Claude, Fri 23 Oct 2026, 15:10 PT. The founder: "Zenas must be live by Sunday, end of story." This is what Zenas is, what is built, what's live and what's left, with an owner and a time for every step. It runs alongside `docs/ops/GROK-48H-2026-10-23.md` as lane G there.

## 1. What Zenas is
- **A legal research and drafting agent** for civil work: commercial, trade and shipping, contracts, corporate, IP, employment, property and regulatory compliance.
- **Two jurisdictions:** the United States and South Africa.
- **No criminal law, ever.** The test: if someone's guilt, liberty or criminal defence is at stake, Zenas doesn't take it. A victim's own civil claim is in.
- **A licensed lawyer signs off every client output.** Zenas drafts and researches; the lawyer advises.
- **Two regions with no client data crossing between them:** US work runs on Boston and SA work on the ZA box. Same code; the region is configuration.

## 2. What is built and merged (36 PRs, 14–20 Oct)

| Area | What works | PRs |
|---|---|---|
| **The room and safety** | Zenas's own sealed room, the scope gate (criminal refused, not-yet-offered areas refused politely), detection of personal details, and the region lock (a ZA client can't be opened on Boston, and the reverse) | #37 #39 #63 #68 #69 |
| **US law library** | GovInfo, eCFR, Federal Register, CourtListener (with bulk reads), UNCITRAL and CISG | #66 #72 #87 #164 #178 |
| **SA law library** | National Acts and Gazette regulations from gov.za, and each official SA court archive. The SAFLII loader is built but **off until SAFLII gives written permission** | #155 #171 #172 |
| **The legal ladder** | Law worked out once as rule cards, facts applied cheaply, region-locked client facts | #55 #185 |
| **Decided cases as worked matters** | Each loaded judgment is turned into a worked example, with reasons shown when one fails | #160 #161 #168 #169 #170 #175 |
| **SA precedent (Z12)** | Full judgments, court weight (what binds which court), the citation trail, and a gate that stops made-up cases, checked nightly | #204 #206 |
| **Drafting and review** | Clause library, contract drafts from approved clauses, review of a third party's contract, Word redlines | #59 |
| **Deadlines** | FRCP 6 and the SA Uniform Rules, with the rule cited at every step, including dates from sheriff service | #53 #122 #187 |
| **Pages** | Matters, Review (the lawyer console), Feeds (Load now, last load status), deadlines panel, and a Moot Court placeholder page | #53 #133 #136 #162 |
| **Learning** | Held-out self-test, a learning register, gold candidates for training | #125 #148 #189 |

## 3. What is live right now
- **Boston (US region):** Zenas's room is deployed (`agent-zenas`) and the Workspace Zenas pages are behind sign-in.
- **ZA region: down.** The ZA host was dropped on 22 Oct and the move to Hetzner is in progress. `ZA_OFFLINE=true` stops deploys there. So **no South African Zenas is live**, and the SA law library isn't loaded anywhere.
- **Moot Court:** only a placeholder page. MOOT-1 (the AI judge) isn't built yet.

## 4. "Live by Sunday" means these six things

| # | Live means | Owner | When |
|---|---|---|---|
| 1 | **US Zenas works end to end on Boston.** A US civil question passes the scope gate, opens a matter and gets a cited answer and a draft. A US reviewer releases it. A criminal question is refused. | Grok tests it; the founder gives reviewer accounts | Sat AM |
| 2 | **The ZA box is up on Hetzner** with `tervory-tank-za` and `agent-zenas-za`, and `ZA_OFFLINE=false` | Grok and the founder (Grok plan, lane C) | Sat PM |
| 3 | **The SA law library is loaded:** gov.za Acts and regulations, the official court archives, then Convert into worked matters and rule cards. SAFLII only if permission arrives. | The founder presses **Load now** on `/zenas/feeds` (ZA); Grok watches the counts | Sat PM → Sun AM (loads run for hours) |
| 4 | **SA Zenas works end to end** on the ZA box. An SA civil question gets a cited answer that names only real cases (the Z12 gate). An SA reviewer releases it. A criminal question is refused. | Grok tests it; the founder gives SA reviewer accounts and the consent wording | Sun PM |
| 5 | **Moot Court, text edition (MOOT-1a).** A real decided civil appeal as the problem. AI counsel against AI counsel, run twice with the sides swapped (the fairness check). The AI judge questions both sides and rules with reasons, citing only verified authorities, then the reveal of what the real court held. A public watch page. | Codex builds (start now); Grok first-pass review; Claude reviews Sunday; the founder merges | PR Sat night, merge Sun evening |
| 6 | **The public Zenas page** on the new marketing site | The founder (redesign) | Sun |

**Not by Sunday, on purpose: MOOT-1b,** the speaking judge (LiveKit, voices, studio screens and clips). It needs the voice providers, a 30-minute accent test with real students, and the studio. It comes next week, on top of 1a.

## 5. Step by step

### Founder, tonight (needed for 1, 2, 4)
- [ ] **Reviewer accounts:** for each US and SA panel lawyer, their name, jurisdiction and bar or admission number. Zenas can't release anything to a client without them. A test reviewer (you) is fine for Sunday.
- [ ] **ZA consent wording,** approved by SA counsel. A ZA client can't open a matter without recorded consent. A test wording is fine for internal use.
- [ ] **Hetzner:** confirm the server is bought, with its location and size.
- [ ] **Start the MOOT-1a Codex thread** with the prompt in 6.1.

### Grok, Saturday morning: US end-to-end test (live item 1)
1. On app.tervory.com as a US test tenant: ask "Is a forum selection clause in a B2B supply contract enforceable in Delaware?"
   - **Expect:** in scope, a matter opens, an answer cites real sources (each link opens the source), and the draft goes to Review.
2. Ask a criminal question ("How do I get bail for theft?").
   - **Expect:** refused with a referral, and no research runs.
3. As the reviewer, release the draft. **Expect:** the release records who released it, when, and their admission number.
4. Check the receipts in Tank for each step. Post screenshots and receipts in the log, with no client text and no secrets.

### Grok and the founder, Saturday afternoon: the ZA box (live item 2)
- Grok plan lane C2. The app names must be exactly `tervory-tank-za` and `agent-zenas-za`.
- `za.tervory.com` points to Hetzner, Tank's `/health` on ZA returns 200, and the Zenas pool status page answers.

### Saturday evening → Sunday morning: SA library (live item 3)
1. Load in order on `/zenas/feeds` (ZA):
   1. **gov.za Acts and regulations** (Z9);
   2. **the official court archives** (Z11);
   3. **Convert** (Z8), which turns judgments into worked matters and rule cards.
2. Loads are resumable, so if one stops, press Load now again.
3. **Grok reports the counts every 3 hours:** documents per source, worked matters, rule cards, and failures with their reasons.
4. **SAFLII stays off** unless written permission has arrived.

### Sunday afternoon: SA end-to-end test (live item 4)
1. As a ZA test tenant with consent recorded, ask "Can a landlord in South Africa cancel a commercial lease for late payment without notice?"
   - **Expect:** a cited answer where every case is real and links to its full judgment, with the court weight shown, and the draft goes to Review.
2. A criminal question is refused.
3. A ZA client on Boston is refused: "needs the South Africa region".

### Sunday evening: Moot Court 1a and go-live
- **Claude reviews the MOOT-1a PR once back on Sunday.** After the founder merges, Grok checks:
  - a match runs on a fixture problem in both orders;
  - the fairness check shows;
  - the watch page opens;
  - an unpublished match returns 404.
- **Go-live list:** items 1–6 ticked, with receipts. The watchdog is green for Boston and ZA.

## 6. Prompts

### 6.1 MOOT-1a (Codex, new thread)
```
Run in the cloud only, on your own cloud machine. Never use my computer. Work without asking me: the brief, docs/cursor/CONTEXT.md and AGENTS.md are your answers; list your choices under "Decisions I made" in the PR. Stop only for a secret value, a paid service or key the brief does not name, an irreversible production action, or a conflict with a hard rule.

You are Codex. "docs/cursor/" is only the folder the briefs live in. Name your branch codex/moot-1a-text-court.

Repo Tervory-AI/tervory-tank. Read AGENTS.md, docs/cursor/CONTEXT.md, docs/cursor/ROOMS.md, docs/cursor/Z8-cases-to-worked-matters.md, docs/cursor/Z12-sa-precedent.md, then docs/cursor/MOOT-1-ai-moot-court.md, and build only the "MOOT-1a: the text edition (by Sunday 25 Oct)" section at its top.

Deadline: PR up and complete by Saturday night PT. Z12 is merged; use it directly. The ZA box is offline: build SA mode on fixtures, and run US mode on Boston.

Other lanes are running at the same time. In tank/main.py and tank/schema.sql add only route registrations and additive schema. Branch from latest main. Stay inside the brief's "Files you may change". No secrets in code, URLs, logs or tests. One branch, one PR, never push to main. Do not merge: the founder merges after review. GitHub Actions minutes reset on Saturday: until then, keep the PR as a draft with your local test results in it, and don't re-run CI in loops. End the PR with how to prove it live after deploy: which page, route or database row to check.
```

## 7. Risks to Sunday (and the answer to each)
- **The SA loads take longer than a day.** Go live with what's loaded; the library keeps growing nightly. Live item 4 needs only enough judgments for the test question's area.
- **No reviewer accounts means no client release.** Use the founder as a test reviewer on Sunday, and add the panel after.
- **CI minutes run out again.** Lane B (CI-2) merges first on Saturday.
- **The MOOT-1a review lands late on Sunday.** If Claude's review isn't done by 6 PM PT, Moot goes live on Monday. Items 1–4 don't depend on it.
