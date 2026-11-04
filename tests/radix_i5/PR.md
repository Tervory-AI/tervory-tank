# Radix I5 — monitoring audit

**done in #634**. No duplicate scanner or runtime change is needed.

Checked fetched main `55b2e224` and the inherited #634 head `ca662ce620b14c85e7de6a3d1de1c0fdea22c559`. Main did not yet contain the R6 monitoring implementation. #634 already contains both checks below, and `codex/radix-w4` inherits them. Main was not merged or rebased. Claude opens the wave PR.

## Existing implementation, current file/line

- `agents/radix/passive_routes.py:77`: watched scans call the R6 collector with the previous tenant/domain hashes, within the existing TXT-verified scan and shared one-running lease. This call was already at line 71 in #634's inherited head; I2 added the preceding active-scan branch.
- `agents/radix/passive_r6.py:96`: checksum comparison records changed/new/gone observations with old/new SHA-256 values; `:195` hashes fetched pages and `:216` hashes bounded same-host linked pages.
- `agents/radix/passive_store.py:273`: persist hashes beside the tenant-owned run; `:350` reads previous tenant/domain hashes from a completed page check.
- `agents/radix/passive_r6.py:285`: ClamAV checks its baked signature database, scans bounded same-host downloaded files at `:309`, and records signature findings or an incomplete/skipped result rather than a clean claim.
- `agents/radix/Dockerfile:15`: signature download is build-time only; watch runs do not update signatures or install add-ons.
- `tests/radix_r6/test_checks.py:35`: checksum-change tests; the same file covers malware completion and skipped/incomplete paths.
- `tests/radix_r6/PROOF.txt:125`: #634's existing native image proof includes ClamAV detecting EICAR through the bounded test path.

HIBP remains parked because it requires a paid key. No service, credential or provider was added.

## This gate's only change

`tests/radix_i5/PR.md:1`: record the required #634 skip and its source evidence. No code or test was duplicated. The immediately preceding combined offline regression included R6 and passed **577 tests and 437 subtests**, with 256 warnings; see `tests/radix_i7/PROOF.txt`. CI's exact lint is run before this documentation push. Hosted CI and founder live acceptance remain pending Claude's PR/merge.
