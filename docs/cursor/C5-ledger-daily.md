# C5 — Ledger: daily spend by rung and by task type

**Goal:** a client sees, at a glance, where their money went this month and that work is moving down the ladder.

**Files you may change:** `workspace/app/ledger/*`, `workspace/lib/tank.ts`, and in `tank/main.py` add ONE new read-only endpoint (do not change existing ones).

**Tank:** `GET /v1/ledger/daily?tenant_id=…&days=30` (require `X-Tank-Key`, scoped by `tenant_id`) returning
`{ "days": [ {"day":"2026-10-12","rung":1,"calls":…,"cost_usd":…,"accepted":…,"rejected":…}, … ], "by_task": [ {"task_type":…,"calls":…,"cost_usd":…,"cache_hits":…,"accepted":…,"rejected":…}, … ] }`
using `date_trunc('day', ts)` on `tank.ledger`. Exclude task types ending in `#shadow`.

**Workspace Ledger page, under the existing tiles:**
- "Spend by day" — stacked bars per day, one colour per rung (1 frontier, 2 owned, 3 code, 4 cache), tooltip with calls and cost. Hand-rolled SVG or a small dependency (recharts is fine); must read in light and dark.
- "Calls moving down the ladder" — a line of the share of calls at rungs 2–4 per day.
- "By task type" — a table sorted by cost: task type, calls, cost, cache hits, accepted/rejected, cost per accepted.
- Empty state: "No calls yet. Ask something in Chat."

**Done when:** PR with screenshots using the AmmoSync tenant's data (the founder can sign in to check) and a test for the SQL in `tests/`.
