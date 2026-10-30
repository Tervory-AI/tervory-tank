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
- Radix's egress only: `agents/radix/egress-policy.json`, `agents/radix/egress.py`, `agents/radix/net.py`, `agents/radix/docker-compose.yml` (point 5);
- tests.

> **Updated 21 Oct, 04:15 PT.** The founder has created all the buckets and put a scoped key on each room's Coolify app, tested (each key lists its own bucket and is refused on another). Tank holds only `R2_ACCOUNT_ID`, its own uploads key, and Ghost's keys until Ghost's app exists.

1. **One bucket per agent, shared with no one.** Each room gets a storage client for **its own bucket only**, through a scoped R2 token per bucket. Add `tervory-rig`, `tervory-zenas` and `tervory-ghost` (the founder creates them). Tank keeps `tervory-uploads` for files people upload in the window.
   - ZA Zenas additionally uses founder bucket `tervory-zenas-za` via env name `R2_BUCKET_ZENAS_ZA` (see `docs/cursor/ZA-R2-BACKUP-PROVE-RESTORE.md`). US `tervory-zenas` is unchanged.
2. **What goes in:**
   - test datasets: the full ATF list snapshots, the CourtListener bulk slices, SA judgment PDFs as fetched;
   - agents' working files and browser artefacts (screenshots of what they read);
   - gold and bench snapshots;
   - training datasets, before they go to Hugging Face;
   - nightly database backups (encrypted).
3. **Keys (already in Coolify, use these exact names):**
   - `R2_ACCOUNT_ID` on every room and on Tank.
   - Each room reads only its own pair: `R2_ACCESS_KEY_ID_<ROOM>` and `R2_SECRET_ACCESS_KEY_<ROOM>`, where `<ROOM>` is `BASE`, `TIGER`, `MARKET_LAB`, `RADIX`, `TISAN`, `RIG`, `ZENAS` or `GHOST`. Zenas has the same pair on `agent-zenas` and `agent-zenas-za`.
   - Tank reads only `R2_ACCESS_KEY_ID_UPLOADS` and `R2_SECRET_ACCESS_KEY_UPLOADS`, for `tervory-uploads`. Tank never reads a room's pair. Ghost's pair sits on Tank only until Ghost's own app exists (GHOST-1); Tank does not use it.
   - The storage client refuses to start with a pair whose room does not match its own room name.
   - Never in code, logs or tests.
4. **Usage on the control panel:** used versus 1 TB, per bucket.
5. **Radix stays sealed, with one narrow opening for its own bucket (founder approved, 21 Oct).**
   - Add exactly one destination to Radix's egress policy: our account's R2 endpoint, `<R2_ACCOUNT_ID>.r2.cloudflarestorage.com` on port 443. The host is built from `R2_ACCOUNT_ID` at start, and only that exact host is allowed. No wildcard, and no other R2 or Cloudflare host.
   - R2 traffic goes through the same `egress-proxy`, like `lokd.co.za`. Radix code still never opens a socket itself.
   - Give the R2 destination its own limits, sized for storage (larger objects than a web page), and keep `lokd.co.za`'s limits unchanged.
   - Radix uses only `R2_ACCESS_KEY_ID_RADIX` and `R2_SECRET_ACCESS_KEY_RADIX`, which open `tervory-radix` only.
   - A scan of handed-over code still makes no network call at all. Only storing and reading Radix's own files uses R2.
   - Update `agents/radix/README.md` wording on the corridor, and keep the `--internal` network.

## Done when
CI green. Tests:
- a room can read and write only its own bucket;
- a missing key shows an error and changes nothing;
- the backup job writes and lists a dated object;
- usage is reported;
- Tank uses only the UPLOADS pair, and a room refuses another room's pair;
- Radix can reach only its account's R2 host through the proxy; any other R2 or Cloudflare host, and any direct socket, is refused; a code scan makes no network call;
- `lokd.co.za`'s limits are unchanged.
