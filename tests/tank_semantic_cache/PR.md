# Tank semantic cache: tenant-isolated shadow evaluation

Work in progress on `codex/tank-semantic-cache-2`, starting from main `4bda46b`.
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

Implementation/tests pending. No model downloaded or run here. No paid calls.
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
