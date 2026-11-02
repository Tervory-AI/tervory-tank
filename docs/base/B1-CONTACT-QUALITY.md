# Base B1: contact quality — review handoff

Branch: `codex/base-contact-quality`. Claude opens the PR; the founder merges.
Implementation is pushed. This is **not founder-browser acceptance** and no live run or skill approval was performed.

## What changed

- `tank/requirements.txt:48`: exact Apache-2.0 `phonenumbers==9.0.42` pin.
- `tank/skills/base.contacts/1.2.0/run.py:165`: RFC 5321 ASCII mailbox grammar and local/domain/mailbox octet limits. Each observed address retains its role/personal classification, disposable status, and its own existing MX result. Off-domain addresses are included in quality; pattern guesses are not treated as observed addresses.
- `tank/skills/base.contacts/1.2.0/run.py:196`: all supplied site/profile/input phone numbers get E.164 (null if unparseable), validity, metadata line type, and country agreement. No country is invented: input is an ISO alpha-2 country, absent/unsupported country is unknown. No carrier lookups, SMTP mailbox probing, calls, texts or models.
- `tank/skills/base.contacts/1.2.0/data/UPSTREAM.txt:1`: disposable-email-domains vendored at commit `aa73ac1b77f440ebdcca0872cf2ebbd73fadce70`, with the CC0 licence in `data/LICENSE.txt`; no runtime download.
- `agents/base/pipeline.py:436`: send site/profile/raw phone values, record country, and original contact observations; line 464 uses the existing confidence/source-aware `merge` for the new fields.
- `tank/skills/base.verify/1.2.0/run.py:116`: selected-phone adjustment of +5 when valid, known line type and country matches; -5 when invalid. Unknown quality does not invent a bonus. Existing score is unchanged when the candidate's quality metadata is absent.
- `tank/base_evidence.py:210`: append only the five authorized quality fields, matched to the exact primary verified contact and each field's original source/date. Existing contact evidence remains unchanged; blocked/archived observations cannot acquire quality evidence.
- `tank/base_metrics.py:185`: append the five CSV value columns and their source URL, check date and confidence columns. No pre-existing header or value changes. `tank/base_product.py` already delegates records.csv to this exporter and snapshots the complete fields for Apollo comparison; no change to that file was needed.
- `workspace/app/base/csv.ts:53`: additive five-field export schema.
- `workspace/app/base/field-visibility.ts:2`: explicit page exclusion list. `reference-workflow.tsx:117` and `batch-workflow.tsx:39` apply it before rendering fields. No new page words or labels.
- Candidate packages each include `skill.yaml`, `run.py`, `evals/cases.jsonl`, and `CHANGELOG.md`. Contacts has 19 eval cases, verify has 10, preserving the prior packages' cases. Existing skill versions and Skala lifecycle code are unchanged. Neither candidate is approved by this work.

## Figma item

**Base page: phone validity and line type, email quality**

The five fields remain excluded from both Base page field loops until the founder approves the relevant frames. Existing comparison rendering uses a fixed website/phone/email list and is unchanged.

## Exact validation commands and observed results

Run from `/workspace/codex-base-b1-contacts` unless stated otherwise.

```sh
.venv/bin/python -m pip install -r tank/requirements.txt -r tank/requirements-dev.txt
```

Exit 0. Installed the repository's pinned runtime/test dependencies in this checkout's isolated venv. Earlier attempts with an incomplete environment failed collection (missing dependencies / wrong selectolax version); these were environment setup errors, resolved by this command. Direct pytest also lacked the room import path; the new test now uses the same explicit Base room path as existing tests, and validation uses `python -m pytest`.

```sh
.venv/bin/python -m pytest -q -ra tests/test_base_* tests/test_skills_offline.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
```

Exit 0: **224 passed, 54 skipped, 14 warnings in 110.27s**. This run included every requested Base test module and the complete offline skill eval test. The warnings are existing FastAPI lifecycle deprecations and Pydantic field-shadowing warnings. An earlier run found one incorrect new-test assumption: `notmailinator.com` is itself on the upstream disposable list. Replaced the negative test domain with an invented `.example` domain; no production workaround.

An initial `--disable-socket` run without `--allow-unix-socket` blocked Python asyncio's internal socketpair. The final command above allows the internal event loop and loopback only; external sockets remain blocked.

```sh
.venv/bin/python -m pytest -q tests/test_base_contact_quality.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
```

Final focused run after adding the endpoint regression: **21 passed in 4.18s**. It verifies per-address MX, syntax limits, metadata types, provenance isolation, profile/raw phone forwarding, merge precedence, byte-identical original CSV columns, archive/block guards, and quality retained by records JSON, records.csv and the Apollo snapshot when phone values disagree. It includes the page-render regression below.

```sh
node tests/base_contact_quality_pages.cjs
```

Exit 0:

```text
reference-workflow.tsx: full HTML byte-identical; all five quality fields excluded
batch-workflow.tsx: full HTML byte-identical; all five quality fields excluded
```

These are offline invented test values, never loaded into a live screen and not claimed as the founder's test. The check compares complete rendered HTML against the existing field loop and original fields, with the candidate quality evidence added only to the new rendering input.

```sh
npm ci --ignore-scripts --no-audit --no-fund
```

The npm command ran with working directory `/workspace/codex-base-b1-contacts/workspace`.

```sh
cd workspace && npx tsc --noEmit
```

The TypeScript command ran from the repository root. Both exited 0; TypeScript produced no diagnostics. The npm command installed 45 packages from the existing lockfile without changing it.

```sh
.venv/bin/ruff check tank/skills/base.contacts/1.2.0/run.py tank/skills/base.verify/1.2.0/run.py tests/test_base_contact_quality.py
git diff --check
```

Exit 0 for each. Ruff: `All checks passed!`. Diff check: no output.

## Postgres coverage still requiring CI

All **54 skipped tests** explicitly require an isolated Postgres test service, configured by name through `BASE_TEST_DATABASE_URL` (audit/source-reliability tests also accept `POOL_SCHEMA_DATABASE_URL`). No value was read, supplied or invented here. Breakdown:

| Test module | Skipped |
| --- | ---: |
| test_base_atf_download.py | 10 |
| test_base_audit.py | 14 |
| test_base_database.py | 6 |
| test_base_reference_adopt.py | 14 |
| test_base_reference_file.py | 7 |
| test_base_source_reliability.py | 3 |

There are no remaining real test failures in the commands above. CI's Postgres checks and PR status have not been observed because Claude has not yet opened the PR.

## Git and acceptance proof

For every completed file, staged and committed it, then fetched/merged main before pushing this same branch. The exact local helper used was:

```sh
git add -- "$1"
git commit -m "$2"
git fetch origin main
git merge --no-edit origin/main
git push origin codex/base-contact-quality
```

All pushes succeeded. The first dependency-pin commit initially failed because this checkout had no author identity; after the founder's instruction, set **repository-local only**:

```sh
git config user.name 'Codex'
git config user.email 'codex@users.noreply.github.com'
```

No merge to main, deployment, approval, production SQL, live-data change, or live model call was performed.

**Founder-browser screenshots: pending.** No screenshots of the founder's next DC run exist in this work. Acceptance still requires the founder to approve `base.contacts 1.2.0` and `base.verify 1.2.0` (built on the 1.1.0 in #584) in `/skala`, run DC, and inspect/download the resulting evidence/CSV in his own browser. The new Base page fields remain withheld pending Figma approval. Do not call the product task done based solely on these offline results.
