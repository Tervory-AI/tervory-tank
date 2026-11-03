# Tisan J4 quote engine — branch handoff

Branch: `codex/tisan-j4`. Implementation/tests verified at
`654d3150851dd4cf45e9d1e8cebdeb60453e3a12` for the full suite; the review follow-up below records the subsequent import-only fixes.
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
| `agents/tisan/schema.sql:1` | Idempotent quote request/event tables, tenant composite foreign key, state constraints, indexes, forced RLS and room-role grants. |
| `agents/tisan/app.py:149` | Registers the quote API using the existing `gold_sources.founder` guard. |
| `agents/tisan/Dockerfile:45` | Packages quotes/schema and existing SMTP implementation; includes repository Figma documents for the future approved wording file. |
| `agents/tisan/Dockerfile.dockerignore:8` | Allows the reused SMTP source and existing Figma document tree in the build context. |
| `tests/test_tisan_quotes.py:108` | Every pair of six states, financial-field refusals at three levels, audit/rollback, tenant isolation, API authorization, invalid inputs, missing/invalid wording, successful/rejected/uncertain email and missing SMTP. |
| `tests/test_tisan_quotes_postgres.py:23` | Disposable local PostgreSQL: execute schema twice, exercise non-bypass room role and RLS, concurrent moves, and event-failure rollback. |

Only `agents/tisan/` and the listed tests/report changed, including the root-authorized isolation-fixture correction recorded below. The existing exact-commit
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


## PR #564 lint follow-up

CI run `41353670392` reported two F401 findings. Removed only the unused
`uuid4` import from `tests/test_tisan_quotes.py:10` and unused `Path` import from
`tests/test_tisan_quotes_postgres.py:10`, in commits `490a4a31` and `02caf8ae`.
Both were pushed normally to the same `codex/tisan-j4` branch.

Commands run from `/workspace/codex-tisan-j4`:

```sh
PATH=/tmp/base-reliability-venv/bin:$PATH ruff check tank tests --select E9,F --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"
/tmp/base-reliability-venv/bin/python -m pytest -q tests/test_tisan_quotes.py tests/test_tisan_quotes_postgres.py
git diff --check
```

Results: Ruff **All checks passed**, exit 0; focused tests **94 passed,
3 skipped, 1 warning in 1.14s**, exit 0; diff check exit 0, no output.
The three optional local PostgreSQL tests were skipped because this follow-up
did not start a database or set `J4_TEST_POSTGRES_PORT`; their earlier real-SQL
results remain recorded above. No behavior changed. Hosted checks on the new
head remain pending; no browser acceptance or merge is claimed.


## PR #564 disposable-isolation follow-up

Isolation run `41354022951` failed while installing all room schemas because the
throwaway fixture does not provision the production `agent_tisan` role. Fixed
without creating roles in application schema DDL or weakening RLS:

- `agents/tisan/schema.sql:102`: grant the same least-privilege table/sequence
  permissions only when the room role already exists. Reapplying schema after
  role provisioning applies those grants. Forced RLS and tenant policies always
  install, including when the role is absent; no PUBLIC grant was added.
- `tests/test_tenant_rls.py:199`: omit `GENERATED ALWAYS` identity columns from
  generic seed INSERTs so PostgreSQL generates their IDs. Every actual tenant
  table, including both quote tables, remains in the full isolation matrix.
  No production identity constraint, RLS policy, or matrix assertion was relaxed.
- `tests/test_tisan_quotes_postgres.py:32`: install schema before role
  provisioning, assert no role was created and both quote tables enforce RLS,
  then provision the test role, reapply and verify the original grants and
  actual non-bypass-room-role operations.

Before pushing any of these three files, ran against a new disposable container:

```sh
docker run --detach --name tisan-j4-review-postgres --network bridge --publish 127.0.0.1::5432 --env POSTGRES_HOST_AUTH_METHOD=trust --tmpfs /var/lib/postgresql/data postgres:16
docker port tisan-j4-review-postgres 5432
RLS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32784/postgres J4_TEST_POSTGRES_PORT=32784 /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_tenant_rls.py tests/test_tisan_quotes_postgres.py tests/test_tisan_quotes.py
```

The container bound `127.0.0.1:32784`. First run: **113 passed, 1 failed in
32.80s**; the remaining failure was a missing local `dns` module when importing
Radix gateway code, not a schema/setup/RLS failure. Installed the existing
Radix Dockerfile's pinned dependency into this clone's ignored test-only folder:

```sh
/tmp/base-reliability-venv/bin/python -m pip install --target /workspace/codex-tisan-j4/.test-deps dnspython==2.9.0
PYTHONPATH=/workspace/codex-tisan-j4/.test-deps RLS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32784/postgres J4_TEST_POSTGRES_PORT=32784 /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_tenant_rls.py tests/test_tisan_quotes_postgres.py tests/test_tisan_quotes.py
```

Install exited 0; complete targeted rerun: **114 passed, 13 warnings in
66.65s**, exit 0, **no skips**. This includes the actual disposable all-schema
isolation matrix and real quote PostgreSQL tests, not just doubles.

To explicitly verify the absent-room-role path again after removing only the
role inside this named disposable container:

```sh
docker exec tisan-j4-review-postgres psql -U postgres -d postgres -c 'DROP ROLE agent_tisan'
J4_TEST_POSTGRES_PORT=32784 /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_tisan_quotes_postgres.py
PATH=/tmp/base-reliability-venv/bin:$PATH ruff check tank tests --select E9,F --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"
git diff --check
```

Results: `DROP ROLE`; **3 passed, 1 warning in 1.27s**; Ruff **All checks
passed**; diff check no output. All commands exited 0 before the source/test
fixes were committed and pushed. Source/test commits: `b58d6250`, `ef6b46bf`,
`2daf6928`. This report is the subsequent documentation change. The disposable
container is removed after verification. No production role/schema/data was
accessed or changed. Hosted CI on this new head remains to be checked by root;
no merge or founder browser acceptance is claimed.

## PR #564 generated-memory EOF invariant correction

Full Tank run `41355046121` identified the existing generator invariant:
`tests/test_agent_memory_records.py::test_all_agent_schema_files_use_one_generator`
requires the generated memory block to end the schema file. In source commit
`f2e7b89f`, moved all quote DDL/grants before that block. Current locations are
`agents/tisan/schema.sql:1` (J4 DDL), `:52` (guarded grants), and `:62` through EOF
(generated memory). The generated block is byte-for-byte identical to the prior
head; quote DDL/grants are unchanged apart from their position. No test waiver,
assertion change, role/policy change or generator source change was made.

Actual relocation and generator-roundtrip command, run from the isolated clone:

```sh
/tmp/base-reliability-venv/bin/python - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
from hermes.record_schema import AGENTS, BEGIN, END, generated_block, update_files
root = Path.cwd()
path = root / 'agents/tisan/schema.sql'
before = path.read_bytes()
end = before.index(END.encode()) + len(END.encode()) + 1
block = before[:end]
assert block == generated_block('tisan').encode()
quote_ddl = before[end:].strip(b'\n')
assert quote_ddl.startswith(b'-- J4:')
path.write_bytes(quote_ddl + b'\n\n' + block)
assert path.read_bytes().endswith(block)
assert path.read_bytes().split(BEGIN.encode())[0].strip(b'\n') == quote_ddl
with TemporaryDirectory(prefix='j4-generator-', dir=root) as directory:
    target = Path(directory)
    for agent in AGENTS:
        relative = Path('tank/schema.sql') if agent == 'tank' else Path('agents') / ('_template' if agent == 'template' else agent) / 'schema.sql'
        out = target / relative
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes((root / relative).read_bytes())
    snapshots = {p.relative_to(target): p.read_bytes() for p in target.rglob('schema.sql')}
    update_files(target)
    assert all((target / p).read_bytes() == content for p, content in snapshots.items())
print('Generated memory block preserved byte-for-byte; actual generator roundtrip unchanged for all 11 schemas')
PY
```

Exit 0, printed exactly the final line above. The real `update_files` generator
ran against copies of every schema in a temporary directory; all 11 files were
unchanged after generation and the temporary directory was removed.

Disposable database commands:

```sh
docker run --detach --name tisan-j4-generator-postgres --network bridge --publish 127.0.0.1::5432 --env POSTGRES_HOST_AUTH_METHOD=trust --tmpfs /var/lib/postgresql/data postgres:16
docker port tisan-j4-generator-postgres 5432
PYTHONPATH=/workspace/codex-tisan-j4/.test-deps MEMORY_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32785/postgres RLS_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32785/postgres J4_TEST_POSTGRES_PORT=32785 /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_agent_memory_records.py tests/test_tenant_rls.py tests/test_tisan_quotes_postgres.py tests/test_tisan_quotes.py
```

The container bound `127.0.0.1:32785`. Initial collection failed because this
local Python environment lacked `qdrant_client`; no tests ran in that attempt.
Installed the existing repository-pinned dependency into the clone's ignored
local test-only directory, then reran the same command:

```sh
/tmp/base-reliability-venv/bin/python -m pip install --target /workspace/codex-tisan-j4/.test-deps qdrant-client==1.20.0
```

Install exit 0. Final combined result: **139 passed, 13 warnings in 30.84s**,
exit 0, **no skips**, including the exact failing generator-invariant test,
the complete memory-record test file, actual disposable tenant RLS and quote
PostgreSQL tests, and focused quote behavior tests. Memory tests use their
existing deterministic encoder and in-memory Qdrant, with no model calls.

```sh
PATH=/tmp/base-reliability-venv/bin:$PATH ruff check tank tests --select E9,F --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"
git diff --check
```

Ruff **All checks passed**; diff check no output; both exit 0. All verification
completed before committing/pushing `f2e7b89f` to the same PR branch. This report
is the only subsequent change. The named disposable container is removed after
verification. Hosted checks on the new head remain pending. No production
mutation, merge or founder browser acceptance is claimed.

## W3 gate 2 — designed quote fields (3 Nov 2026)

Current work: `/workspace/codex-tisan-w3`, branch `codex/tisan-w3`, continuing
from gate-1 head `bb0338f9bd517b4e48610838f2d29a457a02a38b`. No main merge.
The field register was read with:

```sh
git show origin/codex/tisan-quote-design:docs/figma/tisan/SPEC.md
```

That remote ref resolves to `d08ed785647c23cf0a1dea108cb5a592cdb92008`.
The draft spec was not copied or changed. No page, email, payment field,
Workspace file, or visible product wording was built. QUOTE-EMAILS.md remains
absent; the existing approved_letter() gate and founder guard are unchanged.

| File and line | Gate-2 change |
| --- | --- |
| `agents/tisan/quotes.py:41` | Required contact name/reply method, optional phone/company, conditional phone validation; existing email check retained. |
| `agents/tisan/quotes.py:81` | Product/service type, required description and quantity, optional notes and existing UUID product reference. |
| `agents/tisan/quotes.py:109` | Move accepts the four quote fields; any supplied field on another move, even null or malformed data, is refused with the existing 409. |
| `agents/tisan/quotes.py:124` | Positive exact Decimal with at most two decimal places, Rig-equivalent uppercase currency check, aware future expiry and required quote message. |
| `agents/tisan/quotes.py:162` | Legacy missing quote fields stay absent; amounts are returned as exact decimal text instead of lossy JSON floats. No missing contact/item fields are filled. |
| `agents/tisan/quotes.py:230` | Locked acknowledged-to-quoted snapshot and audit event in one transaction. No later move changes the quote; accepted/declined remain final. |
| `agents/tisan/schema.sql:1` | Updated retained-fields comment. `:36` adds nullable checked columns; `:54` installs the immutable-snapshot trigger idempotently, including room-owner reapplication. RLS/grants and generated EOF block are byte-for-byte unchanged. |
| `tests/test_tisan_quotes.py:24` | Existing 94 quote cases use the expanded request and quote inputs; the SQL double retains snapshot values. |
| `tests/test_tisan_quotes_postgres.py:14` | Existing six real PostgreSQL cases retain lifecycle, isolation, rollback and startup/rollout coverage. |
| `tests/test_tisan_quotes_designed.py:1` | 117 additional real PostgreSQL cases: all field edges, quote completeness, forbidden quote fields on other moves, immutable data, legacy reads, actual founder routes and actual quote lifespan reapplication. |
| `tests/tisan_j4/PR.md:360` | This gate's commands, results, scope and remaining deployment evidence. |

### Founder-route acceptance evidence in disposable PostgreSQL

`test_founder_routes_complete_designed_request_to_accepted_with_real_history`
(`tests/test_tisan_quotes_designed.py:188`) mounts the real quote routes with
`gold_sources.founder`, and binds tenant context with the existing chassis helper.
It uses a real non-bypass room role against a fresh local test database.
The request has contact name/email/phone/company/reply method, a product with
its existing UUID reference/quantity/description/notes, and a service with
quantity/description/notes and no product reference. Text values contain
`placeholder`; no sample is added to a live screen.

Verified by passing assertions: creation returns 201/submitted; acknowledge,
quote and accept each return 200 with the corresponding state. The quote is
12.34 USD, with a timezone-aware expiry generated as now plus one day and a
placeholder quote message. The request fields roundtrip unchanged. History is
exactly draft, submitted, acknowledged, quoted, accepted; every timestamp is
aware and every actor is the verified founder. All later moves are refused.
Missing room key returns 401, a non-founder returns 404, and another tenant
cannot see the request or events, including unqualified SELECTs under RLS.
An email attempt returns wording_missing before SMTP configuration; nothing is sent.

Separate passing cases mutate each quote column directly in this disposable
Postgres and receive a database CHECK violation without changing the snapshot.
Legacy submitted and quoted rows remain readable with their original JSON and
without invented fields. The actual mounted quote lifespan runs twice after
room provisioning and confirms all four new columns are present.

### Exact gate-2 commands and results

```sh
docker run --detach --rm --name codex-tisan-w3-j4-postgres --network bridge --publish 127.0.0.1::5432 --env POSTGRES_HOST_AUTH_METHOD=trust --tmpfs /var/lib/postgresql/data --memory 512m --cpus 0.5 postgres:16
docker port codex-tisan-w3-j4-postgres 5432
# Local disposable container; 127.0.0.1:32869. No production DB setting is read.

.venv/bin/python -m py_compile agents/tisan/quotes.py
# Exit 0.

.venv/bin/python -m pytest tests/test_tisan_quotes.py -q --disable-socket --allow-hosts=127.0.0.1,localhost
# 94 passed, 1 existing warning, 2.16s.

J4_TEST_POSTGRES_PORT=32869 .venv/bin/python -m pytest tests/test_tisan_quotes_postgres.py -q --disable-socket --allow-hosts=127.0.0.1,localhost --maxfail=1
# 6 passed, 1 existing warning, 3.01s.

J4_TEST_POSTGRES_PORT=32869 .venv/bin/python -m pytest tests/test_tisan_quotes_designed.py -q --disable-socket --allow-hosts=127.0.0.1,localhost --maxfail=3
# 117 passed, 1 existing warning, 43.03s.

J4_TEST_POSTGRES_PORT=32869 POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32869/postgres TISAN_TEST_PLAYWRIGHT=/workspace/codex-tisan-w3/.venv/tisan-browser/node_modules/playwright PLAYWRIGHT_BROWSERS_PATH=/home/ammosync/.cache/ms-playwright .venv/bin/python -m pytest tests/test_tisan_*.py tests/tisan_promotion/ tests/test_c10_rooms.py tests/test_secrets.py -q -rs --disable-socket --allow-hosts=127.0.0.1,localhost --maxfail=3
# 415 passed, 2 skipped, 15 existing warnings, 140.86s.
# Only the two explicitly opt-in npm build cases were skipped. PostgreSQL and
# existing real Chromium promotion tests were enabled.

J4_TEST_POSTGRES_PORT=32869 .venv/bin/python -m pytest tests/test_tisan_quotes.py tests/test_tisan_quotes_postgres.py tests/test_tisan_quotes_designed.py -q --disable-socket --allow-hosts=127.0.0.1,localhost --maxfail=1
# Final focused rerun after the decimal JSON refinement: 217 passed, 1 existing
# warning, 41.85s. Includes 9007199254740993.01 returned without rounding.

.venv/bin/ruff check agents/tisan/quotes.py tests/test_tisan_quotes.py tests/test_tisan_quotes_postgres.py tests/test_tisan_quotes_designed.py --select E9,F
# All checks passed.

git diff --check origin/main...HEAD
# Exit 0.

docker stop codex-tisan-w3-j4-postgres
# Stopped and automatically removed this gate's disposable container/tmpfs.
```

The broad run preceded only the exact-decimal response refinement, which the
final 217-case rerun covers. No model, live SMTP, deployed room job, live schema
change, or deployment was used to check the work. Ruff was installed only into
the existing ignored `.venv/`; tracked dependency manifests did not change.

The standalone memory-generator pytest node could not collect because the
local environment lacks qdrant_client. Instead the actual hermes.record_schema
generator was run against temporary copies of all 11 schemas: each had exactly
one generated block at EOF, and update_files() left every copy byte-for-byte
unchanged. A comparison against gate-1 head also verified the existing Tisan
RLS/grant section and generated block are unchanged. This direct check exited 0;
it does not claim that the wider memory-record test module ran.

Pending after merge: the live deploy log must show successful schema startup
and a healthy room. Local owner-role lifespan checks are not that deployment
proof. Final-head hosted Tank/Workspace CI and founder-browser screenshots remain
pending; no PR was opened or merged by this builder. Gate 3 has not been supplied.
