# Connect room completion events through Tank, with Rig price history

Branch: `codex/e1-e3-tenant-bus`, continued from `origin/main` at `73a0e2f`.
Claude opens the draft PR. No GitHub API, deployment, merge, or production SQL was used.

Rooms previously had no event corridor, and #386 updated Rig's current price without retaining history. This change adds the shared job contract and six completion events through Tank's existing Redis. Rig consumes Tiger price changes into the newly authorized append-only table. The founder can inspect a product's history as JSON in Workspace; there is no page or new page wording.

## Changes and boundaries

| File and line | Change |
| --- | --- |
| `agents/_chassis/chassis/job_contract.py:11` | One shared Pydantic `Job`: tenant, region, agent, skill, input, priority, engine; mapping to/from existing room rows. |
| `agents/_chassis/chassis/app.py:118`, `:198` | Accept the shared contract alongside the existing job request and construct execution context from the stored row. The shared engine is mapped into the existing handler input at execution time, including when input omits it or names a conflicting engine. Reject incorrect room/region and malformed metadata. Existing job-table columns stay unchanged; priority/region/engine use reserved JSON input metadata. |
| `agents/base/room.py:293`, `:324`, `:463` | Map Base's existing task shape and take tenant authority from the task row, overriding conflicting JSON input. |
| `tank/event_bus.py:78`, `:115`, `:192` | Tenant/event stream keys, atomic deduplication, consumer group, claims, ACK/failure settlement, bounded dead letters, and authenticated private room endpoints. Strict event-specific facts reject arbitrary extra fields. |
| `tank/main.py:580`, `:3845` | Permit and mount the private event corridor. Existing routing, queue, ledger and cache logic is unchanged. |
| `agents/_chassis/chassis/events.py:19`, `:34` | Rooms publish through Tank with their existing room credential and stored tenant context. No Redis credential is given to rooms. Redis/Tank failure logs a fixed message and returns; a process backs off for 30 seconds after a failed attempt. |
| `agents/rig/schema.sql:59` | Add only `agent_rig.price_history` and its tenant/product index. `event_id` is the primary key, satisfying uniqueness. Startup applies this through the existing `PgStore.apply_schema` helper. |
| `agents/rig/rigbox/price_events.py:17`, `:45`, `:62` | Resolve the actual product ID from the tenant's catalogue, under its existing catalogue lock; insert before ACK, `ON CONFLICT(event_id) DO NOTHING`. Never update history. Ignore products that were removed, rebound, or became feed-owned. |
| `agents/rig/app.py:389` | Start/cancel the sole consumer with the existing Rig lifespan. Poll the room's own catalogue tenants every five seconds. |
| `tank/rig_brain_routes.py:40` | Founder-only `GET /v1/agents/rig/price-history`, bounded by required tenant/product, paginated, `private, no-store`. Clients and room credentials cannot use this reader. |
| `workspace/lib/tank.ts:8`, `workspace/app/rig/price-history/route.ts:10` | Browser-accessible JSON proxy using Clerk founder identity and the existing server-side Tank helper. Caller headers cannot override identity. Errors have empty bodies; no new page/copy. |
| `tests/tenant_bus/` | Offline delivery, isolation, producer, shared-job, real Tank, and Workspace JSON checks; saved proof below. |

### Completion producers

| Event | Completion location | Facts and emission unit |
| --- | --- | --- |
| `base.record.enriched` | `agents/base/room.py:397` | Saved record/task IDs, confidence, database check timestamp; one per successfully completed record/task. Failed/queued records do not publish. |
| `tiger.price.changed` | `agents/tiger/watch.py:1121`, `:1275`; `agents/tiger/rig_watch.py:49` | Watch/observation IDs, bound SKU, hashed page identity, previous/new confirmed prices, currency and observation time. One per changed product, even when mail alerts are disabled. A watch shared by multiple SKUs emits one distinct event for each SKU. An ordinary unbound watch emits once with `sku: null`; Rig acknowledges it without inventing a product. Initial, unchanged or incomplete readings do not emit. |
| `marketlab.signal.scored` | `agents/market_lab/core/jobs.py:209` | Saved opportunity/signal ID, score, rank, time; one per scored row. This is main's existing ranked opportunity/moves completion path. |
| `zenas.regulation.changed` | `agents/zenas/pool/nightly.py:87`, `agents/zenas/pool/ingest.py:80` | Hashed document/version IDs after a newly saved version. Re-reading the same version emits nothing. Public regional law uses the existing platform tenant, not any client's tenant or a cross-tenant broadcast. `agents/zenas/pool/Dockerfile:16` includes the shared publisher in the existing pool image. |
| `radix.finding` | `agents/radix/scanlib/orchestrate.py:121` | Scan ID, finding ordinal and severity, after findings are committed. File paths, code and fixes are excluded. |
| `tisan.build.ready` | `agents/tisan/app.py:64` | Job ID and hashed site identity, after successful scaffold completion. Failure and eval-only calls do not publish. |

Event bodies carry identifiers and numeric/status facts, never record text, law text, prompts, product descriptions, URLs or credentials. The sole subscription is Rig to `tiger.price.changed`; no other consumer was added. #386's existing direct current-price/stock delivery remains intact.

### Delivery and tenant scope

- The exact data stream key is `tervory:<tenant UUID>:<event>`. The consumer group is the authenticated room agent (`rig` for the only implemented subscription).
- Tank validates the existing `TANK_KEY_<AGENT>` credential and home region. Tenant authority is the private room's trusted header, populated from a stored task or its own catalogue tenant. These are existing service-wide room credentials, not new tenant credentials. Browsers/clients/Workspace keys cannot call the bus. No message body can select a tenant, Redis key or group; added tenant fields are refused and query-string tenant overrides are ignored.
- Delivery is at least once. ACK happens only after the history insert commits. Pending deliveries are reclaimed after 30 seconds. Recovery follows every Redis scan cursor: an empty first scan page cannot hide an abandoned delivery behind 200 busy pending entries. The fifth failed delivery is moved atomically to `<stream>:dead` and acknowledged. Abandoned deliveries also count; after five handler deliveries, the next claim dead-letters the entry instead of invoking the handler again. Settlement requires the current consumer's ownership.
- Data and dead-letter streams each use exact `MAXLEN = 10000`. Producer deduplication lasts seven days; event IDs are deterministic and include the tenant. Rig's database uniqueness prevents duplicate history permanently, including delivery after the Redis deduplication window.
- Publication is deliberately best effort when Redis/Tank is unavailable, as required: product work stays saved, a fixed warning is logged, and that event is not durably spooled for later publication. Stream trimming can discard entries beyond the retention bound. No backfill of pre-deployment changes is claimed.
- No new setting, provider, subscription, model route or service is required. Existing `REDIS_URL`, `TANK_URL`, room-key settings, `TANK_REGION` and `TERVORY_ADMIN_USER_IDS` are reused by name only.

## Verification

[REVIEW-PROOF.txt](REVIEW-PROOF.txt) contains the current amended-brief checks, exact commands, real Tank startup tail and returned history JSON. [PROOF.txt](PROOF.txt) retains the broader initial regression runs and the unchanged Workspace build output. All data in that file belongs to disposable offline fixtures. The test starts `uvicorn main:app` and runs the actual Rig lifespan. Rig startup launches the history consumer automatically and shutdown stops it. Only unrelated scheduled room work is parked in this proof; the consumer, its transport, schema helper and database writes run normally. HTTP outside loopback is blocked by a closed local proxy and LiteLLM points to a closed local port. Expected startup warnings concern unavailable gold/reference services, not a failed Tank startup.

| Check | Result |
| --- | --- |
| `pytest tests/tenant_bus -q -s --disable-warnings` with the local store setting in `REVIEW-PROOF.txt` | **24 passed**. Includes real Redis ACK/claim/DLQ/trimming, recovery beyond the first pending page, two tenants, six producers, shared/legacy jobs, engine execution, row-owned tenant scope, and saved-page Tiger → real Tank → Redis → Rig startup consumer → founder JSON. |
| Current related regression run (exact list in `REVIEW-PROOF.txt`) | **74 passed**: chassis, Base, Market Lab, secrets, Tank startup and one-door checks. |
| Earlier broader regression run (exact list in `PROOF.txt`) | **143 passed**. Tank startup test boots twice against the same disposable database. |
| `pytest tests/test_radix_gold.py -q --disable-warnings` | **6 passed** in a separate process. |
| Zenas corpus/version/region/load-job regressions (exact list in `PROOF.txt`) | **18 passed**. |
| `node tests/tenant_bus/workspace.cjs` | Exit 0: `PASS: founder-only JSON, client/forged identity refusal, trusted tenant, fixed Tank path, no-store, empty error bodies.` |
| `node node_modules/typescript/bin/tsc --noEmit` in `workspace/` | Exit 0, no output. |
| `next build` via the exact command in `PROOF.txt` | Exit 0; `/rig/price-history` is a dynamic route. |
| Ruff commands and `git diff --check origin/main...HEAD` | Exit 0; `All checks passed!`; no whitespace errors. |

```sh
/tmp/command-repo-venv/bin/ruff check tank tests agents/_chassis/chassis agents/base/room.py agents/tiger/rig_watch.py agents/tiger/watch.py agents/rig/app.py agents/rig/rigbox/price_events.py agents/market_lab/core/jobs.py agents/zenas/pool/nightly.py agents/zenas/pool/ingest.py agents/radix/scanlib/orchestrate.py agents/tisan/app.py --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
git diff --check origin/main...HEAD
node tests/tenant_bus/workspace.cjs
```

Reproduction requires the repository's Python test dependencies, Workspace dependencies, and disposable local Postgres. Set `TENANT_BUS_REDIS_URL` only to a dedicated local test Redis: the harness clears its selected database. Without that setting the harness starts/removes a throwaway `redis:7.4.12` container. Postgres tests create/drop a random test database; the history schema is applied twice through the existing helper.

One earlier combined regression invocation included `test_radix_gold.py` after Tiger in the same Python process. Its six Radix tests failed because the existing shared import name `gold_sources` resolved to Tiger's module. The separate Radix invocation above passes; those existing gold modules and tests are unchanged. The final 143-test group excludes that file and passes. Full CI and independent review are not claimed.

### Amended-brief review findings

The required branch checkout and `ls` of every named file succeeded before review. No named file was missing. Two functional gaps were reproduced and fixed on this same branch:

- **Shared engine execution** — before the fix, a shared Market Lab job with `engine: "ffl"` reached the handler with no engine. `agents/_chassis/chassis/app.py:198` now maps the authoritative engine into the handler input while retaining the original stored contract. `tests/tenant_bus/test_jobs.py:75` covers omitted/conflicting input engines and legacy compatibility.
- **Pending delivery recovery** — before the fix, `XAUTOCLAIM COUNT 20` examined only the first 200 pending entries and ignored its continuation cursor, leaving a later abandoned delivery unrecovered. `tank/event_bus.py:138` follows that cursor. `tests/tenant_bus/test_recovery.py:10` reproduces 200 busy deliveries followed by one abandoned delivery; it failed before the fix and passes now.

The previous cycle proof called the consumer helper directly. `tests/tenant_bus/test_tiger_history.py:72` now also proves the normal Rig startup/shutdown wiring, rather than assuming that part works. The current proof is saved in `REVIEW-PROOF.txt`. No additional gap was found in the six completion hooks, append-only schema, tenant boundaries, founder reader or outage behavior. Live evidence remains outstanding as described below.

## Founder/assessor acceptance — still pending

Offline proof is complete; live acceptance, screenshots, CI and independent assessment remain pending. Nothing was deployed or written to production to manufacture that proof.

1. After founder-approved deployment of Tank and the affected room images, select an existing real, unfed Rig product with its public page URL and a confirmed Tiger baseline reading. Use the actual tenant UUID and catalogue product ID; the usual product ID is its SKU. Do not use the fixture tenant or item from `PROOF.txt` on a live screen.
2. The assessor triggers the existing Tiger `check` job for that tenant/URL from the cloud after the source page has a real price change. The existing private room `POST /jobs` accepts `{"tenant_id":"<real tenant UUID>","kind":"check","input":{"url":"<real public product URL>"}}`. No new run button was added; the existing scheduled check also follows this path. Require a successful confirmed changed-price reading in the same currency.
3. Signed in as the founder, open **`https://app.tervory.com/rig/price-history?tenant_id=<real tenant UUID>&product_id=<URL-encoded catalogue product ID>`**. Click the browser's **Reload** after the check finishes and the next Rig poll (normally within five seconds). Verify one new history row containing the source's real `price`, `currency`, `observed_at` and an `event_id`; earlier history remains. Repeat the same completed event: no duplicate row. Attach the founder's before/after browser screenshots and the real observation/event IDs.
4. Open the same JSON route for store B and the same product ID: it must contain only B's history. Open the route as a client user: access must be refused. These live checks and screenshots belong to the independent assessor; this PR does not mark the founder's DONE condition complete.
