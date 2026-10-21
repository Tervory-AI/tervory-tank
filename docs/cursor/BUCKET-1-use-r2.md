# BUCKET-1: put the empty Cloudflare R2 buckets to work

> Written 21 Oct 2026. The account already has R2 buckets that nothing in the repo uses: `tervory-base`, `tervory-tiger`, `tervory-market-lab`, `tervory-radix`, `tervory-tisan`, `tervory-uploads` and `skills-library`. Founder: about 1 TB is sitting empty and should be used for testing now. R2 has no egress fees.
>
> **Pre-launch (founder decision, 21 Oct): there are no clients and no client uploads yet, so test data may be used freely.** The per-region rules apply when the first real client signs up.

**Files you may change:**
- new `tank/storage.py`;
- `agents/_chassis/` (a storage client);
- each room's compose (bucket name env only);
- `.env.example` (names only);
- `jobs/train/`;
- tests.

1. **One bucket per agent, shared with no one.** Each room gets a storage client for **its own bucket only**, through a scoped R2 token per bucket. Add `tervory-rig`, `tervory-zenas` and `tervory-ghost` (the founder creates them). Tank keeps `tervory-uploads` for files people upload in the window.
2. **What goes in:**
   - test datasets: the full ATF list snapshots, the CourtListener bulk slices, SA judgment PDFs as fetched;
   - agents' working files and browser artefacts (screenshots of what they read);
   - gold and bench snapshots;
   - training datasets, before they go to Hugging Face;
   - nightly database backups (encrypted).
3. **Keys:**
   - `R2_ACCOUNT_ID`, plus per-room `R2_ACCESS_KEY_ID_<ROOM>` and `R2_SECRET_ACCESS_KEY_<ROOM>`.
   - The founder creates scoped tokens in Cloudflare and puts them in Coolify.
   - Never in code or logs.
4. **Usage on the control panel:** used versus 1 TB, per bucket.

## Done when
CI green. Tests:
- a room can read and write only its own bucket;
- a missing key shows an error and changes nothing;
- the backup job writes and lists a dated object;
- usage is reported.
