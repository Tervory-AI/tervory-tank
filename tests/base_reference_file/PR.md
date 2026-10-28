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
