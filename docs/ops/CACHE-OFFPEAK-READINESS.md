# Cache and off-peak rollout handoff

This is **offline fixture proof**, not evidence that Boston is enabled. Run in an
isolated cloud checkout, using the repository's pinned development dependencies:

```sh
python scripts/cache_rollout_readiness.py
```

The command creates disposable local PostgreSQL with the existing `pgserver` dev
dependency, runs only seven named acceptance modules, and removes its database.
It ignores inherited database URLs, sets the optional layers off initially, and
lets each test explicitly enable its layer. pytest blocks external sockets and
DNS; only local PostgreSQL is reachable. Gateways, encoders, clocks and prices
are fixtures. No model download, paid request, GPU or service activation occurs.
The test subprocess has a ten-minute deadline and each test a sixty-second
limit. Any failure, error, skip or empty result prevents `ready: true`.

## Evidence covered

| Requirement | Acceptance evidence |
| --- | --- |
| Exact-repeat reuse, zero cost, distinct receipts | `test_engine_exact_cache.py`: real SQL/transcript lookup and fake gateway |
| Tenant and user isolation, unsigned exclusion, TTL and policy eligibility | `test_engine_exact_cache.py` |
| Policy correction and negative feedback invalidate reuse | `test_cache_rollout_readiness.py`; gateway refresh after rejected ledger in `test_engine_exact_cache.py` |
| Embedding dedupe across consumers and simultaneous misses | `test_engine_embedding_cache.py`: local Qdrant and fake CPU encoder |
| Cache outage fallback | `test_engine_embedding_cache.py`: failed Qdrant cache falls through to computation, with zero dollar savings |
| Truthful C1/C4/C5 receipts, no hit inferred from missing signals | Exact, embedding and prompt cache suites; combined returned receipt regression |
| Ask prevents enqueue until approved; deferral retains that grant and run fingerprint, dispatches once | `test_cache_rollout_readiness.py`: real approval journal, queue and ledger, frozen clock |
| Deadline expiry never dispatches; feasible plans respect completion allowance | `test_offpeak_deadline.py`; `test_engine_scheduling.py` |
| No optional layer enabled by an absent or invalid flag | `test_engine_layers_off.py` |

A policy instruction correction is tested here; full Hermes memory integration
belongs to its owner. Redis failure handling inside the deployed LiteLLM version
is **not** certified by the Qdrant outage fixture. Before enabling C1 broadly,
the coordinator must verify Redis outage/miss fallback and recovery against the
deployed gateway without an unapproved paid call. No synthetic Redis result
should be reported as live outage evidence.

## Reconciliation with Tank #755

Inspected main `350f27e5` and #755 head
`22e43578a70b8967c908d8fb173fe6124a319ded` before editing. Main already includes
`bf52e188` (C1), `201e0d49` (expiry/receipts), `570dd51f` (C4), `0adf8328`
(C5) and `1ed846f4` (explicit opt-in for C1/C4/I8).

The exact two-tip comparison is reproducible:

```sh
git diff 350f27e5 22e43578a70b8967c908d8fb173fe6124a319ded -- tank/exact_cache.py tank/main.py litellm tests/test_engine_exact_cache.py
```

#755's remaining C1 implementation uses older engine helpers, a different default
TTL, and a standalone callback rather than main's composed tenant trace callback.
Its returned receipt merge and SQL receipt merge lose other layer details. It
also carries runtime config and older versions of concurrent work. Do not apply
that branch wholesale. Current main already wires C1 into Tank and LiteLLM with
the same opt-in setting. This readiness PR extends main; it does not replace or
repeat #755's runtime changes. The coordinator can mark #755 superseded after
reviewing this comparison; no close, merge or branch rewrite is performed here.

## Coordinator execution gates (names only)

1. Review and merge the source/readiness PR only after hosted required checks
   pass. No runtime config is changed here. Any needed Compose or `litellm/`
   change requires its own small PR under AGENTS rule 11, before dependent work.
2. Preserve existing paid-step Ask/Auto controls, tenant policy eligibility and
   task TTLs. Approval grants remain tied to their tenant, run and request hash;
   a queue entry grants no spending authority.
3. Inspect only setting names: `ENGINE_C1_ENABLED` in Tank and LiteLLM;
   `ENGINE_C4_ENABLED` in Tank and Hermes; `ENGINE_I8_ENABLED` in Tank.
   Existing connections are `QDRANT_URL` and `QDRANT_API_KEY`; the existing Redis host and
   port are defined in the gateway roster. Never copy values into handoff or logs.
4. Enable one reviewed layer at a time through the coordinator's production
   procedure. Verify repeat/miss counts, tenant/user separation, feedback refresh,
   layer receipts and queued approval/deadline behavior before proceeding.
   C4 compute savings are not dollar savings; unknown prices remain unknown.
5. Roll back through the same procedure by disabling `ENGINE_I8_ENABLED`,
   `ENGINE_C4_ENABLED` and `ENGINE_C1_ENABLED` in the corresponding services.
   Do not delete queue, approval or ledger rows. Existing explicit off-peak jobs
   and legacy SQL cache behavior predate the optional flags: disabling I8 stops
   automatic scheduling, not all queued work. Inspect outstanding jobs and their
   deadlines/approval state through existing tenant-scoped status routes.

`ENGINE_LOCAL_URL`, `ENGINE_LARGE_URL` and Langfuse configuration are not
prerequisites for these offline proofs. Their absent production configuration
must not be presented as local-serving or tracing readiness. Live acceptance,
Redis outage validation, production enablement and rollback execution remain
coordinator gates; this job changes none of those settings.
