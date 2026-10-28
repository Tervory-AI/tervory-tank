# D1 / D2 / D3 — authoritative agent memory

New memories now commit a PostgreSQL record and its index job together before
calling the encoder or Qdrant. A vector failure leaves the record readable and
the job available to a restarted worker. No production database was accessed,
no legacy data was migrated, and no client publication policy was enabled.

## What changed

- `hermes/record_schema.py` is the single schema generator. Its marked block is
  checked into every agent's `schema.sql`, including `tank/schema.sql`. Run
  `python hermes/record_schema.py` after editing it. The record has all requested
  fields; separate tables hold index jobs, publication policy and publication
  attempts. Schema application is additive and idempotent. Hermes preserves the
  existing chassis ownership convention so restricted agent startup can reapply
  the tables regardless of service startup order.
- New Qdrant collections store row IDs and scope/index metadata, never claims,
  evidence or private metadata. Recall hydrates and rechecks tenant, agent, tier
  and current encoder against SQL. Old `mem_*` collections remain readable in
  place. New records use request-ID idempotency; legacy semantic deduplication
  does not merge new authoritative claims.
- A durable worker retries failed indexing with backoff and enqueues rows whose
  `embed_model` differs from the current pin. It uses #388's exact CPU encoder
  module and pinned weights. Model versions have separate vector collections;
  the old Zenas law encoder and law collections remain unchanged. Claims beyond
  the encoder's 512-token limit still persist in SQL but remain pending indexing.
- Client reads remain sealed by tenant. Platform reads use
  `00000000-0000-0000-0000-000000000001`, matching `tank/training.py`.
  `/reference-corpora` registers the existing Zenas law pool as read-only and
  points to its existing `/law/search`; no corpus is copied or moved.
- Publication is an explicit founder-only operation. No policy row means OFF.
  Opt-in is keyed by tenant inside the named agent's schema. Publication strips
  identifiers with code, drops private metadata and internal evidence, and logs
  actor, time, source row and result, including refusals while OFF. Repeated
  publication is idempotent but every attempt is logged. No startup, memory write
  or retry job invokes publication.
- The existing founder chat accepts `Remember that <fact>` (Tank memory), or
  `Remember for tiger that <fact>` (a named configured agent). It verifies the
  founder identity, writes through Hermes and creates the existing zero-cost
  command receipt. The response uses the existing chat renderer and displays the
  stored claim. No new UI or navigation was added.

## Acceptance proof

**No existing founder memory view was found. The view waits for Figma.**
The existing Ghost/Autumbra incident panels are not a general agent-memory view.

`proof-row.json` was read directly from an isolated test PostgreSQL database after
calling the real `command.route_turn` -> Hermes `/founder/memories` -> SQL path.
Only the local encoder and Tank receipt dependency were substituted. The test
fails if the paid/model routing path is called. All identifiers and content are
synthetic fixtures.

| Field | Observed value |
| --- | --- |
| claim | `fixture deliveries happen on Tuesdays.` |
| evidence | `urn:tervory:command:33333333-3333-4333-8333-333333333333` |
| confidence | `0.5` — an unscored default, not a model's certainty |
| last_verified | `null` — no verification claimed |
| tier | `client` |
| embed_model | `offline-pin-v1` — stub used only by this offline test |

The test also reads the same row through `/founder/records` and verifies that
publication returns 403 while disabled. The founder-only Tank read proxy is
`GET /v1/memory/records?tenant_id=<uuid>&agent=<name>` for the future view.

## Tests and limits

Completed on the branch rebased onto main `b08ff957d0cb77b0a57ff3698d737cc1be5ac694`:

- **24 passed:** `tests/test_agent_memory_records.py`, including empty/reapplied
  schema and restricted role, committed row-before-vector ordering, lost vector
  acknowledgement/restart retry, SQL/encoder failure, stale-only re-embedding,
  tenant/agent/tier isolation, scoped deletion and recreation, every requested
  identifier category, default-OFF publication and audit, per-client/agent opt-in,
  and founder chat-to-row acceptance.
- **47 passed:** existing Hermes, agent role, secret and model-boundary checks:
  `tests/test_hermes_memory.py tests/test_agent_roles.py tests/test_secrets.py
  tests/test_tank_one_door.py`.
- **66 passed, 38 skipped:** existing command, chassis and Zenas law checks:
  `tests/test_command.py tests/test_agent_chassis.py
  tests/zenas_za_meaning_search/test_hermes_law.py`. The skipped cases require
  their separate database/integration configuration.
- Ruff `E9,F` and `git diff --check` pass.
- `tests/test_schema.py` has one existing static failure in the untouched
  `tank.case_study_clients` DO block (it checks `IF to_regclass`, while the test
  only accepts `IF NOT EXISTS`). Reproduced against the starting main before
  this change. The new memory DDL was executed twice successfully in PostgreSQL.

SQL evidence used PostgreSQL 18.6 compiled to WASM (PGlite 0.5.13) through its
loopback PostgreSQL protocol server, with asyncpg 0.30.0 and local Qdrant 1.20.0.
It did not use SQLite or a mocked SQL engine. Native PostgreSQL 16, concurrent
multi-process load, the Docker image build and live founder/browser interaction
were not exercised here. No weights were downloaded and no model was called
by the tests; these tests prove persistence and routing, not embedding quality.

To repeat against a disposable native PostgreSQL database, install the existing
Tank/test requirements, set `MEMORY_TEST_DATABASE_URL` to its loopback URL, then:

```sh
python -m pytest -q tests/test_agent_memory_records.py
```

The tests create and remove uniquely named `agent_memtest_*` schemas. With no
test database URL, SQL cases skip. Set `MEMORY_PROOF_PATH` to a temporary JSON
path to capture a new acceptance row. The current default CI smoke command does
not run this new suite automatically; the command above is the targeted check.

## Decisions and rollout boundaries

- No backfill, export, production migration command, publication or deployment
  was performed. After a reviewed merge/deploy, schema startup creates empty
  tables and only subsequent writes create memory records.
- Hermes reuses the existing regional Postgres, Qdrant and credentials. No new
  service, credential or paid route is added. Compose passes its existing
  `DATABASE_URL` and `TERVORY_ADMIN_USER_IDS` to Hermes. Its build context becomes
  the repository root to copy the unchanged #388 encoder and approved PII
  detector into the image. Both models download only in image dependency layers.
- Founder opt-in needs a reviewed identity inventory (`names`, `emails`,
  `phones`, `addresses`, `client_domains`, `reviewed: true`). Missing fields or
  missing review refuse publication. Deterministic rules cannot discover every
  unknown name/address in arbitrary prose; the inventory must cover the client
  identities. This is not a claim of universal automatic anonymization. Keep
  every real client OFF until the founder deliberately enables the named agent.
- `POST /v1/memory/publish-policy` forwards the scoped policy and inventory;
  `POST /v1/memory/publish` takes `tenant_id`, `agent` and `source_row`. Both use
  existing founder authorization. Enabling policy alone moves no rows.
- Individual deletion now requires the tenant UUID. The chassis client includes
  it and legacy vector deletion also checks that tenant. Retry jobs cannot remove
  a subsequently recreated row's index or another tenant's point.

Changed: SQL-first memory, three tiers, audited founder opt-in publication, and
the founder chat save path. Tests: the offline checks and actual test row above.
Screenshots: none; no UI changed, and the memory view waits for Figma.
