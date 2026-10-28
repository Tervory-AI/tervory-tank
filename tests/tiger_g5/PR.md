# G5: Tiger product, cost and market alerts

Branch: `codex/tiger-g5-alerts`, based on `origin/main` at `585a900`.

Implementation and offline proof are in progress. No live database, page, SMTP
settings, or recipient configuration has been changed. The founder's controlled
page/inbox test and its screenshot have not been performed; this is not a claim
of live completion.

The only new email wording is the three sentences approved by the founder on
28 October. Existing alert rows, SMTP delivery, and email layout are reused.
No new Workspace controls or copy are added; preferences use the watch API.

## Commands so far

`git fetch origin main` — passed.

`git worktree add -b codex/tiger-g5-alerts /workspace/tiger-g5-alerts origin/main`
— passed; started at `585a900`.

## Founder test (pending)

After founder merge/deployment, establish a baseline on a watched listing page
the founder controls, add a product, and run another check. The founder must
receive `New product listed: {product}` in the configured inbox. A repeated check
must not send it again. No screenshot or live result is claimed here.

## Implementation checkpoint

`source /workspace/tervory-env/activate.sh && python -m pytest -q tests/tiger_g5 --tb=short`
— `26 passed in 7.46s`. Covers all three types with memory and disposable
PostgreSQL stores, two tenants, loopback SMTP, switches before detection and
before delivery, repeated checks, rollback and idempotent migration. Additional
API integration and regression validation are still in progress.
