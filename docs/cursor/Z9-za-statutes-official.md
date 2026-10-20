# Z9: South African legislation from official sources (all national Acts)

> Written 19 Oct 2026, 03:45 PT. Founder: the SA library must hold **all** national legislation, not a short list. Laws.Africa's API costs $2,500 a year; the official texts are free. Permission for a consolidated feed has been requested from the University of Pretoria (Laws of South Africa) and AfricanLII at UCT (LawLibrary); until a written yes arrives, load only from official government sources.

**Files you may change:** `agents/zenas/pool/adapters/` (new `za_govza.py`, `za_gazette.py`), `agents/zenas/pool/catalogue.py`, `agents/zenas/pool/nightly.py`, `agents/zenas/schema.sql` (additive), new tests with saved real responses and PDFs as fixtures.

## Do
1. **Every national Act** listed on gov.za (Acts index, all years): the Act as passed and every amendment Act, as PDFs, parsed with docling or pypdf into one document per section, each with source URL, Act number and year, Gazette number and date.
2. **Regulations** published in the Government Gazette under those Acts, same shape.
3. **Amendment record, not invented consolidation.** For each Act store which amendment Acts exist and which sections they change. Do not write a merged "current text" unless it is produced by applying an amendment's own wording and tested against a known consolidated reference; mark every section `as_passed` or `as_amended_by: [...]`.
4. **Weekly refresh:** new Gazettes and new Acts are picked up by the nightly job; nothing is re-downloaded that has not changed (hash).
5. **Polite fetching:** one request at a time per host, a descriptive User-Agent, retry with backoff; a challenge page is logged and never stored.
6. **SA region only.** Everything lands on the ZA box.

## Done when
CI green; fixture PDFs of one Act and one amendment Act load into many sections with their sources (tested); an unchanged PDF is not re-stored (tested); the feeds page shows Acts loaded, amendments recorded, and errors. After merge Claude runs Load now on the ZA box and reports counts.
