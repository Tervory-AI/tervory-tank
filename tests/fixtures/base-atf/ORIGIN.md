# Saved ATF list for offline download proof

`0925-ffl-list-complete.txt.gz` is a losslessly compressed saved copy of the
September 2025 complete ATF FFL file. The original bytes are unchanged, including
three tab-filled blank rows, the unnamed business-name header, and line endings.
It has **77,611 licence records** (not the count expected from any live box).

- Publisher: Bureau of Alcohol, Tobacco, Firearms and Explosives (ATF).
- Official listing: https://www.atf.gov/firearms/listing-federal-firearms-licensees/complete
- Saved-copy archive: https://github.com/wadearnold/ffl-verify/blob/847b5f62fbb9912d44ebccd26d22372681d709ef/data/0925-ffl-list-complete.txt
- Archive commit date: 10 November 2025. The commit identifies this as its downloaded September 2025 ATF data.
- Retrieved from that public archive on 27 October 2026 for fixture proof; no live ATF connection is made by the tests.
- Uncompressed size: **11,103,529 bytes**.
- Uncompressed SHA256: `ebe50ffac9e53c6e513ba43832ddb913a7190f209b2ae6133d515b3d5eee465c`.
- Compression: Python `gzip.compress(original_bytes, mtime=0)`; no rows rewritten or removed.

This is public government reference data used only in a disposable fixture
database. The synthetic listing page advertises this saved file along with an
older file and invalid/future links, so the test can prove selection of the latest
eligible complete list. Production reads the official ATF listing and its linked
file; it does not read this archive or pin a date or licence count.
