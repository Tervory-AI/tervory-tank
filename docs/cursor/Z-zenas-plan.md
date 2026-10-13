# Zenas — the legal Squad member (plan, phases Z1–Z6)

**What Zenas is:** a legal research and drafting agent for **commercial, trade, international shipping, contracts, corporate, IP/trademark, employment, property and regulatory compliance** work, in **two jurisdictions: the United States and South Africa**. **No criminal law.** Every client-facing output is reviewed and signed off by a licensed lawyer in that jurisdiction (the founder's US and SA panels) before the client sees it. Zenas drafts and researches; the lawyer advises.

Read `AGENTS.md` first. Rule 9 applies with one more layer: **core legal skills know no jurisdiction.** US and SA are engines (`agents/zenas/engines/us/`, `.../za/`) holding their sources, court rules, citation formats, clause variants and terminology. A third country later is a third engine.

Depends on C6 (chassis) and C7 (Hermes).

## Non-negotiables
1. **Scope gate first.** Every request passes `zenas.scope` before any other skill. Criminal matters (defence, prosecution, police matters, bail, sentencing, criminal charges) are refused with a referral message and never researched. Regulatory work that *carries* criminal penalties (export controls, customs, sanctions, firearms import/export permits) is in scope as **compliance**, but always flagged "lawyer must review".
2. **No uncited law.** Every statement of law in an output links to a document in the knowledge pool. `zenas.cite_check` runs on every output: a citation that does not resolve to a pool document, or a quote that does not match the source text word for word, blocks delivery.
3. **Lawyer sign-off before delivery.** Outputs go to a review queue; only a reviewer with the matching jurisdiction tag can release them. The release records who, when, their bar/admission number and what they changed.
4. **Client matters are confidential.** Matter data lives per tenant (own schema rows + Hermes memory per tenant). Legal tenants may only route to providers on their allowed list (no China-hosted providers; providers that do not train on API data). No matter text in logs.
5. **Licences respected.** Every source in the pool records its licence and terms. A source whose terms are unknown or forbid bulk use is not ingested; it can be linked, not copied. Copyrighted model texts (e.g. the UCC official text and comments, ICC Incoterms) are referenced, never stored in full; the enacted statute text is used instead.
6. **Not legal advice to the public.** UI copy says Zenas prepares drafts and research for review by a licensed lawyer.

## Z1 — Zenas box, matters, scope gate
- `agents/zenas/` from the template. Tables in `agent_zenas`: `matters (id, tenant_id, jurisdiction us|za|both, area, title, parties jsonb, status, created_by)`, `documents (matter_id, kind, version, body, sources jsonb, state draft|in_review|released|rejected)`, `reviews (document_id, reviewer, jurisdiction, admission_no, decision, changes, ts)`.
- Skill `zenas.scope@1.0.0` (Tank, cheap model + rules): returns `{in_scope, area, jurisdiction, criminal: bool, needs_lawyer: bool, reason}`. Evals: at least 30 cases incl. 10 criminal ones that must be refused, 5 regulatory-with-criminal-penalty that must be in scope + flagged, and mixed US/SA cases.
- **Done when:** a criminal question can never reach any other Zenas skill (tested), and evals pass 100% on the criminal cases.

## Z2 — Knowledge pool: ingestion framework + United States
- `agents/zenas/pool/`: one adapter per source → common document model `{id, jurisdiction, level federal|state|national|provincial|international, body, kind statute|regulation|case|court_rule|treaty|form|guidance, citation, title, date, effective_from, effective_to, status, url, licence, text, sections[]}`. Keep every version (laws change; answers must be "as at" a date).
- Chunk by structure (section, subsection, paragraph), never by blind length. Store in Postgres (text + metadata + full-text index) and Qdrant collection `law_<jurisdiction>` (shared knowledge, not per tenant). Embeddings computed locally (C7's embedding service; a legal-tuned open model may replace it later).
- US sources, first wave (check and record each licence before ingesting):
  - US Code and CFR via govinfo.gov / eCFR APIs; Federal Register for changes.
  - Trade/shipping: 19 CFR (customs), HTSUS (USITC), EAR 15 CFR 730–774, ITAR 22 CFR 120–130, OFAC 31 CFR 500s, COGSA (46 USC 30701 note), Carmack (49 USC 14706).
  - International: CISG and UNCITRAL texts (UN, public).
  - Case law: CourtListener (Free Law Project) API, starting with federal appellate + Delaware/New York commercial decisions; Caselaw Access Project bulk data for history.
  - Court rules: Federal Rules of Civil Procedure and Evidence; local rules of the districts the panel practises in.
  - State law: start with Delaware (DGCL), New York and Texas commercial statutes as enacted; UCC Articles 1, 2, 9 as enacted by those states.
- A nightly update job per source; a `pool_status` endpoint (source, documents, last update, licence).
- **Done when:** the federal titles above and the first state statutes are searchable by citation and by meaning, with version dates; a re-run adds new versions without duplicating.

## Z3 — Knowledge pool: South Africa
- Same framework, engine `za`. First wave (check and record each licence/terms of use before ingesting; SAFLII and Laws.Africa terms especially):
  - Legislation: Companies Act 71 of 2008, Consumer Protection Act, POPIA, Customs and Excise Act, International Trade Administration Act, Electronic Communications and Transactions Act, Labour Relations Act / BCEA, Trade Marks Act, Conventional Arms Control Act and Firearms Control Act **as regulatory compliance only**; Government Gazette notices for changes.
  - Case law: SAFLII judgments (SCA, Constitutional Court, High Court commercial matters), within its terms.
  - Court rules: Uniform Rules of Court (High Court), Magistrates' Courts Rules, practice directives of the divisions the panel uses.
  - SA citation formats in the `za` engine.
- **Done when:** same tests as Z2 for SA.

## Z4 — Research and reasoning skills (core, jurisdiction-free)
- `zenas.retrieve@1.0.0`: hybrid search (exact citation + full text + meaning), filtered by jurisdiction, level, kind and "as at" date; returns passages with citations.
- `zenas.cite_check@1.0.0` (pure code): every citation resolves; every quotation matches the source text; flags superseded versions.
- `zenas.issue_spot@1.0.0`: facts in → issues, applicable law (retrieved, cited), open questions for the lawyer.
- `zenas.memo@1.0.0`: research memo in IRAC form, citations inline, a "confidence and gaps" section.
- `zenas.plain_language@1.0.0`: rewrites a memo or clause for a business reader without changing its legal effect (the lawyer reviews both).
- Evals: questions with known answers written by the panel (the founder's lawyers write 20 per jurisdiction); a planted fake citation must always be caught.

## Z5 — Documents: drafting and review
- Clause library per engine (`clauses (id, jurisdiction, kind, text, fallback_positions, notes, approved_by)`), seeded only with clauses the panel approves.
- `zenas.draft@1.0.0`: contract from a term sheet using approved clauses only; marks every non-library sentence for review. First templates: NDA, supply agreement, distribution agreement, sale of goods (domestic and CISG), freight/shipping terms, services agreement, SA/US cross-border agency agreement.
- `zenas.review@1.0.0`: reviews a third-party contract against a playbook (per tenant): deviations, risk level, suggested redlines with the clause that would replace each.
- Output as .docx with tracked changes for redlines.

## Z6 — Court rules engine and the lawyer review console
- `zenas.deadlines@1.0.0` (pure code, no model): computes deadlines from a trigger date under FRCP 6 and the SA Uniform Rules (court days, public holidays per jurisdiction, dies induciae), with the rule cited for every step. Evals against the panel's worked examples.
- Workspace pages: **Matters** (client) and **Review** (panel only: Clerk role `reviewer` + jurisdiction tags). Review shows the draft beside its sources, lets the lawyer edit, approve or reject, and records the sign-off. Approved edits feed Tank's golden cases so Zenas learns the panel's standard.

## What the founder provides
- Reviewer accounts for the US and SA panels (name, admission/bar number, jurisdictions).
- 20 test questions with model answers per jurisdiction, written by the panel (Z4 evals), plus worked deadline examples (Z6).
- The firm's preferred positions for the first templates (Z5 playbooks).
- A decision, with SA counsel, on where SA client matter data is stored (POPIA cross-border rules) before the first SA client matter.
