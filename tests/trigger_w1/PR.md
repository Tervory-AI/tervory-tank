# Trigger W1: formats, tenant learning, revisions and catalogue batches

Branch: `codex/trigger-w1-writing`. Own clone: `/workspace/codex-trigger-w1`.
Initial implementation/test checkpoint: `4820572088ea40fbe6ee35a83370f953a4839219`.
Review fixes and their verification are recorded below.
Claude opens the PR. Founder merges. No main push, deployment, production SQL,
real model call, live tenant mutation or founder-computer work was performed.

**Offline implementation is ready for review. The founder-browser DONE condition
is pending, and no founder screenshots are available or claimed.** The GBP
length-limit acceptance check also remains unresolved under the official-source
rule described below. No Trigger page or Workspace UI file was changed.

## Changes and review locations

| File and line | Result |
|---|---|
| `agents/trigger/formats.py:9`, `:24`, `:125`, `:140` | Nine fixed formats; official source/date metadata, local X weighted counter, code `over_limit` findings with exact count, preserved total/200-finding truncation. |
| `agents/trigger/service.py:17`, `:28`, `:64` | Optional format; format/limit in the existing draft request; tenant examples/change notes labelled guidance, not instructions or product facts; original voice version on revisions; check every draft through existing free checkers and existing `trigger.write` route. |
| `agents/trigger/voice_history.py:30`, `:45`, `:71` | Append literal chosen change requests to Rules while preserving other voice fields. Existing preview hash, expected revision, Confirm and immutable-version commit remain in use. |
| `agents/trigger/app.py:81`, `:94` | Existing internal voice preview/commit accepts those exact Rules. No new room endpoint/provider/config setting. |
| `tank/trigger_learning.py:12`, `:32`, `:68` | Save format/context/example IDs and parent; feedback on individual batch/revision receipts; tenant-only five newest accepted candidates then stable code overlap rank, plus five recent same-format change texts. |
| `tank/trigger_learning.py:87`, `:112`, `:127`, `:149` | Revisions retain parent voice/format/examples; withdrawn examples refused; chosen change-note lookup; last/prior 30-day scorecard from existing rows. |
| `tank/trigger_batch.py:10`, `:30`, `:58` | Real owned CSV rows or entitled tenant Rig product GETs; maximum 25; discard cross-product graph/fit fields; one product record per request. |
| `tank/trigger_commands.py:14`, `:86` | Code commands, explicit batch-item feedback IDs, learned-voice preview and source-bound batch snapshot/count in the existing Brief field. |
| `tank/trigger_routes.py:29`, `:119`, `:148`, `:158`, `:170` | Attachment command/source separation; accepted-copy lookup includes batch/revision items; unpaid GET scorecard/$0 receipt; confirmed write/revise/batch dispatch and individual pending records/receipts. Unknown item cost keeps the aggregate unknown. |
| `tank/command.py:35`, `:886`, `:1054`, `:1108`, `:1179`, `:1344`, `:1374`, `:1530` | Same founder/tenant-admin catalogue/access; typed tool adapters; GET query scope; bounded batch timeout/result envelope; confirmed changes propose a separate paid revision Confirm card. |
| `tank/schema.sql:2337` | Additive/idempotent columns on existing writes, composite tenant/parent FK, recent-format index. Exact personal-token rollout condition, permissive/restrictive tenant policies, ENABLE/FORCE RLS. Legacy RLS remains off. |
| `tank/case_study_sources.py:178` | Existing draft figure includes `drafts_using_accepted_examples`; batch/revision checker/feedback evidence follows distinct confirmed tenant/region receipts. |
| `agents/trigger/requirements.txt:1`, `tank/requirements-dev.txt:42`, `agents/trigger/ATTRIBUTION.md:14` | Proselint remains; twitter-text-parser and its vulnerable setuptools pin are removed. Local stdlib counting uses pinned official matching data with Apache/MIT notices. No replacement package, provider or paid service. |
| `agents/trigger/README.md:47` | Existing-card usage, counting semantics and acceptance boundaries. |
| `tests/test_trigger_w1.py:26` | Fifteen offline contracts with disposable Postgres and fake Tank: formats/counts/truncation, tenant/format selection, parent/original voice, literal learned Rules/Cancel/Confirm/stale rejection, per-row facts, Rig entitlement/GET, 25 receipts, accepted next-batch provenance, scorecard figures, RLS rollout and unconfirmed/member refusal. |
| `tests/trigger_second_build/test_second.py:120` | Helper selects the card created by the current turn, rather than an older pending revision. Original feedback/no-extra-model assertions remain intact. |

No policy, paid fallback, model checker, shared cache, queue worker, approved skill
version, sign-in, price, key, spend-cap or other-room implementation was changed.
The existing `trigger.write` route still owns all actual draft calls.

## Format source verification (2026-11-03 UTC)

- LinkedIn: [official post help](https://www.linkedin.com/help/linkedin/answer/a527226)
  states 3,000 characters. Report explicitly counts Unicode code points.
- Standard X post: [official counting rules](https://docs.x.com/fundamentals/counting-characters)
  specify 280 weighted characters. Local stdlib code handles NFC, official weight
  ranges, URLs and compound emoji, with all official weighted conformance cases. No paid long-post assumption.
- Meta description: [Google Search Central](https://developers.google.com/search/docs/appearance/snippet)
  explicitly states no fixed length limit; display truncation is separate.
- Google Business Profile: [official LocalPost reference](https://developers.google.com/my-business/reference/rest/v4/accounts.locations.localPosts)
  and [official post help](https://support.google.com/business/answer/7342169?hl=en)
  did not provide a numeric post limit. Community/third-party claims were not
  substituted for official documentation. The format therefore has no enforced
  limit, as explicitly required when an official limit cannot be found.
- Instagram: [official error-code reference](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/error-codes),
  HTTP 400/code 36004/subcode 2207010, specifies 2,200 characters. Applied in the
  PR #595 review fix on 2026-11-03 using the official row supplied by the reviewer;
  this environment's fetch still returned HTTP 429. Character count only; no
  separate hashtag or mention checks were added.
- Facebook: no verified official organic-post limit found; none enforced.
- Product description, email (subject and body), article: no publishing platform
  specified, therefore no invented universal limit.

Consequently a GBP `over_limit` screenshot cannot honestly be supplied from this
implementation. It needs a verifiable official numeric limit before enforcement.
This boundary is recorded beside the format in code, not hidden as a guessed cap.

## Commands and offline results

All repository commands ran in the own clone above. PostgreSQL below was a new
throwaway container owned by this task, with trust auth only on a loopback test
port, no volume and no production data. Existing dummy test auth is fixture-only.
Outside sockets and nonlocal DNS were blocked during pytest. Tank/provider calls
were replaced by AsyncMock/local ASGI fixtures; no real model was called.

```bash
git clone https://github.com/Tervory-AI/tervory-tank.git /workspace/codex-trigger-w1
cd /workspace/codex-trigger-w1
git fetch origin main
git checkout -B codex/trigger-w1-writing origin/main
# PASS; named existing files checked with ls before implementation.
# Before each push, git fetch origin main; git merge --no-edit origin/main.
# Integrated main 9313fd6e; every finished file committed and pushed separately.

docker run -d --name trigger-w1-pg -e POSTGRES_HOST_AUTH_METHOD=trust \
  -p 127.0.0.1::5432 postgres:16
docker port trigger-w1-pg 5432/tcp
# PASS: own disposable test DB at 127.0.0.1:32796.

/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pip install twitter-text-parser==3.0.0
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pip install --target .w1-tmp/site jsonschema==4.23.0
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pip install --upgrade --target .w1-tmp/site jsonschema==4.26.0
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pip install --target .w1-tmp/site setuptools==80.9.0
# PASS. Corrected jsonschema to main's exact pin before successful regression runs.
```

The initial requested-suite collection stopped because the reusable test runtime
lacked jsonschema; it made no test/model calls. Initial W1 tests exposed the
parser's undeclared pkg_resources dependency and attachment transport text being
parsed as part of the command. Both product issues were fixed and retested.
A Rig test seed initially omitted required `enabled_by`; the fixture was fixed.
A repeat found the older helper selecting an existing pending revision by UUID
ordering; it now selects the newly created card and tolerates historical seeded
result cards without an ID, without weakening assertions.

```bash
TMPDIR="$PWD/.w1-tmp" PYTHONPATH="$PWD/.w1-tmp/site" \
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32796/postgres \
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q \
  tests/trigger_first_build tests/trigger_second_build tests/trigger_gate2 \
  tests/test_trigger*.py tests/test_command.py tests/test_case_study_reports.py \
  --disable-socket --allow-hosts=127.0.0.1 --tb=short -ra
# 246 passed, 2 skipped, 16 warnings in 221.59s at the broader regression checkpoint.

TMPDIR="$PWD/.w1-tmp" PYTHONPATH="$PWD/.w1-tmp/site" \
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32796/postgres \
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q \
  tests/test_trigger_w1.py -k batch_25 \
  --disable-socket --allow-hosts=127.0.0.1 --tb=short
# 1 passed, 13 deselected: explicit batch feedback and next-batch provenance.

TMPDIR="$PWD/.w1-tmp" PYTHONPATH="$PWD/.w1-tmp/site" \
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32796/postgres \
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q \
  tests/test_trigger_w1.py -k batch_owned \
  --disable-socket --allow-hosts=127.0.0.1 --tb=short
# 2 passed, 13 deselected: known and unknown item cost aggregation.
```

Final requested suite plus Gate2, after the helper and aggregate-cost fixes:

```bash
TMPDIR="$PWD/.w1-tmp" PYTHONPATH="$PWD/.w1-tmp/site" \
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32796/postgres \
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q \
  tests/trigger_first_build tests/trigger_second_build tests/trigger_gate2 \
  tests/test_trigger*.py --disable-socket --allow-hosts=127.0.0.1 --tb=short -ra
# 143 passed, 2 skipped, 5 warnings in 75.05s (0:01:15).
```

Actual captured output for both regression checkpoints: [verification.txt](verification.txt).

The two skips are explicit: the optional real room/LanguageTool container check
and the CRM WSGI smoke requiring its pinned Django runtime. Neither was represented
as passing. Warnings include existing Pydantic/FastAPI notices and the parser's
pkg_resources deprecation (the compatibility pin is intentional).

```bash
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m ruff check \
  agents/trigger/formats.py agents/trigger/service.py agents/trigger/voice_history.py \
  agents/trigger/app.py tank/trigger_batch.py tank/trigger_learning.py \
  tank/trigger_commands.py tank/trigger_routes.py tank/command.py \
  tank/case_study_sources.py tests/test_trigger_w1.py \
  tests/trigger_second_build/test_second.py --select E9,F
git diff --check origin/main...HEAD
# PASS; final verification repeated after source/test changes.
```

Every database fixture applies Tank/Trigger schemas twice. The rollout test also
starts with legacy RLS off, enables the existing command-table rollout signal,
reapplies schema and inspects ENABLE/FORCE plus permissive/restrictive policies.
`tank/main.py:753` `_startup` was inspected before pushing: it uses a non-bypass
tenant pool and configured admin pool when RLS is active, and applies schema
through `(_admin_pool or raw_pool)`. No startup/config/credential workaround.

## Founder-browser acceptance still required

No screenshot in this handoff is a simulated founder test. None is attached
because no founder browser session or live acceptance run was available, and
this branch was not deployed. Existing Tank and Trigger applications will receive
their code/schema/dependencies only after authorized founder merge/deployment.
No new setting name or secret is required. Trigger Write and Voice pages remain
unbuilt and await their approved Figma frames.

In Custom Nation `/chats`, the founder still needs to:

1. Save its real voice and real on-voice examples through the existing preview
   and Confirm; capture the before/after views.
2. Request 10 real Rig SKUs in one batch, inspect the item count, Confirm and see
   each draft/report/receipt.
3. Accept selected write IDs, confirm a change request on one, then Confirm the
   proposed revision and inspect its parent ID.
4. Run the next batch and inspect accepted-write provenance IDs.
5. Resolve the official GBP limit boundary above before claiming that limit test.
6. Read the unpaid scorecard and inspect rates/periods/$0 receipt.

Capture those real founder screenshots for the PR. No live voice, product facts,
accepted examples or copy have been invented for this handoff. Interrupted paid
batches retain the existing Command uncertain-outcome/no-automatic-retry behavior;
completed item rows can survive an interruption, so recovery is not claimed by
the all-success offline acceptance tests.


## PR #595 review fix — 2026-11-03

`agents/trigger/formats.py:28` now sets Instagram captions to 2,200 characters,
with Meta's official error-code URL and explicit checked date 2026-11-03.
`tests/test_trigger_w1.py:46` checks the 2,200/2,201 boundary, exact `over_limit`
count and source, and confirms no separate hashtag/mention limits are imposed.
Other format limits are unchanged. README source notes match the correction.

```bash
TMPDIR="$PWD/.w1-tmp" PYTHONPATH="$PWD/.w1-tmp/site" \
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q \
  tests/test_trigger_w1.py -k 'formats_and_exact_counts or instagram_caption' \
  --disable-socket --tb=short
# 2 passed, 14 deselected, 5 existing warnings in 2.51s.
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m ruff check \
  agents/trigger/formats.py tests/test_trigger_w1.py --select E9,F
git diff --check
# PASS.
```

Each finished file was committed, origin/main fetched and merged, then pushed to
`codex/trigger-w1-writing`. No model, database, live copy or UI operation was used.


## PR #595 security-CI fix — 2026-11-03

Pulled Claude's `d0021069` before editing. Removed `twitter-text-parser==3.0.0`
and `setuptools==80.9.0` from `agents/trigger/requirements.txt`, eliminating the
introduced pins associated with PYSEC-2026-3447, GHSA-h35f-9h28-mq5c and
GHSA-xmj3-9gf7-h52w. No replacement Python package or setuptools version is added.
Historical install commands above describe the earlier implementation only.

`agents/trigger/formats.py:59`–`:125` now counts in local stdlib code using NFC,
the four official weight-one ranges/default weight two, and URL weight 23.
Pinned official TLDs and lightweight punycode label checks identify URLs without
DNS. The generated official Twemoji expression identifies compound emoji in
UTF-16 units; unmatched spans are weighted as Unicode code points. No parser
package, Node process, network or model executes at runtime.

- `agents/trigger/sources/x_text.json`: extracted official v3 configuration/TLD
  alternatives and Twemoji matching expression, with both upstream commit IDs.
- `tests/trigger_w1/twitter-text-weighted.json`: all 42 official weighted-length
  cases from `conformance/validate.yml`, with unchanged texts/expectations,
  original source SHA-256 and pinned URL. Only YAML-to-JSON extraction changes.
- `tests/test_trigger_x_length.py`: 22 current v3 cases through the public X
  format/checker, 20 preserved legacy-v2 cases through the undiscounted primitive,
  range boundaries, URL/emoji edges, and a subprocess proving all 42 cases with
  `python -S` (site packages disabled). 68 tests total.
- `agents/trigger/ATTRIBUTION.md:14` and `sources/x_text-LICENSE.txt`: full Apache-2.0
  and MIT licences/notices, extraction/adaptation details and exact sources.

Merged `origin/main` through `3fc94027` (Base B4), preserving both catalogues and
both action-timeout branches in `tank/command.py`. The Base saved-list schema and
Trigger provenance block both remain **above** the unchanged generated agent
memory block. A direct comparison with `hermes.record_schema.generated_block`
passed. No main push, deployment, model call or production SQL was used.

Exact verification commands (own clone; task-owned loopback disposable Postgres):

```bash
PYTHONPATH=agents python3 -S - <<'PYTHON'
import json
from pathlib import Path
from trigger.formats import _x_length
for group, cases in json.loads(Path('tests/trigger_w1/twitter-text-weighted.json').read_text())['tests'].items():
    for case in cases:
        assert _x_length(case['text'], discount_emoji='DiscountedEmoji' in group) == case['expected']['weightedLength']
PYTHON
# PASS: all 42 official cases with site packages disabled.

TMPDIR="$PWD/.w1-tmp" PYTHONPATH="$PWD/.w1-tmp/site" \
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q \
  tests/test_trigger_x_length.py --disable-socket --tb=short
# 68 passed in 0.46s.

RUNNER_TEMP="$PWD/.w1-tmp" GITHUB_PATH="$PWD/.w1-tmp/security-path" \
GITHUB_WORKSPACE="$PWD" bash .github/scripts/install-security-tools.sh
# PASS: repository-pinned gitleaks and OSV release checksums verified.
PATH="$PWD/.w1-tmp/security-bin:$PATH" TMPDIR="$PWD/.w1-tmp" \
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m unittest \
  discover -s tests/ci_security -p test_security.py -v
# All 41 security gate policy tests passed in 15.935s.
PATH="$PWD/.w1-tmp/security-bin:$PATH" TMPDIR="$PWD/.w1-tmp" \
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python \
  .github/scripts/security_scan.py osv --base origin/main \
  --output "$PWD/.w1-tmp/x-security-results"
# osv: clean. Zero NEW findings against origin/main 3fc94027.
# The scanner also reports 202 existing baseline findings, not introduced here.
PATH="$PWD/.w1-tmp/security-bin:$PATH" TMPDIR="$PWD/.w1-tmp" \
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python \
  .github/scripts/security_scan.py gitleaks --base origin/main \
  --output "$PWD/.w1-tmp/x-security-results"
# gitleaks: clean.

docker run -d --name trigger-w1-x-pg -e POSTGRES_HOST_AUTH_METHOD=trust \
  -p 127.0.0.1::5432 postgres:16
docker port trigger-w1-x-pg 5432/tcp
# 127.0.0.1:32805; disposable, no volume or production data.
npm install --prefix .w1-tmp/node --no-save --package-lock=false \
  --ignore-scripts --no-audit --no-fund typescript@5.9.3
# PASS: existing Workspace lockfile's version, test-folder tooling only.
NODE_PATH="$PWD/.w1-tmp/node/node_modules" node tests/base_lists_download.cjs
# PASS: saved-list CSV byte preservation and existing batch download behavior.

TMPDIR="$PWD/.w1-tmp" PYTHONPATH="$PWD/.w1-tmp/site" \
NODE_PATH="$PWD/.w1-tmp/node/node_modules" \
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:32805/postgres \
BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:32805/postgres \
/home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q \
  tests/trigger_first_build tests/trigger_second_build tests/trigger_gate2 \
  tests/test_trigger*.py tests/test_command.py tests/test_base_lists.py \
  --disable-socket --allow-hosts=127.0.0.1 --allow-unix-socket --tb=short -ra
# 357 passed, 2 skipped, 15 warnings in 203.78s (0:03:23).
```

Initial verification setup issues were resolved without product changes: an
unfiltered unit run blocked asyncio's Unix socketpair; the final command explicitly
allows local Unix sockets while blocking outside sockets/DNS. The broad merge run
initially lacked the lockfile's TypeScript test dependency. Security-policy tests
initially lacked the pinned gitleaks executable; installing the existing CI tools
resolved that. No environment issue was counted as a product pass.

Lint and `git diff --check` passed. The source/test checkpoint is `80656f02`;
subsequent evidence/handoff commits change documentation only. Actual outputs and
OSV gate JSON are in [x-security-verification.txt](x-security-verification.txt).
The founder-browser acceptance conditions above remain pending.
