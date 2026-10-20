# Z10: CourtListener from the bulk files, then the API for updates

> Written 19 Oct 2026, 12:55 PT. Founder decision: load CourtListener's back catalogue from its free bulk files, and use the API only for new cases. Reason: the API rate-limits us (HTTP 429 after 5 retries, 0 cases loaded on 19 Oct) even with the key and one request per second.

**Source facts (CourtListener bulk data page, read 19 Oct 2026):** full snapshots, one CSV per database table (PostgreSQL `COPY TO`, UTF-8, header row, `ESCAPE '\'`), generated quarterly on the last day of March, June, September and December, listed at `https://com-courtlistener-storage.s3-us-west-2.amazonaws.com/list.html?prefix=bulk-data/` with the schema dump alongside. Public Domain Mark, no key needed. Tables we need: courts, dockets, opinion clusters, opinions. The opinions file is very large.

**Files you may change:** `agents/zenas/pool/adapters/cases.py` (or a new `courtlistener_bulk.py` next to it), `agents/zenas/pool/catalogue.py`, `agents/zenas/pool/nightly.py`, `agents/zenas/pool/schema.sql` (additive), `workspace/app/zenas/feeds/` (progress line), tests with small saved slices of the real CSVs as fixtures.

## Do
1. **Find the latest snapshot** from the bucket listing: the newest file for each of courts, dockets, clusters and opinions, and the matching schema file. Record the snapshot date.
2. **Stream, never store the whole file.** Read each CSV straight from S3 (decompress on the fly if the file is compressed), row by row. Never write a full bulk file to disk; Boston has 400 GB and the opinions file alone is very large.
3. **Filter in this order, keeping only ids in memory or a temporary table:**
   - dockets: `court_id` in our appellate court list (`ALLOWED_COURTS`); keep `docket_number` and `nature_of_suit` (if the column exists) for convert's criminal check; drop a criminal docket here.
   - clusters: `docket_id` in the kept dockets; keep case name, citations, date filed, precedential status.
   - opinions: `cluster_id` in the kept clusters; take the best text field available (plain text, else HTML with the tags stripped).
   - Then the same commercial filter and stored-row shape as the API loader, so convert and the self-test see no difference.
4. **Resumable and polite.** Record which file of which snapshot is done; a restart picks up at the next file (or re-reads the current one, skipping rows already stored by hash). One stream at a time, low priority (`os.nice`), a cap per run (`ZENAS_CL_BULK_MAX`, default 50,000 opinions) so one press cannot fill the disk. Runs as a background job (FIX-4) on Boston only.
5. **Then the API for updates.** After a bulk snapshot is loaded, the nightly job asks the API only for opinions filed after that snapshot's date in our courts, one request per second, with the 429 handling from FIX-3. A new quarterly snapshot is picked up automatically and only adds rows that are not already stored (hash).
6. **Feeds page:** CourtListener shows snapshot date, file being read, rows read, cases kept, and skipped by reason (not our court, criminal, not commercial, no text).

## Rules
- US only, Boston only. Nothing goes to the ZA box.
- No key is used or needed for the bulk files. The API key stays in the header for updates, never in a URL or log.
- Schema changes additive, tested on an empty database and re-applied.

## Done when
CI green; fixture slices of real courts, dockets, clusters and opinions CSVs load the right cases and drop other courts, criminal dockets and non-commercial cases (tested); a stopped run resumes without duplicates (tested); the API update step only asks for dates after the snapshot (tested). After merge Claude presses Load on CourtListener and reports cases kept, then converts and runs the US self-test.
