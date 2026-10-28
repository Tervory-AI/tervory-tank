# Base reference file and fewest-first states

Status: implementation in progress. This is not proof of live completion.

Brief: `docs/build/TONIGHT-2026-10-27.md`, section 3, plus the founder's instruction to push this branch early and leave PR creation to Claude.

Base: `713dd46` from `origin/main`.
Branch: `codex/base-reference-file`.

## Scope

- Optional `BASE_REFERENCE_FILE_URL` in the existing first-download/refresh paths; reuse parsing, validation and installation.
- Preserve ATF's 403 block; allow a changed source to attempt without editing production rows.
- Order states by reference licence count, then name.
- No UI, production data, secret values, model calls, merge or deployment changes.

## Commands and evidence

- `git fetch origin main` — succeeded; main resolved to `713dd46`.
- Read `AGENTS.md`, `docs/cursor/CONTEXT.md`, and the full section 3 brief.
- `git switch -c codex/base-reference-file origin/main` — created a fresh branch from main.

Implementation details, exact checks and their results will be added here after execution.

## Founder browser acceptance

Pending. No founder screenshots are available and no live success is claimed.
The founder must set `BASE_REFERENCE_FILE_URL` in Coolify after review/merge, then verify the file date/licence count and smallest-state-first campaign in his browser.

## Job A implemented

- `agents/base/engines/ffl/reference.py`: configured dated CSV/TXT uses the existing bounded reader, challenge handling and `parse_file`; `0926-ffl-list.csv` means 2026-09-01. Current/older files are not downloaded again, and a missing/invalid/future filename date is rejected using existing wording. Query strings are not saved in source provenance.
- `agents/base/engines/ffl/reference_source.py` and `agents/base/Dockerfile`: reuse `agents/_brain/security.py` for URL/DNS checks, pin the socket to a checked public address, preserve TLS hostname/Host, re-check redirects, and disable environment proxies. No production private-address exception.
- `tank/base_repository.py`: source-specific blocked/recent checks, existing parser/install flow, one initial attempt per configured source per daily window, durable stops for 403/challenges, and the original ATF stop retained when the setting changes or is removed.
- `tank/schema.sql`: one additive, idempotent JSONB metadata column. Existing ATF check rows are interpreted in code; no UPDATE of live rows or production SQL was run. Source identities are hashes, not link values.
- `.env.example`, `docker-compose.yml` and `agents/base/docker-compose.yml`: the single optional setting name `BASE_REFERENCE_FILE_URL`, with no value. The same setting is required on the Tank and Base resources.

### Exact checks so far

```sh
BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres /workspace/worker-venv/bin/python -m pytest -q tests/test_base_reference_file.py tests/test_base_atf_download.py tests/test_base_reference_adopt.py tests/test_base_product.py > tests/base_reference_file/source-tests.txt 2>&1
```

Result: **81 passed in 16.86s**. See `source-tests.txt`.
Tests use a local HTTP fixture server, a local PostgreSQL database, and a test-only transport that maps a validated public destination to the local listener. Fixtures never reach a live screen. The existing ATF download/adoption/block tests remain passing.

```sh
/workspace/worker-venv/bin/ruff check tests/test_base_reference_file.py --select F401 --fix
git diff --check
```

Result: removed one unused test import; whitespace check passed.
