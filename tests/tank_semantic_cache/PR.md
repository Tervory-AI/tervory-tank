# Tank semantic cache: tenant-isolated shadow evaluation

Branch `codex/tank-semantic-cache-2`, starting from main `4bda46b`.

Adds a CPU embedding shadow cache to the existing route cache. A paraphrase miss
continues through the normal route; its would-be cached answer is recorded and
scored using the existing comparator/judge. Serving requires the founder gate.
Claude opens the PR. Founder approval is required before serving embedding hits;
this branch does not approve any tenant or task.

## Decisions I made

- Reuse Hermes's pinned `fastembed==0.9.1` and `qdrant-client==1.20.0`.
- Pin `BAAI/bge-small-en-v1.5` to Qdrant's ONNX repository revision
  `52398278842ec682c6f32300af41344b1c0b0bb2`. Published upstream evidence:
  https://huggingface.co/Qdrant/bge-small-en-v1.5-onnx-Q/commit/52398278842ec682c6f32300af41344b1c0b0bb2
  (metadata only read here; no weights downloaded).
- The Docker build downloads the public files with `token=False`. Runtime uses
  only the baked files, CPU, two threads, and `local_files_only=True`.
- New cache logic stays in dedicated modules. Shared route hooks are limited to
  the explicitly authorized cache work. No UI change.

## Commands and results

All commands run in the managed cloud checkout `/workspace/tervory-tank`.

```sh
git fetch origin main
# exit 0; origin/main advanced from bde4578 to 4bda46b
git switch -c codex/tank-semantic-cache-2 origin/main
git push -u origin codex/tank-semantic-cache-2
# exit 0; new remote branch created
```

Read `AGENTS.md`, `docs/cursor/CONTEXT.md`, `docs/cursor/ROOMS.md`, and the rules
block in `docs/build/MILESTONES-28OCT-1NOV.md`. Previous unmerged work remains on
its original branch. No secrets, laptop access, GitHub API or production writes.

## Acceptance

Implementation and offline tests are complete. All 29 semantic-cache cases pass.
One repository audit fails identically on starting main; see the evidence below.
No model downloaded or run here. No paid calls.
Boston image build, real-model shadow quality, founder approval and founder-browser
acceptance have not been performed. No screenshots or live success are claimed.

## Shadow implementation

- Tenant collections hold vectors and scoped IDs only. Candidate text is read
  from the existing tenant/context/region/TTL/feedback-checked Postgres cache.
- Every eligible observed miss records hit/miss/guarded/unavailable. Negation,
  changed ordered numbers, multi-turn requests and overlong input fail closed.
- The existing `_shadow` comparator and `tank.judge` evaluate would-be answers;
  daily judge budget still applies. Unscored pairs cannot graduate.
- 200 distinct input hashes and at least 99% mean agreement are required, scoped
  to tenant, region, task, policy and encoder. Existing founder authentication
  protects the explicit approval/revocation API; policy/encoder changes invalidate
  approval. `command.turn` cannot be indexed, shadowed or approved and its existing
  cache is now explicitly exact-match only.
- Existing proof shadow pairs show zero prospective cache inference cost, with
  judge cost reported separately. Per-task `semantic_cache` fields provide miss,
  would-hit, scored-hit counts and potential savings in report/API/exports.
- Existing QDRANT_URL/QDRANT_API_KEY names are wired into both regional Tank
  services. No new setting or credential, no cross-region connection.

```sh
/workspace/worker-venv/bin/python -m compileall -q tank/semantic_cache.py tank/semantic_encoder.py tank/main.py tank/proof.py
git diff --check
# both exit 0
```

## First offline validation

```sh
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres /workspace/worker-venv/bin/python -m pytest -q tests/test_tank_semantic_cache.py > tests/tank_semantic_cache/tests-first.txt 2>&1
# exit 0: 24 passed, 5 existing FastAPI lifespan deprecation warnings, 18.55s
```

Real Tank handlers, disposable local Postgres, Qdrant's in-memory implementation,
and a deliberately identical-vector encoder stub prove that numeric/negation and
scope guards override similarity. Includes 199/200 samples, .989/.99 agreement,
duplicate input exclusion, founder-only approval, revoke, policy invalidation,
chat exact matching, existing prose judge accounting/budget, reports and schema
reapplication. No inference, download or paid provider call occurred. Added explicit
token-length refusal to avoid runtime encoder truncation, and verified Docker's
COPY list includes both new modules.

## Final validation and existing-main audit failure

```sh
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres /workspace/worker-venv/bin/python -m pytest -q tests/test_tank_semantic_cache.py tests/test_tank_ladder.py tests/test_tank_batch_providers.py tests/test_t6_graduate.py tests/test_core1_proof.py tests/test_core2_baselines.py tests/test_tank_tenant_boundaries.py tests/test_tank_boots.py tests/test_tenant_scoping.py tests/test_tank_one_door.py tests/test_secrets.py > tests/tank_semantic_cache/regression.txt 2>&1
# exit 1: 170 passed, 1 failed, 5 existing deprecation warnings, 101.35s
```

The one failed test was `test_no_new_tank_bypass`. Initially it reported a test
import of `huggingface_hub` here, plus two pre-existing findings in
`tests/tank_batch_providers/verify_passthrough.py:87`. Replaced this lane's test
import with a stub module: tests do not need the real hub client. No audit waiver
was added. Verified the remaining findings on an untouched detached main worktree:

```sh
git worktree add --detach /workspace/semantic-cache-main-check 4bda46b
# exit 0
# cwd: /workspace/semantic-cache-main-check
/workspace/worker-venv/bin/python -m pytest -q tests/test_tank_one_door.py > /workspace/tervory-tank/tests/tank_semantic_cache/main-audit.txt 2>&1
# exit 1: 26 passed, 1 failed, 11.84s
# cwd: /workspace/tervory-tank
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres /workspace/worker-venv/bin/python -m pytest -q tests/test_tank_semantic_cache.py tests/test_tank_one_door.py > tests/tank_semantic_cache/targeted-final.txt 2>&1
# exit 1: 55 passed, 1 failed, 5 existing deprecation warnings, 32.50s
/workspace/worker-venv/bin/python -m compileall -q tank/semantic_cache.py tank/semantic_encoder.py tank/main.py tank/proof.py tests/test_tank_semantic_cache.py
git diff --check
# both exit 0
```

Final targeted run: **all 29 semantic-cache cases pass**, plus 26 audit tests.
The remaining single failed audit has exactly the same two findings as main:
`assembled endpoint [2703e202bb2a19bc]` and
`model/paid endpoint [d898b966b41955fb]`, both at the existing batch-proof script's
line 87. That script and the audit exceptions are unchanged in this branch.
This is the outstanding repository-check blocker; CI green is **not** claimed.
No GitHub API or hosted CI query was used. Claude opens the PR; hosted CI has not
been triggered by this thread.

The expanded tests also cover batch completion preserving the enqueue-time probe,
repeated polling without duplicate observations, malicious cross-tenant Qdrant
payloads, Qdrant failure, negated source exclusion, CPU/local-only constructor
arguments, exact revision enforcement, and refusal to truncate encoder input.
Long prose comparisons that exceed the existing judge's answer window remain
unscored instead of graduating on a truncated comparison.

## File and line references

- `tank/semantic_encoder.py:5`: model name, repository, immutable revision and
  encoder evidence identity; `:16` local CPU loader; `:42` build-only downloader.
- `tank/semantic_cache.py:35`: per-tenant collection; `:48` guards; `:61` Qdrant
  adapter; `:126` authoritative Postgres recheck; `:162` scoped evidence and
  graduation; `:200` shadow observations/indexing; `:243` founder routes;
  `:282` durable provider-batch observation snapshots.
- `tank/main.py:1033`: command.turn exact-only enforcement; `:1161` shadow lookup
  and gated serving; `:1199` / `:1318` successful code/model observation hooks;
  `:1520` reuse existing comparator/judge; `:2447` / `:2569` provider-batch hooks;
  `:4130` founder router registration. Batch cost caps and reservations unchanged.
- `tank/schema.sql:1923`: additive observation and approval tables/index.
- `tank/proof.py:129`: cache inference/evaluation cost separation; `:133` / `:180`
  per-task potential savings in founder proof, with CSV/PDF exports using existing
  report serialization. Existing page's per-task shadow comparison shows primary
  spend against zero prospective cache inference spend. No page/copy changes.
- `tank/Dockerfile:5`: module packaging and build-time download.
- `tank/requirements.txt:28`: existing Hermes dependency pins reused.
- `docker-compose.yml:208`, `docker-compose.za.yml:129`: existing local Qdrant
  setting names passed to Tank; no secret values.
- `tests/test_tank_semantic_cache.py:1`: real route/SQL/Qdrant offline proof.
- `tests/tank_semantic_cache/*.txt`: raw test output, including failures.

## Founder graduation contract (after review, merge and deployment)

Existing founder authentication is required for both routes; tenant UUID is always
required. No approval was performed by this thread.

1. `GET /v1/semantic-cache/{task_type}?tenant_id=...` returns the current
   `policy_hash`, `encoder_id`, sample count, agreement, proven and approved flags.
2. `POST /v1/semantic-cache/{task_type}/approval` accepts `tenant_id`, those exact
   hashes, and `approved: true`. It refuses fewer than 200 distinct scored inputs,
   agreement below .99, mismatched policy/encoder or `command.turn`.
3. The same endpoint with `approved: false` revokes. Evidence is rechecked before
   serving; new policy/encoder versions require fresh evidence and approval.

The index starts empty and fills only from eligible, privacy-safe real answers.
No production fixtures, corpus backfill, SQL edits or approval seeds are shipped.
Stub tests prove the integration and guardrails, **not** the model's actual
paraphrase accuracy. Boston must build the image and collect real shadow samples;
founder-browser acceptance and screenshots remain outstanding.

## Push record

All pushes target `codex/tank-semantic-cache-2`; never main.

```sh
git commit -m 'Pin CPU semantic encoder for image-build-only download'
git push
# b6ff19c; exit 0
git commit -m 'Add tenant-isolated semantic shadow cache and founder gate'
git push
# 68834b3; exit 0
git commit -m 'Prove semantic cache isolation and graduation offline'
git push
# 4b775c4; exit 0
```

Final commit includes batch completion coverage, regression evidence and this
review description. The final branch/commit are reported to the founder after git
push completes. No merge, deployment or founder approval is performed.

## PR #388: merge main and preserve RouteLLM (28 Oct)

Merged main `678d47e` into the existing branch `codex/tank-semantic-cache-2`.
This section supersedes the earlier main-baseline audit count and Docker layout
notes. No second PR, merge to main, deployment, model download or paid call.

Changes resolving the four conflicts:

- `tank/main.py:1557`: one `_shadow` accepts both `routellm=` and `cache_content=`.
  RouteLLM keeps its measured inference receipt and `routellm_shadow.save` path;
  cache shadows keep the supplied answer, existing judge, budget behavior and
  returned agreement. Both existing route hooks remain active independently.
- `tank/proof.py:134`: one comparisons query preserves RouteLLM's actual model
  costs, known-price/success filters and sample savings. Embedding rows retain
  zero prospective inference cost and separate evaluation spend. The semantic
  per-task summary remains at `:145`, attached to task rows at `:192`.
- `tank/schema.sql:1922` / `:1954`: retain the semantic tables and all incoming
  RouteLLM columns/indexes and subsequent main migrations. Both suites exercise
  schema reapplication.
- `tank/Dockerfile:5`: main's heavy-layer COPY now also includes
  `semantic_encoder.py`. The same heavy RUN installs dependencies and executes
  both `python routellm_build.py /opt/routellm` and `python semantic_encoder.py`
  before main's unchanged `COPY *.py ...`. Ordinary application edits therefore
  do not invalidate the model-download layer. No hand-maintained module list.
- `tests/test_tank_semantic_cache.py:282`: update the existing Docker assertion
  to enforce heavy-layer ordering and wildcard code COPY.
- `tests/test_tank_shadow_coexistence.py:14`: enable both experiments for the same
  tenant/task and real route; verify both shadow rows on one ledger, unchanged
  live answers, separate inference/judge costs, semantic summary and tenant seal.
  All inference and provider responses are stubbed; Qdrant is in-memory and
  Postgres databases are disposable and local.

Exact commands and results (cwd `/workspace/tervory-tank` unless stated):

```sh
git fetch origin main
# exit 0; 4bda46b -> 678d47e
git merge --no-commit origin/main
# exit 1; expected conflicts in Dockerfile, main.py, proof.py, schema.sql
# Resolved the four files as described above, retaining both features.
/workspace/worker-venv/bin/python -m compileall -q tank/main.py tank/proof.py
# exit 0
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres /workspace/worker-venv/bin/python -m pytest -q tests/test_tank_semantic_cache.py tests/test_tank_routellm.py tests/test_tank_one_door.py tests/test_tank_shadow_coexistence.py tests/test_train1_dockerfile.py > tests/tank_semantic_cache/merge-main-tests.txt 2>&1
# exit 1: 40 passed, 30 setup errors (missing jiter), 1 known audit failure
/workspace/worker-venv/bin/pip install --cache-dir /workspace/scratch/pip-cache -r tank/requirements.txt > tests/tank_semantic_cache/merge-main-dependencies.txt 2>&1
# exit 0; installed main's pinned jiter==0.18.0 and openai==2.54.0
# No model artifacts are downloaded by this dependency installation.
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/postgres /workspace/worker-venv/bin/python -m pytest -q tests/test_tank_semantic_cache.py tests/test_tank_routellm.py tests/test_tank_one_door.py tests/test_tank_shadow_coexistence.py tests/test_train1_dockerfile.py > tests/tank_semantic_cache/merge-main-final-tests.txt 2>&1
# exit 1: 70 passed, 1 failed, 6 warnings, 44.79s
```

Passing tests: all **29 semantic-cache**, **13 RouteLLM**, **1 coexistence**,
**1 Docker packaging**, and **26 one-door audit cases**. The one failed test is
`test_no_new_tank_bypass`, reproduced on untouched current main:

```sh
git -C /workspace/semantic-cache-main-check status --short
# exit 0, clean
git -C /workspace/semantic-cache-main-check switch --detach 678d47e
# exit 0
# cwd: /workspace/semantic-cache-main-check
/workspace/worker-venv/bin/python -m pytest -q tests/test_tank_one_door.py > /workspace/tervory-tank/tests/tank_semantic_cache/merge-main-audit-baseline.txt 2>&1
# exit 1: 26 passed, 1 failed, 14.75s
# cwd: /workspace/tervory-tank
git diff --name-only --diff-filter=U
# exit 0, no unresolved files
git diff origin/main --check -- tank tests/test_tank_semantic_cache.py tests/test_tank_shadow_coexistence.py
# exit 0
```

Both branch and current main report exactly these three findings:

- `tests/tank_batch_providers/verify_passthrough.py:87`, assembled endpoint
  `2703e202bb2a19bc` and model/paid endpoint `d898b966b41955fb`.
- `tests/test_command_streaming.py:81`, model/paid endpoint `20a97d67b3598de5`.

No new audit findings, waivers or changes to those files. The full staged
whitespace check also reported upstream vendored-license whitespace; those
licenses remain byte-for-byte main. The scoped branch-to-main check passes.
No claim that hosted CI is green or that founder-browser acceptance occurred.
No Docker build was run here because it would download the model artifacts.

Final merge publication:

```sh
git commit -m 'Merge main into semantic cache and preserve RouteLLM shadows'
git push origin codex/tank-semantic-cache-2
```

The final push result and merge commit are reported in the task response. This
updates the same PR #388. The founder still performs the PR merge.
