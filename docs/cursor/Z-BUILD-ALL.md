# Zenas, start to finish — the build order for one builder

> Written 14 Oct 2026, 18:05 PT. Deadline: **15 Oct 2026, afternoon PT**, so the founder can plug in the data feeds (keys) and load. One builder works through the phases in order. Read `AGENTS.md`, `docs/cursor/ROOMS.md` and `docs/cursor/Z-zenas-plan.md` first.

## How to work
- **One phase = one branch = one PR.** If a phase needs the previous one and it is not merged yet, branch from the previous phase's branch and say so in the PR ("stacked on #N; merge #N first"). PRs target `main`. Never push to `main`, never merge; the founder merges after review (`docs/RUNBOOK.md`).
- After opening a PR with CI green and "ready for review" in its description, **go straight on to the next phase**. Do not wait for review.
- Tests mock every model and every network call; fixtures only in CI.
- **Database safety (Tank went down on 14 Oct because of this):** every change to any `schema.sql` must be tested in CI by applying the whole schema (a) to an empty Postgres, (b) a second time on top of itself, and (c) on a database where the previous `main` schema already ran and the agent roles already exist. Never `ALTER ... OWNER` a sequence that belongs to a table; never assume a role is absent.
- Keys: any source with an API key is used with it. Read keys from the environment by name, list every name in `.env.example`, skip a keyed source cleanly until its key is set. No key ever in code, URLs, logs or tests.
- Data use is the founder's decision. Record each source's terms as information; never block or limit a source on your own reading. Judgments are public record and stored as published. No criminal law, ever (scope gate).

## Phases

| # | Phase | Brief | Depends on |
|---|---|---|---|
| 1 | US law library at scale | `docs/cursor/Z2b-us-law-bulk.md` | — |
| 2 | South Africa box (second region) | `docs/cursor/ZA1-za-region.md` | — |
| 3 | SA law library, live loading | this file, section 3 | 2 |
| 4 | Zenas on the ladder (rule cards, decided cases as worked matters, matching, apply, memos, training pairs) | `docs/cursor/Z4-legal-ladder.md` | 1 (fixtures are enough to build) |
| 5 | Drafting and contract review | `Z-zenas-plan.md` Z5 + section 5 below | 4 |
| 6 | Deadlines, Matters and Review pages, feeds switchboard | `Z-zenas-plan.md` Z6 + section 6 below | 4 |

## 3. SA law library, live loading (Z3b)
**Files you may change:** `agents/zenas/pool/` (new `za` adapters, catalogue entries, nightly), `docker-compose.za.yml` (the `pool-loader` service only), `.env.example`, new tests.
- Sources: SAFLII judgments (SCA, Constitutional Court, High Court divisions; commercial and civil, criminal dropped) by its bulk or page routes; Laws.Africa content API with `LAWS_AFRICA_API_TOKEN` for consolidated legislation; gov.za / Government Gazette for new Acts and notices; Uniform Rules of Court and Magistrates' Courts Rules.
- SA citation formats (neutral citations like `[2023] ZASCA 12`, law report citations like `2019 (3) SA 123 (SCA)`) parsed into the citation graph, alongside eyecite for US.
- Same loader rules as Z2b: resumable, idempotent, disk cap, low priority, versions kept "as at" dates. Runs only on the ZA box.
- **Done when:** fixture judgments and Acts load; SA citations resolve; pool status lists every `za` source with counts and key status.

## 5. Drafting and contract review (Z5)
**Files you may change:** `agents/zenas/core/` (new `drafting.py`, `review.py`, `docx_redline.py`), `agents/zenas/schema.sql` (additive: `clauses`, `playbooks`), `tank/skills/zenas.draft/1.0.0/`, `tank/skills/zenas.review/1.0.0/`, policy rows appended to `tank/schema.sql`, `agents/zenas/requirements.txt`, new tests.
- As the plan says: clause library per jurisdiction (empty until the panel approves clauses; an admin endpoint adds them); `zenas.draft` builds a contract from a term sheet using approved clauses only and marks every non-library sentence for review; `zenas.review` checks a third-party contract against a per-tenant playbook and suggests redlines.
- Both run on the ladder: reuse prior approved drafts and reviews (worked matters from phase 4) first, code next, cheapest model only for what differs.
- Output as .docx; redlines as real Word tracked changes (`w:ins` / `w:del`), opened cleanly in Word.
- First templates: NDA, supply, distribution, sale of goods (domestic and CISG), freight/shipping terms, services, SA/US cross-border agency.

## 6. Deadlines, pages and the feeds switchboard (Z6)
**Files you may change:** `tank/skills/zenas.deadlines/1.0.0/`, `tank/main.py` (a `/v1/zenas/*` proxy to the Zenas room only, like `/v1/base/*`), `workspace/app/matters/`, `workspace/app/review/`, `workspace/app/admin/` (a new "Zenas feeds" section only), `workspace/app/api/zenas/`, new tests.
- `zenas.deadlines` as the plan says (pure code; FRCP 6 and SA Uniform Rules; court days and public holidays per jurisdiction; rule cited for every step).
- **Matters** page (clients): open a matter, upload documents, see drafts and memos only after release.
- **Review** page (Clerk role `reviewer` + jurisdiction tag): draft beside its sources and matched worked matters, edit, approve or reject; approval records reviewer, admission number and changes; approved rule cards and matters feed phase 4's reuse and training pairs.
- **Zenas feeds** (founder console): every source per region with: key name, key set yes/no (never the value), documents loaded, last load, errors, and a "Load now" button that starts the pool-loader for that source. This is where the founder plugs in the feeds.

## Founder, by tomorrow
- Keys in Coolify (US app `agent-zenas`, and the ZA app once it exists): `COURTLISTENER_API_TOKEN`, `GOVINFO_API_KEY`, `LAWS_AFRICA_API_TOKEN`, plus any the research names.
- The SA server's IP and size, so Claude can add it to Coolify for phase 2.
- Reviewer accounts (name, admission number, jurisdiction) and the 20 test questions per country.
