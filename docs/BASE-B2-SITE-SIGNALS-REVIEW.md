# Base B2 site signals — PR handoff

Branch: `codex/base-site-signals`. Claude opens the PR; the founder merges.
No merge, deployment, live-data SQL, skill approval or model calls were performed.

## Change and evidence locations

- `agents/base/pipeline.py:31`: optional skill list; `:358`: approved signals pass immediately after scrape, using existing merge semantics.
- `agents/base/room.py:187`: pin optional skills through existing `approved()`; absent approvals do not block the existing core pipeline, including preview runs.
- `tank/skills/base.site_signals/1.0.0/run.py:1`: passive HTML/header fingerprints, explicit sales actions/negative statements, observed external booking/quote action URLs, copyright year, Last-Modified and dated posts. Evidence, source URL, confidence and the actual check timestamp are retained. Missing sales evidence stays unknown. Archived pages do not establish current signals.
- `tank/skills/base.scrape_site/1.3.0/run.py:1`: new unapproved version retains per-page HTML, source URL, observed-at time and allowlisted non-secret headers from the same existing requests. Browser-rendered HTML does not inherit HTTP dates from a different response.
- `tank/skills/base.verify/1.1.0/run.py:1`: new unapproved version adds a dated-content staleness check (730 days) while retaining existing scoring and flag wording. Copyright alone does not prove editorial recency. No B1 verify version was present on main at the last merge; the second landing must retain both changes in 1.2.0.
- `tank/base_evidence.py:211`: three new fields are retained only after the signals pass, with source, timestamp, confidence and evidence; explicit false sales values can be verified.
- `tank/base_metrics.py:185` and `:215`: append signal values and source/check/evidence/confidence columns. Existing columns retain their order and cell bytes.
- `workspace/app/base/display.ts:68`: explicit page exclusion list for all three fields.
- `workspace/app/base/reference-workflow.tsx:116` and `workspace/app/base/batch-workflow.tsx:38`: apply that list without changing existing page copy or elements.
- `tests/test_base_site_signals.py:49`: optional approval and outage tests; `:95`: unchanged unapproved pipeline; `:106`: approved flow; `:160`: eight exact recorded-page evals; `:170`: same-request header retention; `:198`: original CSV bytes; `:221`: entire rendered HTML of both pages remains byte-identical when all three new fields are present.

## Fingerprint provenance

OpenTechalyzer built-in fingerprints, independently authored upstream and MIT licensed:
https://github.com/Houseofmvps/opentechalyzer/tree/a3d30e479c91c06732ef88867d69b7feef8f3f35/src/fingerprints

Pinned commit: `a3d30e479c91c06732ef88867d69b7feef8f3f35`.
Vendored license: `tank/skills/base.site_signals/1.0.0/data/LICENSE`.
Verbatim TypeScript sources, normalized selected categories and the transformation description
are beside it in `data/upstream/`, `data/fingerprints.json` and `data/PROVENANCE.md`.
No GPL fingerprint data or external imported dataset was copied. No vendor probes execute.
Booking/quote URLs are directly observed action links, not guessed vendor fingerprints.

## Commands and results

Run from `/workspace/codex-base-b2-signals` unless a prefix says otherwise.

```sh
git fetch origin main && git merge origin/main
```

Succeeded; merged main through `a6bb55bf` before final validation. The same fetch/merge was
performed before every push; all pushes succeeded. Each finished file was separately committed
and pushed. The checkout was initially cloned and placed on the founder's requested branch.

Test environment provisioning (local checkout only):

```sh
/home/ammosync/.local/bin/python3.12 -m venv .venv
.venv/bin/pip install -q pytest pytest-asyncio pytest-socket pytest-timeout httpx fastapi asyncpg pydantic==2.10.6 PyYAML jsonschema rapidfuzz selectolax redis tiktoken openai dnspython cryptography reportlab feedparser python-multipart
.venv/bin/pip install -q selectolax==0.3.27 rapidfuzz==3.10.1 redis==5.2.1
.venv/bin/pip install -q pypdf google-re2==1.1.20251105 proselint==0.16.0
npm ci --prefix workspace --ignore-scripts --no-audit --no-fund
```

Succeeded; npm installed 45 packages. The initial unpinned selectolax install was incompatible
with the repository's existing parser imports and was corrected to the repository pin.
Earlier attempts also exposed missing local TypeScript, PDF and Trigger dependencies, and a
socket setting that blocked a localhost HTTP fixture. Those environment failures were fixed;
no unrelated product code or tests were weakened.

Required final suite:

```sh
PYTHONPATH=.:tank:agents/_chassis .venv/bin/python -m pytest tests/test_base_* tests/test_skills_offline.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 -q
```

**219 passed, 54 skipped, 0 failed, 14 warnings in 65.10s.**
This includes all new approval, page-render, CSV and skill-eval regressions. Warnings are existing deprecations/model-field warnings.

Skip classification commands:

```sh
PYTHONPATH=.:tank:agents/_chassis .venv/bin/python -m pytest tests/test_base_database.py tests/test_base_audit.py tests/test_base_atf_download.py tests/test_base_reference_adopt.py tests/test_base_reference_file.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 -q -rs
PYTHONPATH=.:tank:agents/_chassis .venv/bin/python -m pytest tests/test_base_gold_nightly.py tests/test_base_source_reliability.py tests/test_base_unknown_cost.py tests/test_base_trial_launch.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1 -q -rs
```

Results: **29 passed, 51 skipped** and **46 passed, 3 skipped**, respectively.
All 54 skips require an isolated local PostgreSQL fixture (`BASE_TEST_DATABASE_URL`, or
`POOL_SCHEMA_DATABASE_URL` for audit/source reliability). CI must run those with its test database.
No setting values or credentials were read, created or copied. No real test failures remain.

Skipped PostgreSQL tests by file:

- `tests/test_base_atf_download.py`: 10
- `tests/test_base_audit.py`: 14
- `tests/test_base_database.py`: 6
- `tests/test_base_reference_adopt.py`: 14
- `tests/test_base_reference_file.py`: 7
- `tests/test_base_source_reliability.py`: 3

```sh
git diff --check
```

Passed (no output).

## Figma item

Base page: technologies, sells online, site newest year

The fields remain in evidence/API and CSV only. Both existing Base pages exclude them until
approved Figma frames provide their presentation. No page text or controls were added.

## Acceptance still outstanding

Founder browser test and screenshots have **not** been obtained. This report does not claim
browser acceptance or completion of the founder's done condition. After review/merge and
founder approval in `/skala` of site_signals 1.0.0, scrape_site 1.3.0 and verify 1.1.0 (or the
combined 1.2.0 if B1 lands first), the founder must verify DC rows' evidence and download the
CSV in his own browser. The pages should retain their current rendering. Attach those actual
screenshots to the PR; no invented or fixture screenshot substitutes for that proof.

Changes under `agents/base/` redeploy the Base room and its regional copies when the founder
merges. This branch does not perform that deployment.
