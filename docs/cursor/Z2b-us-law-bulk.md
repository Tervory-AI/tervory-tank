# Z2b — Load US law at scale (statutes, regulations, case law)

> Written 14 Oct 2026, 17:50 PT. Builds on Z2 (`agents/zenas/pool/`, merged): the framework, licences, chunking, versions and search exist, but only ~10 sample sections are loaded. This task fills the US library. Runs on the Boston server (US region) only.

**Files you may change:** `agents/zenas/pool/` (adapters, catalogue, nightly, a new `bulk.py`), `agents/zenas/docker-compose.yml` (a `pool-loader` one-shot service only), `agents/zenas/requirements.txt`, new tests under `tests/`. Do not rewrite existing adapters; extend them.

## What to load (first full wave)
- **US Code**, whole titles relevant to the launch areas, from the official USLM XML bulk download (uscode.house.gov): Titles 9 (arbitration), 11 (bankruptcy, commercial parts), 15 (commerce and trade), 17 (copyright), 19 (customs), 35 (patents), 46 (shipping, incl. COGSA note), 49 subtitle IV (Carmack), 50 ch. 58 (export control).
- **CFR**, whole parts via the eCFR API: 19 CFR (customs), 15 CFR 730–774 (EAR), 22 CFR 120–130 (ITAR), 31 CFR 500–599 (OFAC). Nightly: Federal Register changes for those parts.
- **HTSUS** current edition (USITC JSON).
- **Court rules**: FRCP and FRE in full; FRAP.
- **Case law**, bulk files only (never paging an API for bulk copy):
  - CourtListener bulk data: opinions from SCOTUS, the 13 federal circuits, Delaware Supreme Court and Court of Chancery, NY Court of Appeals and Appellate Division, Texas Supreme Court. Stream and filter; never store the whole dump.
  - Caselaw Access Project bulk data (static.case.law) for history, same courts.
  - Drop criminal matters before storage (existing `is_criminal`), keep commercial/civil ones.
- **State statutes** as enacted: Delaware Titles 6 and 8; NY UCC and BCL; Texas Business & Commerce Code. Only where the recorded terms allow bulk use; otherwise link-only.

## How
- Citations: extract and normalise every citation in every opinion and statute with **eyecite** (Free Law Project, BSD licence), and store a citation graph (`cites (from_doc, to_doc, citation_text)`). This is what cite-check and "is this case still good law" rely on later.
- Chunk by structure (section, subsection, paragraph); keep every version with dates, as Z2 does.
- Embeddings: the local embedder, in batches, overnight, at low priority (`nice`, `mem_limit` 2g on the loader), so Tank and the agents are never slowed.
- Disk budget: check free disk first and stop at a configurable cap (default 40 GB for the pool). Store text and metadata, never PDFs or images.
- `pool-loader` is a one-shot service run on demand ("load wave"), resumable, idempotent (a re-run adds new versions, never duplicates).
- Free public sources only. No paid service, no key.

## Done when
CI green on fixtures; pool status shows document counts per source with last update dates; 20 test citations (statute, regulation and case) resolve by citation and by meaning; no criminal opinion is stored (tested); a second run adds nothing new; a planted fake citation does not resolve.

## Founder step (after merge)
GitHub → Actions → coolify-ops → `op` = `deploy`, then Claude runs the loader once in the Zenas room. First full load runs overnight.
