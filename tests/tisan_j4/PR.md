# Tisan J4 quote engine — branch handoff

Branch: `codex/tisan-j4`. Implementation/tests verified at
`654d3150851dd4cf45e9d1e8cebdeb60453e3a12`; this report is the only subsequent change.
Claude opens the PR from this branch. Founder merges. No PR has been opened by
this thread, so hosted PR checks and the separate review remain pending.

## What changed

Quote requests now have an auditable, tenant-bound lifecycle:
`draft → submitted → acknowledged → quoted → accepted | declined`.
API creation atomically records draft and submitted events. Submission itself
is the approval; no separate approval or payment flow is added. All other moves,
including repeated moves and moves out of terminal states, are refused.

| File and starting line | Change |
| --- | --- |
| `agents/tisan/quotes.py:38` | Strict structured input: email plus UUID item IDs and integer quantities; unknown fields at every level are refused before storage. No free-form customer payload, card, bank, or payment fields. |
| `agents/tisan/quotes.py:77` | Allowed transition map and actor validation. |
| `agents/tisan/quotes.py:93` | Atomic creation/state updates plus timestamped actor audit events; tenant predicates on every read/write; row lock serializes moves. |
| `agents/tisan/quotes.py:152` | Explicit acknowledgement email attempt; approved wording gate precedes SMTP setup and any mail-status write. Reuses the same `SmtpMailer` that Tiger imports. |
| `agents/tisan/quotes.py:198` | Reads only the designated approved wording file, verbatim, with no default or caller-supplied wording. |
| `agents/tisan/quotes.py:224` | Additive schema initialization and five private API routes, all using the existing founder/room-key guard. |
| `agents/tisan/schema.sql:51` | Idempotent quote request/event tables, tenant composite foreign key, state constraints, indexes, forced RLS and room-role grants. |
| `agents/tisan/app.py:149` | Registers the quote API using the existing `gold_sources.founder` guard. |
| `agents/tisan/Dockerfile:45` | Packages quotes/schema and existing SMTP implementation; includes repository Figma documents for the future approved wording file. |
| `agents/tisan/Dockerfile.dockerignore:8` | Allows the reused SMTP source and existing Figma document tree in the build context. |
| `tests/test_tisan_quotes.py:108` | Every pair of six states, financial-field refusals at three levels, audit/rollback, tenant isolation, API authorization, invalid inputs, missing/invalid wording, successful/rejected/uncertain email and missing SMTP. |
| `tests/test_tisan_quotes_postgres.py:24` | Disposable local PostgreSQL: execute schema twice, exercise non-bypass room role and RLS, concurrent moves, and event-failure rollback. |

Only `agents/tisan/` and the listed tests/report changed. The existing exact-commit
promotion and Radix gate implementations from #425/#426 are retained. No
Workspace page, generated-site page, Tank route, Compose setting, model call,
production SQL, live SMTP send, promotion or deployment was performed.

Merging changes under `agents/tisan/` redeploys Tisan and its regional copies
through the existing deploy-on-merge mechanism. No region/environment/network
configuration changes are included.

## Private API

All routes require the existing `X-Tank-Key` and verified founder
`X-Tervory-Admin` allowlist. The actor recorded in events comes from that verified
header, never a body field. Existing chassis endpoint binding supplies the
validated tenant to its transaction-local RLS context.

- `POST /quotes`: `{tenant_id, data: {contact: {email}, items: [{item_id, quantity}]}}`; creates submitted, HTTP 201.
- `GET /quotes?tenant_id=<uuid>&limit=100`: at most 200 tenant records.
- `GET /quotes/<uuid>?tenant_id=<uuid>`: one request and its ordered audit events.
- `POST /quotes/<uuid>/state`: `{tenant_id, state}`; only the allowed next state.
- `POST /quotes/<uuid>/email?tenant_id=<uuid>`: explicit gated mail attempt.

Unknown fields are rejected on create, nested contact/items, and state moves.
A request from another tenant is absent, not returned. Missing records return
404; invalid moves return 409; invalid structured inputs return 422. These are
API responses only; no page/error copy has been added.

Email status is independent of quote state. Missing/invalid wording sends
nothing and changes neither quote state, audit events nor mail status. The future
approved file must contain one fenced `json` block whose `acknowledgement`
object has only nonempty string `subject` and `text` fields. No wording file was
created. Parser fixtures exist only under temporary test directories and are
not proposed copy or live content.

With valid wording, existing SMTP settings are consumed by name only:
`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.
Missing SMTP leaves the request untouched. A durable `sending` claim prevents
concurrent/repeated delivery; definite rejection remains pending, while ambiguous
failure remains uncertain. A crash during sending is not automatically retried.
No email outcome moves the quote to acknowledged; that is an explicit store action.

## Exact verification commands and results

Working directory for the commands below: `/workspace/codex-tisan-j4`, except
the npm command, which ran in `/workspace/codex-tisan-j4/workspace`.
The existing `/tmp/base-reliability-venv` supplied Python/pytest dependencies.
No credentials or production database settings were read.

```sh
git clone https://github.com/Tervory-AI/tervory-tank.git /workspace/codex-tisan-j4
git fetch origin main && git checkout -B codex/tisan-j4 origin/main
ls agents/tisan/schema.sql agents/tisan/app.py agents/tiger/alert_email.py
```

Clone was created during the preceding authorized preparation. Restart fetch and
checkout succeeded at `7a5132fa`; every named existing file was present. The
shared `/workspace/tervory-tank` checkout was not changed.

```sh
python3 -m py_compile agents/tisan/quotes.py
python3 -m py_compile agents/tisan/app.py
```

Both exited 0. Initial `python -m py_compile agents/tisan/quotes.py` failed because
this host has `python3`, not `python`; rerun as above succeeded. The first commit
attempt failed because the clone had no Git author identity. Local-only
`git config user.name Codex` and `git config user.email codex@openai.com` fixed it.
The early push after that failed commit created the branch without a source
commit; `1f137095` then committed/pushed the actual engine successfully. No push
failed, and every completed source/test/report file was committed and pushed.

```sh
/tmp/base-reliability-venv/bin/python -m pytest -q tests/test_tisan_quotes.py
```

Final result: **94 passed, 1 warning in 0.99s**, exit 0.
Earlier increments: 81 passed, then 93 passed as input/API cases were added.

```sh
docker run --detach --name tisan-j4-test-postgres --network bridge --publish 127.0.0.1::5432 --env POSTGRES_HOST_AUTH_METHOD=trust --tmpfs /var/lib/postgresql/data postgres:16
docker port tisan-j4-test-postgres 5432
J4_TEST_POSTGRES_PORT=32783 /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_tisan_quotes_postgres.py
```

Disposable container bound **127.0.0.1:32783**. Integration result:
**3 passed, 1 warning in 1.42s**, exit 0. Each test created and dropped its own
local test database. No password was generated or needed. The container is
removed after verification. Integration tests opt out unless this explicit local
test-port setting is supplied; they never discover production connection values.

```sh
J4_TEST_POSTGRES_PORT=32783 /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_tisan_* 2>&1 | tee /tmp/tisan-j4-all-tests.log
```

Initial all-Tisan run: **1 failed, 133 passed, 1 skipped in 8.86s**.
The pre-existing gold-actions test needed `workspace/node_modules/typescript`.
`tee` also reported `Disk quota exceeded` for its `/tmp` output file; this file
is not used as evidence. The console output identified the failure.

```sh
npm ci --ignore-scripts --no-audit --no-fund
```

Exit 0: **added 45 packages in 24s** using the existing workspace lockfile.
No tracked dependency file changed.

```sh
J4_TEST_POSTGRES_PORT=32783 POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32783/postgres /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_tisan_*
```

Final result at `654d3150`: **148 passed, 13 warnings in 4.90s**, exit 0,
**no skips**. The URL above is the disposable local trust-auth test container,
with no password. It also enables the existing gold schema test. The preceding
run before the final missing-SMTP test was added had 147 passed in 4.98s.
Warnings concern existing FastAPI/Starlette/Pydantic deprecations.

```sh
/tmp/base-reliability-venv/bin/python -m pytest -q tests/tisan_promotion
```

**35 passed, 3 skipped in 3.43s**, exit 0. The three existing real-Chromium opt-in
tests were not selected. This is regression evidence for the existing promotion
and Radix gate code, not evidence of a live promotion or a new full image build.

```sh
docker run --rm --network none --memory 512m --cpus 0.5 --read-only --tmpfs /tmp --mount type=bind,src=/workspace/codex-tisan-j4/agents/tisan/app.py,dst=/app/app.py,readonly --mount type=bind,src=/workspace/codex-tisan-j4/agents/tisan/quotes.py,dst=/app/quotes.py,readonly --mount type=bind,src=/workspace/codex-tisan-j4/agents/tisan/schema.sql,dst=/app/schema.sql,readonly --mount type=bind,src=/workspace/codex-tisan-j4/agents/rig/rigbox/reserve.py,dst=/app/quote_smtp.py,readonly --entrypoint python lblbn0wjaz30hhdur9l3pylg_agent-tisan:f986c6f4e24c29202117d737b78c601c0486ba14 -c 'import app, sys, quote_smtp; q=sys.modules["tisan_quotes"]; routes=sorted(r.path for r in app.app.routes if hasattr(r,"path") and r.path.startswith("/quotes")); assert len(routes)==5, routes; assert str(q.EMAIL_WORDING)=="/app/docs/figma/tisan/QUOTE-EMAILS.md"; assert q.approved_letter() is None; print("Packaged imports: OK; quote routes:", routes); print("Wording absent: no email")'
```

Exit 0. Output:

```text
Packaged imports: OK; quote routes: ['/quotes', '/quotes', '/quotes/{request_id}', '/quotes/{request_id}/email', '/quotes/{request_id}/state']
Wording absent: no email
```

This runs a new network-disabled, read-only container from an existing Tisan
image, overlaying this branch's source files. It imports the actual room app and
SMTP implementation. It neither starts the production container nor runs the
application lifespan or a full Dockerfile build.

```sh
git diff --check
```

Exit 0, no output. Source/test files were staged individually, committed and
pushed with `git push origin codex/tisan-j4` after completion. First source push
used `git push -u origin codex/tisan-j4`. No main push or merge occurred.

## Figma items — deliberately stopped here

- Approved Tisan quote-form frames, including field labels and every state/error
  needed for the founder's test site. No page was added or changed.
- Approved acknowledgement wording at `docs/figma/tisan/QUOTE-EMAILS.md`.
  The file remains absent, so current runtime behavior sends no email.

Founder browser evidence/screenshots: **not available**. No founder submission,
mailbox receipt, test-site URL, screenshot or acceptance is claimed. Per the
revised brief, this browser test follows approval of the frames and wording.

## Handoff status

The engine and local tests are ready on the branch. Claude must open the PR;
hosted green checks and the separate review are still pending. This report does
not claim the revised PR-green completion condition or browser acceptance.
