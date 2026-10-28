# Zenas: retain verified law source links and the existing output notice

Draft for Claude to open. Branch: `codex/zenas-source-links`.
Base: `4e74b42` (fetched main on 28 October 2026).

## What changed

- Cherry-picked only `7c3cc67` with `-x`, producing `df85dd4`. The pool's exact document/version supplies the source URL; answers and saved memos retain it, and Workspace passes it through. Request-provided passages cannot establish a law citation.
- `agents/zenas/core/law_pool.py:61`: reuse the existing region mapping for source metadata on each box. Queries remain scoped to that box and jurisdiction. The restored helper's US-only check would otherwise disable ZA source links.
- `workspace/app/zenas/view.tsx:424`: the existing citation text now opens its retained URL. No new label, control, or layout. The restored API alone left these citations as plain text.
- `tests/test_zenas_citation_source_links.py:58` and `tests/zenas_source_links/links.test.cjs:1`: offline checks of regional queries, exact versions, public URL validation, real Ask submission/presentation/rendering, and unreleased answer privacy.
- `agents/zenas/core/service.py:53`: the exact existing footer, **“Zenas provides legal information, not legal advice.”**, is appended to completed answers and memos and to new/reused drafts before persistence. Draft Word downloads carry it too. Already-noticed drafts keep a single notice; clause content and review marking are preserved.
- `tests/test_zenas_citation_source_links.py:120`: checks real service output and saved body/source equality, missing-link refusal, tenant isolation, review on/off, and new/reused drafts and Word downloads in both regions, with zero model calls. `tests/test_zenas_draft.py:249` updates the existing exact-output expectation for the requested notice.

The Boston-only commit `c433fca` was not taken. No routing, auth, pricing, keys, or schema changes.

## Commands and results

Run on the Codex cloud machine, in `/workspace/tervory-tank`.

```sh
git fetch founder main
git switch -c codex/zenas-source-links founder/main
git push -u founder codex/zenas-source-links
git fetch founder restore/zenas-backend-326
git cherry-pick -x 7c3cc67
git push founder codex/zenas-source-links
```

Results: new branch pushed from fetched main, then cherry-pick `df85dd4` pushed. No GitHub API used. Git reports that the repository redirects to `Tervory-AI/tervory-tank`.

```sh
env -u RIG_TEST_DATABASE_URL -u POOL_SCHEMA_DATABASE_URL -u ZENAS_SCHEMA_DATABASE_URL -u GITHUB_ACTIONS PATH=/workspace/.tervory-cloud/node/bin:/workspace/.tervory-cloud/venv/bin:/usr/bin:/bin PYTHONPATH=. /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/test_zenas_citation_source_links.py tests/test_zenas_law_pool.py tests/test_zenas_pool_region.py
/workspace/.tervory-cloud/node/bin/node --test tests/zenas_source_links/links.test.cjs
```

Results: **24 passed, 1 skipped** in 0.98s (database integration skipped; no database setting supplied); **2 Node tests passed**. One pre-existing Starlette/AnyIO deprecation warning. No network/model calls or production SQL in these checks.

```sh
git diff --check
git add agents/zenas/core/law_pool.py workspace/app/zenas/view.tsx tests/test_zenas_citation_source_links.py tests/zenas_source_links
git commit -m 'Keep Zenas source links usable in both regions and Ask'
git push founder codex/zenas-source-links
env -u RIG_TEST_DATABASE_URL -u POOL_SCHEMA_DATABASE_URL -u ZENAS_SCHEMA_DATABASE_URL -u GITHUB_ACTIONS PATH=/workspace/.tervory-cloud/node/bin:/workspace/.tervory-cloud/venv/bin:/usr/bin:/bin PYTHONPATH=. /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/test_zenas_citation_source_links.py tests/test_zenas_draft.py tests/test_zenas_ladder.py
```

Results: whitespace check passed; link integration committed as `801aaed` and pushed. Output-notice checks: **41 passed, 1 skipped** in 1.85s, with the same test-database skip and deprecation warning.

## Nightly scheduling — blocked, not installed

This cloud has no Coolify connection, configured credential, or scheduling tool. Coolify access is missing, so no scheduled task has been created or claimed. No alternative cron or GitHub workflow was added.

Use Coolify scheduled tasks on each region's existing Zenas room container (`agent-zenas` in the Boston resource and in the ZA room's Compose service), once nightly. The existing callable is:

```sh
POOL_USE_FIXTURES=0 python -c 'from agents.zenas.pool.nightly import main; main()'
```

The existing container supplies `DATABASE_URL` and `TANK_REGION` by name only. Its region must remain its own box's region. The module has a `main()` callable but no module-execution guard, so `python -m agents.zenas.pool.nightly` would not run the job. The callable loads that region's sources and invokes the existing conversion/self-test scheduling. This live command was **not run** here. The actual resource selection, schedule/timezone, last-run result, and next-run time require Coolify access and remain unverified.

## Decisions I made

- Kept both existing regions: reuse main's region mapping instead of importing Boston-only routing.
- Made the existing citation name clickable because retaining a URL only in JSON does not meet Prompt A's source-opening requirement. No citation wording or page layout changed.
- Kept the restored live harness untouched but did not run it; this brief requires offline tests.
- Added the notice after composition/rewording and before saving/exporting, so it survives downloads and cannot be omitted by the wording step. Reused drafts do not acquire a duplicate notice.

## Founder proof — pending

No founder screenshots were provided and no live test was performed. Offline results are not founder acceptance; this is not marked done or ready for review.

After deployment, open **https://zenas.tervory.com/zenas**, ask **“Is a forum selection clause in a B2B supply contract enforceable in Delaware?”**, and click every citation under **Sources**. Each must open the actual publisher's source used by the answer. The answer must include **“Zenas provides legal information, not legal advice.”** Record the returned answer, each source URL and its loaded page, and the saved matter ID; reload Matters and open the saved memo to confirm the same sources and notice. Attach screenshots from the founder's browser, including the answer and opened sources. Also capture Coolify's task settings and successful nightly execution separately for US and ZA, without exposing settings values.
