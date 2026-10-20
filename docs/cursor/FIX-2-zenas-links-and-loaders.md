# FIX-2: Zenas reaches both regions, ZA stack deploys, loaders load

> Written 18 Oct 2026, 21:45 PT by Claude, from the live checks after #148 deployed. One PR. It touches `tank/main.py`, a shared file, so keep the change to exactly what is below.

**Files you may change:** `tank/main.py` (only `_ZENAS_PATH` and `_homes_key_scope`), `.github/scripts/deploy_changed.py`, `agents/zenas/pool/adapters/` (and `agents/zenas/pool/http.py` if a fetch helper is needed), `agents/zenas/requirements.txt` and `agents/zenas/Dockerfile` (only to add the libraries named below), new or updated tests.

## 1. Tank forwards the new Zenas routes
`_ZENAS_PATH` does not list `selftest` or `review-switch`, so `/v1/zenas/selftest` and `/v1/zenas/review-switch` return 404 and the founder pages show "could not be loaded". Add both (GET and POST). Test both.

## 2. The ZA founder link may read status and start loads
Boston reaches the ZA Tank with `TANK_API_KEY_ZA`, which is the ZA `TANK_HOMES_KEY`. `_homes_key_scope` only allows `POST /v1/zenas/tenants`. Also allow, each only with `home_region=za`:
- `GET /v1/zenas/pool/status`
- `POST /v1/zenas/pool/sources/{id}/load`
- `GET` and `POST /v1/zenas/selftest`
- `GET` and `POST /v1/zenas/review-switch`

Everything else stays refused. These routes return only source names, counts, dates, errors and scores. Tests for every allowed path and for refused ones (matters, documents, rule cards).

## 3. Auto-deploy keeps the ZA stack current
`deploy_changed.py` deploys the Boston main app and the rooms (including `agent-zenas-za`) but never the Coolify app **`tervory-tank-za`** (the SA Tank stack), which was 3 days behind on 18 Oct. After the main app deploys successfully, deploy `tervory-tank-za` and wait for it, before the rooms. A failure stops the run like the main app does. Test it.

## 4. Loaders (live results 18 Oct, 21:05 PT)
- **eCFR:** now `HTTP Error 404: Not Found`. Fix the endpoint path for the current eCFR API.
- **UNCITRAL CISG and model laws:** finish with 0 documents. The sources are PDFs: parse them with **docling** (MIT) or **pypdf** (already used for ZA judgments) into one document per article/chapter.
- **SAFLII:** returns a Cloudflare challenge. Fetch it with **patchright** (Apache-2.0, stealth Playwright on Chromium). Keep the rule that a challenge page is logged as an error and never stored.

Each fix gets a saved real response (or PDF) as a fixture and a test that it parses into many documents.

## Done when
CI green; the four items above are each tested. After merge Claude runs Load now on every keyless US and SA source and the first self-test in both regions, and reports the scores.
