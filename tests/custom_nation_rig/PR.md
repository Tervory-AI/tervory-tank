# Job 8 — Custom Nation quote notices and receipts

Branch: `codex/job8-custom-nation-rig`; existing PR #366. No new PR.

The widget previously had only a hidden notice slot. A store can now configure
its exact plain-text notice and HTTPS privacy-page URL through the existing
retailer settings operation. Its authenticated widget displays that notice in
both quote forms and submits the displayed version. The server rejects stale
versions before storing/delivering a quote and persists the text, URL, version
and UTC submission time in the existing quote payload. Existing stores without
a configured notice keep their previous behavior; no policy or customer data
has been invented or populated.

The founder authorized this continuation without the former blanket Figma/copy
approval gate. Original step-1 theme persistence remains on this PR; its prior
proof is preserved in commit f85a9ee89ee0d61594f348779ec010f27d6cc8ba.

## Changed files and lines (continuation)

| File:line | Behavior |
| --- | --- |
| agents/rig/schema.sql:131 | Additive, idempotent optional retailer quote_notice JSONB. |
| agents/rig/rigbox/store.py:301,715,739 | Memory/Postgres tenant-scoped notice storage; omitted legacy saves preserve it; read/reload supported. |
| agents/rig/rigbox/retailer.py:101 | Validate text/HTTPS URL on existing settings operation; reject explicit null before reporting saved. |
| agents/rig/rigbox/quotes/notice.py:12 | Preserve exact text/URL, derive SHA-256 version; stale/missing version yields 409 when configured; snapshot receipt with UTC time. |
| agents/rig/rigbox/quotes/service.py:49 | Allow only name/email/phone contact fields; validate displayed notice version and persist receipt before quote delivery. |
| agents/rig/rigbox/api.py:44,249 | Reject unknown top-level quote fields; accept notice_version; authenticated tenant-scoped no-store notice GET. |
| agents/rig/rigbox/quotes/widget-source.patch:1 | Pinned source changes, notice rendering/client version submission, load guard, refresh on quote open/stale rejection, escaping and unit tests. |
| agents/rig/rigbox/quotes/widget/manifest.json:1 | Select content-addressed 69d323434d149dd8324aeb2f324210ab45fe0488308e43ff8925348701890c17 UMD with integrity. Superseded bundles removed. |
| tests/test_rig_quote_notice.py:20,67,83 | Memory/Postgres settings and receipt tests; financial fields; real Chromium shipped-widget stale recovery. |
| tests/custom_nation_rig/PR.md:1 | Current proof and factual acceptance gaps. |

## Exact verification commands and results

All repository commands below run in `/tmp/tervory-job8-resume`, unless the
widget directory is specified. The disposable DB is a NEW local container;
no production database, restore, bucket or deployment was changed. The local
Postgres trust-auth URL contains no password. Test code uses existing offline
fixture keys only; no live key was issued, read or created.

```sh
git clone --single-branch --branch codex/job8-custom-nation-rig https://github.com/Tervory-AI/tervory-tank.git /tmp/tervory-job8-resume
git clone --no-checkout https://github.com/Tervory-AI/tervory-rig.git /tmp/tervory-job8-widget-resume
# In /tmp/tervory-job8-widget-resume:
git checkout --detach f382f8da90944a3176c1bd43cfc77f14e78c6a0f
git apply --unidiff-zero /tmp/tervory-job8-resume/agents/rig/rigbox/quotes/widget-source.patch
npm ci --no-audit --no-fund
npm run lint
npm run build
npx vitest run
git add -N tests/custom-nation-privacy-slot.test.ts
git diff --no-ext-diff --unified=0 > /tmp/tervory-job8-resume/agents/rig/rigbox/quotes/widget-source.patch
node scripts/package-widget.mjs /tmp/tervory-job8-resume/agents/rig/rigbox/quotes/widget
```

Clone/checkout/apply/install/lint/build/package exited 0. Source lint/build/Vitest
were rerun after the reviewer recovery fix: 3 test files, 25 tests passed.
TypeScript, Vite ESM/UMD and existing bundle sample-data check passed.
Final UMD: 67,143 bytes, 17,750 bytes gzipped. Only the final bundle remains.

```sh
python3 -m venv /tmp/tervory-job8-python
/tmp/tervory-job8-python/bin/pip install pytest pytest-asyncio asyncpg fastapi httpx python-multipart pydantic redis cryptography ruff
/tmp/tervory-job8-python/bin/pip install playwright
/tmp/tervory-job8-python/bin/pip install uvicorn
/tmp/tervory-job8-python/bin/python -m playwright install chromium
docker run -d --name tervory-job8-notice-test --label codex.task=job8-notice --memory=384m --cpus=1 -e POSTGRES_HOST_AUTH_METHOD=trust -p 127.0.0.1:55438:5432 postgres:17
docker exec tervory-job8-notice-test pg_isready -U postgres
RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55438/postgres /tmp/tervory-job8-python/bin/python -m pytest -q tests/test_rig_quote_notice.py tests/test_custom_nation_rig.py tests/test_rig_store_job.py tests/test_rig_feeds_retailer.py tests/test_rig_quotes.py tests/test_rig_quotes_postgres.py tests/test_rig_quotes_hosting.py tests/test_rig_quotes_limits.py tests/test_tank_one_door.py tests/test_secrets.py
/tmp/tervory-job8-python/bin/ruff check agents/rig/rigbox/api.py agents/rig/rigbox/quotes/notice.py agents/rig/rigbox/quotes/service.py agents/rig/rigbox/retailer.py agents/rig/rigbox/store.py tests/test_rig_quote_notice.py --select E9,F
git diff --check
```

Result: **136 passed, 1 warning in 52.03s**. Warning: installed FastAPI/Starlette
notes deprecated httpx TestClient integration. Ruff: All checks passed.
Whitespace check: exit 0, no output. This local environment is Python 3.14 with
separately installed test dependencies, not the repository's Python 3.12 CI
image; hosted CI is reported separately and is not inferred from this run.

The new notice file independently passed **16 tests in 11.61s**. Browser tests
use MemoryStore and a real local HTTP API/UMD, recording sender, both forms,
both themes and 390/1440 widths. They change the store notice after display,
verify stale submission stores nothing, observe refreshed wording, explicitly
submit again and check the resulting receipt. Persistence, reload, schema
reapplication, two-store separation and null-clear rejection are covered
separately with real disposable Postgres as well as memory storage.

```sh
git -C /tmp/tervory-job8-widget-resume worktree add --detach /tmp/tervory-job8-widget-check f382f8da90944a3176c1bd43cfc77f14e78c6a0f
git -C /tmp/tervory-job8-widget-check apply --check --unidiff-zero /tmp/tervory-job8-resume/agents/rig/rigbox/quotes/widget-source.patch
```

Result: exit 0 against clean pinned source. No 3D engine/bundle rebuilt.

Earlier iterations: initial 21 existing quote tests passed; combined new
store/existing quote run passed 33. Ruff twice identified fixture-import F811
in the new test file; explicit pytest-fixture annotations fixed it, and final
Ruff passed. The first commit attempt failed because this isolated clone had
no author identity; explicit per-command Codex identity fixed it. No push
failed. Every completed file was committed and actually git pushed to the
same branch. The push command each time was:

```sh
git push origin HEAD:refs/heads/codex/job8-custom-nation-rig
```

Every commit used `git -c user.name=Codex -c user.email=codex@openai.com commit -m`
with its exact subject in the branch history. Checkpoints include b05a641,
c837efb, 5ea745a, 7d43dde, 7fd5f6c, cafcae0, 6256895, 97e8ace, 7c9cf88,
10ac5a7, 02d08de, ddb1079, 63b7ee9, 79c050d, 763b173, 63319e4,
22effe4 and 75329e8. No main push or merge.

## Review and remaining acceptance

The independent reviewer identified explicit-null settings handling and stale
widget version recovery. Both are fixed and tested on this same PR. Final
head review and hosted CI status follow separately. Local screenshots are
created only in pytest temporary paths and show offline data; they are NOT
founder screenshots or live acceptance evidence.

No production settings, SQL, catalogue, key, quote, email or deployment was
changed. No model call checked the work. Customer launch still requires the
actual store-owned notice text/privacy-page URL, approved real catalogue CSV,
exact test-page origin and quote delivery inbox; no such values were guessed.
No supported Coolify connection is available here. Settings are names only:
SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM.

The founder still must see Custom Nation's real skin/catalogue/notice in his
own browser and receive the email with the matching reference in his inbox.
Those screenshots and actual receipt are missing. Tests and independent
review cannot substitute for them. Jobs 2/5 are already merged and were not
rebuilt. M0 remains an evidence inventory, with no live backup/restore/SQL run.
