# Zenas — the legal Squad member (plan, phases Z1–Z6)

**What Zenas is:** a legal research and drafting agent for **commercial, trade, international shipping, contracts, corporate, IP/trademark, employment, property and regulatory compliance** work, in **two jurisdictions: the United States and South Africa**. **No criminal law.** Every client-facing output is reviewed and signed off by a licensed lawyer in that jurisdiction (the founder's US and SA panels) before the client sees it. Zenas drafts and researches; the lawyer advises.

Read `AGENTS.md` first. Rule 9 applies with one more layer: **core legal skills know no jurisdiction.** US and SA are engines (`agents/zenas/engines/us/`, `.../za/`) holding their sources, court rules, citation formats, clause variants and terminology. A third country later is a third engine.

Depends on C6 (chassis) and C7 (Hermes).

## Two regions, no personal data crossing
South African work runs on infrastructure in South Africa; US work runs in the US. Same code, same skills, deployed twice; the region is configuration (`TANK_REGION=za|us-east`), never a fork.
- **Each region has its own** Postgres, Redis, Qdrant/Hermes, Tank, Zenas box, file storage and backups. A ZA tenant exists only in the ZA region; nothing replicates between regions.
- **Model calls from ZA:** prompts with personal information go only to models running in South Africa (an open-weight model on our own SA server, or a provider's South African region where one offers the model). Prompts sent to providers outside SA carry placeholders, never the identifiers (see `zenas.pii`). Tank in the ZA region enforces this per tenant: a prompt still containing a detected identifier is refused for any non-SA provider.
- **Every other vendor counts too:** sign-in (Clerk is US-hosted: ZA tenants need either consent wording that covers it or self-hosted sign-in in the ZA region), email, error tracking, logs and backups must stay in SA or carry no personal information.
- **Public legal sources** (statutes, judgments, court rules) contain no client data; the ZA pool is built on the ZA server, the US pool on the US server.
- Coolify may manage both servers from one dashboard (it stores deploy settings, not client data).

## Non-negotiables
1. **Scope gate first.** Every request passes `zenas.scope` before any other skill. Criminal matters (defence, prosecution, police matters, bail, sentencing, criminal charges) are refused with a referral message and never researched. Regulatory work that *carries* criminal penalties (export controls, customs, sanctions, firearms import/export permits) is in scope as **compliance**, but always flagged "lawyer must review".
2. **No uncited law.** Every statement of law in an output links to a document in the knowledge pool. `zenas.cite_check` runs on every output: a citation that does not resolve to a pool document, or a quote that does not match the source text word for word, blocks delivery.
3. **Lawyer sign-off before delivery.** Outputs go to a review queue; only a reviewer with the matching jurisdiction tag can release them. The release records who, when, their bar/admission number and what they changed.
4. **Client matters are confidential.** Matter data lives per tenant (own schema rows + Hermes memory per tenant). Legal tenants may only route to providers on their allowed list (no China-hosted providers; providers that do not train on API data). No matter text in logs.
5. **Licences respected.** Every source in the pool records its licence and terms. A source whose terms are unknown or forbid bulk use is not ingested; it can be linked, not copied. Copyrighted model texts (e.g. the UCC official text and comments, ICC Incoterms) are referenced, never stored in full; the enacted statute text is used instead.
6. **Consent and personal information (South Africa, POPIA).** A ZA tenant cannot open a matter until its user has given recorded consent: what is processed, why (only the work requested), that data is processed outside South Africa (US servers and model providers) and under which safeguards. Store each consent with the exact wording version, user, timestamp and IP; a change of wording requires fresh consent. Personal identifiers found in matter documents (ID and passport numbers, full home addresses, bank details, phone numbers, dates of birth) are detected on upload, stored encrypted, used only for that matter, masked in model prompts unless the task needs them, and never written to Hermes memory, golden cases, the ledger or logs. Deleting a matter or a tenant deletes them. The same controls apply to US tenants.
7. **Not legal advice to the public.** UI copy says Zenas prepares drafts and research for review by a licensed lawyer.

## Z1 — Zenas box, matters, scope gate
- Room per `docs/cursor/ROOMS.md`: `agents/zenas/` own compose, corridor `tervory-gw-zenas`, login `agent_zenas`, key `TANK_KEY_ZENAS`; the knowledge pool package (`agents/zenas/pool/`, Z2) is imported, not rewritten.
- `agents/zenas/` from the template. Tables in `agent_zenas`: `matters (id, tenant_id, jurisdiction us|za|both, area, title, parties jsonb, status, created_by)`, `documents (matter_id, kind, version, body, sources jsonb, state draft|in_review|released|rejected)`, `reviews (document_id, reviewer, jurisdiction, admission_no, decision, changes, ts)`.
- Consent: table `consents (tenant_id, user_id, jurisdiction, wording_version, text_hash, ts, ip)`; matters for ZA tenants are refused until a current consent exists. Personal-identifier detection (`zenas.pii@1.0.0`, pure code with SA ID-number checksum and US SSN/passport patterns) runs on every upload; matches stored encrypted in `pii (matter_id, kind, ciphertext)` and replaced by placeholders in model prompts.
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
- Consent wording for ZA (and US) tenants, approved by SA counsel: covers processing for the requested work and cross-border processing (US servers, model providers). SA counsel to confirm how counterparties' personal information inside client documents is covered, and that Tervory's Information Officer is registered with the Information Regulator.
