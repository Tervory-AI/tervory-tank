# Tenant-scoped job contract and Redis event bus

Branch `codex/e1-e3-tenant-bus`, from `origin/main` at `73a0e2f`.

Scope: shared job contract without room-table changes; tenant/event Redis Streams,
agent groups, acknowledgements, five-attempt dead letters, bounded retention;
six completion producers and one Rig price-history consumer reusing #386.
Redis failure must not fail product work. Event payloads contain IDs and facts only.
No page or model changes. Offline evidence and exact assessor steps will be recorded here.

Implementation and verification are in progress. Claude opens the draft PR;
independent live acceptance remains pending.
