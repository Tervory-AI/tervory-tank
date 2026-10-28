# Zenas: assemble existing civil drafts through regional Docassemble

Branch: `codex/zenas-docassemble`. Started from main `3f469b0`; merged main `be3935d` in `82a7d87`, keeping both sides. Claude opens the **draft** PR; the founder merges; Grok deploys. Every finished file was committed and pushed separately. No GitHub API was used.

Zenas previously filled its approved clauses and wrote the Word document itself. Its existing drafting route now sends the existing fields to the private regional Docassemble API and returns Docassemble's text and finished DOCX. The same slot order, clause wording, missing-field marks, notice, prior reuse, citation guard and lawyer-review behavior remain. Trigger's existing legal hand-off still calls this route.

**Offline implementation is verified. Live deployment, restore proof and founder screenshots are pending. This is not a claim that the founder's live acceptance is done.**

## What changed — file and line

| File and line | Change |
| --- | --- |
| `agents/zenas/core/docassemble.py:20` | Documented session/file API, fixed private host, deployment-region check before HTTP, no proxy/redirects, fields nested under one fixed variable name, returned DOCX used directly. Only necessary prior fields are sent; database timestamps and tenant IDs stay out. |
| `agents/zenas/core/service.py:1493`, `:1535`, `:1560` | Existing region/scope gates precede Docassemble. Existing prior selection, permitted revision/citation guard, saved document state and response fields remain. Assembly and final Word generation use Docassemble. |
| `agents/zenas/core/drafting.py:75`, `tank/skills/zenas.shared/drafting.py:75` | Add an optional clause renderer to reuse existing selection/review policy on Docassemble. Defaults remain compatible for existing immutable skill packages and their evals. No approved version directory changed. |
| `agents/zenas/docassemble/package/assembly.py:16`, `:35`, `:60`, `:69` | Native Mako field rendering, independent server-side region validation, existing review policy, exact notice handling. Clause text and fields are literal data, never executable template source. |
| `agents/zenas/docassemble/package/__init__.py:1`, `package/data/questions/assembly.yml:1` | Internal package and documented questionless interview returning JSON and a generated file number. No interview questions or new client wording. |
| `agents/zenas/docassemble/package/data/templates/nda.md:1`, `supply.md:1`, `distribution.md:1`, `sale_of_goods.md:1`, `sale_of_goods_cisg.md:1`, `freight.md:1`, `services.md:1`, `cross_border_agency.md:1` | All eight existing layouts converted, retaining each slot and its order. Actual legal wording continues to come from the existing approved clause rows. |
| `agents/zenas/docassemble/package/data/templates/document.docx` | Native Docassemble DOCX template retains the old Word geometry, text and tracked review insertions. Binary file has no source line number. |
| `agents/zenas/docassemble/us/` and `agents/zenas/docassemble/za/`: each of the eight named template `.yml` files, line 1 | Explicit US/ZA interview bindings. Only the owning region's interview directory is mounted on its service. |
| `agents/zenas/docker-compose.yml:27`, `:48`; `agents/zenas/docker-compose.za.yml:34`, `:54` | Official pinned internal service, readiness dependency, independent local PostgreSQL, persistent backup volume and separate encrypted-backup worker per region. No published port or public ingress. |
| `agents/zenas/docassemble/backup.py:21`, `:49`, `:81` | Archive the previous completed official daily snapshot through `tar → age`, reusing the existing R2 archive/completion-marker code and regional bucket validation. No SQL and no plaintext upload or new plaintext spool. |
| `.env.example` — final Docassemble setting block | Setting names only, with empty values. |
| `tank/requirements-dev.txt` — Docassemble renderer block | Official release's Mako/docxtpl pins for offline parity tests only; no new room runtime dependency. |
| `tests/test_zenas_draft.py:390`, `tests/test_zenas_citation_source_links.py` — final fixture | Existing assertions run through the API stub; expected document text, notices, review and revision behavior are unchanged. |
| `tests/zenas_docassemble/api_stub.py:1`, `legacy_drafting.py:1`, `test_assembly.py:65`, `test_deployment.py:27` | Documented API-shaped stub with real template rendering, frozen main oracle, 80 word-for-word cases, regional/failure/refusal/Trigger checks and backup contracts. |

No Workspace page, Figma asset, client text or layout changes relative to merged main. No production database, tenant clause library or secret value was accessed.

## Official upstream evidence

- [Official Docker instructions](https://docassemble.org/docs/docker.html): `jhpyle/docassemble`, all-in-one local PostgreSQL, the persistent `/usr/share/docassemble/backup` volume, 600-second graceful shutdown and daily rolling snapshots. No new database service or custom database implementation.
- [Image metadata evidence](evidence/image-pin.json): `jhpyle/docassemble:1.10.14@sha256:5dc6feb56f69a912885ad5652d1754330f37c1a05331c5831e34e9d0c509492d`. The manifest and both platform digests were read from Docker Hub. No image was deployed here.
- [Pinned release Dockerfile](https://github.com/jhpyle/docassemble/blob/v1.10.14/Dockerfile): the release uses `local3.14`, although the public Docker guide still describes `local3.12`. Mounts follow the pinned release, not the older guide. Updating the image requires rechecking these mounts.
- [API documentation](https://docassemble.org/docs/api.html): authentication uses `X-API-Key`; `GET /api/session/new` starts the fixed interview; `POST /api/session` supplies `variables` with `raw: 0`; the documented questionless `json_response()` pattern returns the result; `GET /api/file/<file_number>` returns the finished DOCX. API keys stay in headers. The generated session encryption material is used only in the POST body, never a URL or log.
- [Document templates](https://docassemble.org/docs/documents.html) and [release dependencies](https://github.com/jhpyle/docassemble/blob/v1.10.14/docassemble_base/pyproject.toml): native Mako and DOCX/Jinja rendering, with Mako 1.4.2 and docxtpl 0.20.2 used in the offline tests.
- [Official daily snapshot implementation](https://github.com/jhpyle/docassemble/blob/v1.10.14/Docker/cron/docassemble-cron-daily.sh): dated snapshots include configuration, files and PostgreSQL dumps. The backup worker reads yesterday's directory, rejects stale/incomplete snapshots and encrypts before the existing regional archive upload.

Commands used to verify upstream (cloud only):

```sh
curl --fail --location --max-time 30 --output /tmp/docassemble-api.html https://docassemble.org/docs/api.html
curl --fail --silent --show-error --location --max-time 30 --output /tmp/docassemble-docker.html https://docassemble.org/docs/docker.html
curl --fail --silent --show-error --location --max-time 30 --output /tmp/docassemble-config.html https://docassemble.org/docs/config.html
curl --fail --silent --show-error --location --max-time 30 --output /tmp/docassemble-documents.html https://docassemble.org/docs/documents.html
curl --fail --silent --show-error --location --max-time 30 --output /tmp/docassemble-tags.json 'https://hub.docker.com/v2/repositories/jhpyle/docassemble/tags?page_size=5'
git ls-remote --tags https://github.com/jhpyle/docassemble.git 'refs/tags/v1.10.14' 'refs/tags/1.10.14'
git clone --depth 1 --branch v1.10.14 --filter=blob:none https://github.com/jhpyle/docassemble.git /tmp/zenas-docassemble-upstream
```

These succeeded. The tag resolves to source commit `b821998ddd9442f80456ed1649f38afee0a3b877`. A guessed upstream example-file URL returned 404; it was not used. The implementation follows the documented questionless example and the pinned release source.

## Offline proof and main comparison

All tests reject outbound IPv4/IPv6 socket connections. Docassemble's API is stubbed; Mako and DOCX rendering use the real pinned libraries. No model call, production SQL, real API credential, container deployment or live backup ran here.

| Final check | Main `be3935d` | This branch | Failures on main | Failures on branch |
| --- | --- | --- | --- | --- |
| Zenas + existing Trigger suite; branch additionally includes Docassemble tests | [538 passed, 6 skipped, 13 warnings; 124.88s](evidence/main-tests.txt) | [640 passed, same 6 skipped, 13 warnings; 132.03s](evidence/branch-tests.txt) | None | None |
| Model-boundary guard | [27 passed; 17.68s](evidence/model-boundary-main.txt) | [27 passed; 18.01s](evidence/model-boundary-branch.txt) | None | None |
| Focused integration checkpoint before the final region-binding tests | — | [151 passed, 3 skipped, 3 warnings; 7.03s](evidence/focused-tests.txt) | — | None |

The six final skips are the same on both sides: four existing Zenas PostgreSQL/schema cases and two existing Trigger real-database/live-checker cases. They need `POOL_SCHEMA_DATABASE_URL`, `ZENAS_SCHEMA_DATABASE_URL` or the explicit `TRIGGER_INTERNAL_CHECKER_TEST` opt-in. They were not configured for these offline runs. The 13 warnings are also the same. These scoped results do not claim that every unrelated Tank/Workspace CI job is green.

The first baseline collection needed the existing `proselint` pin installed in this cloud. A new Trigger test initially imported Tank without its deployment configuration; the test now uses an in-process adapter as the existing Trigger tests do. The first full branch run caught a change to the required room-region setting; that change was reverted, and an independent Docassemble region binding now rejects mismatches before any data is sent. All are resolved in the final results above. No unrelated main test was weakened or repaired.

Exact dependency commands:

```sh
/workspace/.tervory-cloud/venv/bin/python -m pip install Mako==1.4.2 docxtpl==0.20.2
/workspace/.tervory-cloud/venv/bin/python -m pip install -r agents/trigger/requirements.txt
```

Both exited 0. The offline runner `/tmp/zenas-laws-africa-offline.py` has these exact contents (its earlier task name is retained):

```python
import socket
import sys
import pytest

def offline(event, args):
    if event == "socket.connect" and args[0].family in (socket.AF_INET, socket.AF_INET6):
        raise RuntimeError("Outbound connections are disabled for the offline Zenas suite")

sys.addaudithook(offline)
raise SystemExit(pytest.main(sys.argv[1:]))
```

Main commands, working directory `/tmp/zenas-docassemble-main`, detached at `be3935d`:

```sh
env -u RIG_TEST_DATABASE_URL -u POOL_SCHEMA_DATABASE_URL -u ZENAS_SCHEMA_DATABASE_URL -u GITHUB_ACTIONS PATH=/workspace/.tervory-cloud/node/bin:/workspace/.tervory-cloud/venv/bin:/usr/bin:/bin PYTHONPATH=. /workspace/.tervory-cloud/venv/bin/python /tmp/zenas-laws-africa-offline.py -q tests/test_zenas*.py tests/trigger_first_build/test_trigger.py --junitxml=/tmp/zenas-docassemble-main-final.xml > /tmp/zenas-docassemble-main-final.log 2>&1
env PYTHONPATH=. /workspace/.tervory-cloud/venv/bin/python /tmp/zenas-laws-africa-offline.py -q tests/test_tank_one_door.py > /tmp/zenas-docassemble-guard-main-final.log 2>&1
```

Branch commands, working directory `/workspace/tervory-tank`:

```sh
env -u RIG_TEST_DATABASE_URL -u POOL_SCHEMA_DATABASE_URL -u ZENAS_SCHEMA_DATABASE_URL -u GITHUB_ACTIONS PATH=/workspace/.tervory-cloud/node/bin:/workspace/.tervory-cloud/venv/bin:/usr/bin:/bin PYTHONPATH=. /workspace/.tervory-cloud/venv/bin/python /tmp/zenas-laws-africa-offline.py -q tests/test_zenas*.py tests/trigger_first_build/test_trigger.py tests/zenas_docassemble --junitxml=/tmp/zenas-docassemble-branch-final.xml > /tmp/zenas-docassemble-branch-final.log 2>&1
env PYTHONPATH=. /workspace/.tervory-cloud/venv/bin/python /tmp/zenas-laws-africa-offline.py -q tests/test_tank_one_door.py > /tmp/zenas-docassemble-guard-branch-final.log 2>&1
```

[Static-check proof](evidence/static-checks.txt) records the exact Ruff and diff commands with their exit codes. Saved output has trailing whitespace removed; test results are unchanged.

## Grok deployment — resource and setting names only

| Region / existing Coolify resource | Services in that resource | Persistent volume |
| --- | --- | --- |
| Boston / `agent-zenas` | `agent-zenas`, `docassemble`, `docassemble-backup` | `docassemble_us_backup` |
| ZA / `agent-zenas-za` | `agent-zenas`, `docassemble`, `docassemble-backup` | `docassemble_za_backup` |

Volume names above are Compose names; Coolify prefixes them with the resource's project name. The Docassemble service uses only the internal `assembly` network; the backup worker has a separate `backup` network and a read-only view of its own volume. It has no Docker socket, model credentials, Laws.Africa token, room API key or production database login.

Founder-supplied setting names, **separate values per region, never pasted into this PR**:

- `DOCASSEMBLE_API_KEY`
- `DOCASSEMBLE_DB_PASSWORD`
- `DOCASSEMBLE_SECRET_KEY`
- `DOCASSEMBLE_ADMIN_EMAIL`
- `DOCASSEMBLE_ADMIN_PASSWORD`
- Existing `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID_ZENAS`, `R2_SECRET_ACCESS_KEY_ZENAS`, `R2_BACKUP_RECIPIENT`
- ZA additionally: `R2_BUCKET_ZENAS_ZA`

Compose-managed setting names: `DOCASSEMBLE_REGION`, `DOCASSEMBLE_URL`, `TANK_REGION`, `R2_BUCKET`, `CONTAINERROLE`, `DAHOSTNAME`, `DAUPDATEONSTART`, `DAALLOWUPDATES`, `DAENABLEPLAYGROUND`, `DADEBUG`, `DAALLOWLOGVIEWING`, `TIMEZONE`, `DABACKUPDAYS`. The official image's bootstrap aliases are `DBPASSWORD`, `DASECRETKEY`, `DA_ADMIN_EMAIL`, `DA_ADMIN_PASSWORD`, `DA_ADMIN_API_KEY`.

Grok deploys the two existing regional Compose resources after founder merge, with no domain/public port for Docassemble. The official image runs its own local PostgreSQL and restores/persists through the official backup volume and graceful shutdown. The room waits for the official readiness endpoint. Keep bootstrap credentials and config out of logs/screenshots; remove browser/API development access through the supplied disabled-update/playground settings. Missing required settings block startup or assembly; there is no local assembly fallback.

Backups run at 03:00 UTC and encrypt the preceding day's official snapshot. This deliberately avoids the actively written daily dump, so off-box recovery lags by a daily snapshot. A new deployment has no eligible snapshot until that first previous-day snapshot exists. Grok must verify the encrypted completion manifest and restore to a separate scratch Docassemble resource in the **same region**, using the founder's offline restore identity. Do not restore over the running database. Neither a real archive nor restore has been claimed by this PR; the offline tests prove routing, validation and encryption-before-upload ordering only.

## Decisions I made

- Kept the real clause source: the existing region-scoped, lawyer-approved database rows. The eight code templates contain slot order rather than fixed legal wording, so the converted templates receive those same approved rows at runtime. No sample clauses or copied client documents are seeded.
- Kept rows approved for `both` within their stored region. Each actual interview is explicitly US or ZA; the other region's interview directory is absent from its service, and both client and server validate jurisdiction.
- Reused existing clause selection/review policy and the existing age/R2 archive implementation. Mako fills fields and Docassemble's native attachment engine produces the Word file. Compatibility helpers remain for existing approved skill evals; the deployed drafting route has no local generation fallback.
- Preserved the existing optional model revision of differing, non-library prior text and its citation guard **outside assembly**. Assembly makes zero model calls. Existing tests still require the same revision behavior; standard library drafts and full prior reuse remain model-free.
- Used the image's official volume/daily dump mechanism rather than adding SQL or maintaining a separate database dumper. Backups reuse the same encrypted platform-archive path as existing ZA backups; the storage `public` parameter is a platform gate, not a public object ACL.
- Retained the room's required region setting. Added a Compose-managed assembly-region binding so misconfiguration is refused before client fields can be sent to the wrong regional service.
- No UI controls, pages, wording, pricing, model routing, production skill approvals or permanent production-data changes were added.

## Founder screenshots and live proof — pending

No founder-browser screenshots were available in this cloud, and none were fabricated. Grok/assessor still need to attach the real civil result with its notice/review state, the real refusal, the returned document and encrypted-backup restore evidence. The API tests and real renderer tests do not substitute for running the pinned container and checking the founder's browser.

## Exactly what to open and click to prove it

1. After Grok deploys the intended region, open **https://app.tervory.com/chats** in the founder's account routed to that region. Click **+ New chat** (or the existing **Start a new chat** button), use the existing **Message Tervory** box to ask **Trigger** for a standard civil contract from an already approved local template, and supply the same real fields used for the pre-deployment reference document. Click **Send**, inspect the existing proposed action and click **Confirm**. Do not use fixture parties/terms or add a template to make this check pass.
2. Confirm that Trigger hands the request to Zenas and the result has exactly the reference contract's wording, the existing **“Zenas provides legal information, not legal advice.”** notice, and the same review marks/state. Record the existing response's `review`, `model_calls` and returned `docx_base64` artifact through the assessor's authenticated route capture; compare the Word document's text and tracked marks. No new download control is added by this PR. Capture the actual browser result and document.
3. Repeat through the existing Zenas drafting route with the same approved template and fields. If a real matter was supplied, reload **https://app.tervory.com/zenas**, click **Matters**, and open it; verify the saved document and review state. Record its real ID without exposing credentials.
4. In the same existing chat flow, request a criminal bail application under the **Criminal Procedure Act 51 of 1977**. Confirm the unchanged refusal **“Refused. Zenas does not do criminal law. Ask a criminal lawyer in that jurisdiction.”** The drafting request must reach neither Docassemble nor a drafting model. Capture the refusal.
5. Repeat the civil check in the other region with that region's own approved template. Verify ZA requests are refused on Boston before assembly, and have Grok attach the matching regional encrypted archive/restore evidence. If the regional route or an approved real clause source is absent, report that missing prerequisite; do not create live fixture data or new page wording.
