# C14 — The ladder: free rungs run, paid rungs pause for approval

**Founder rule (14 Oct 2026):** every run is a ladder of steps. Free steps run automatically. When the next step is paid (Brave search, a model pass in a batch run, any data vendor), the run **pauses** at that step and waits for an admin to approve it, unless that rung is set to **auto**. Brave stays available as a rung. Nothing is removed; it waits for approval.

**Start after B-3 is merged** (Base then runs in its own room, `agents/base/`). **Lane:** this brief allows changes to the Base worker in `agents/base/`, the skill runner in `tank/main.py` (AGENTS.md rule 6), plus `tank/schema.sql` (additive), `tank/skills/base.find_site/1.5.0/` (new version), the Workspace page `workspace/app/approvals/*` with `workspace/lib/tank.ts`, and new tests.

## Rungs
- `tank.paid_routes (route, mode off|approve|auto)` exists (PR #41). Routes now: `search.brave`, `model.base.extract`, `model.base.business_data`. Seed the two model routes as `approve`. Interactive chat in the Workspace (a person asked) is not a batch rung and is not paused.
- A skill declares its paid rung in `skill.yaml`: `paid_routes: [search.brave]`. `base.find_site@1.5.0` returns `{status: "needs_approval", route: "search.brave"}` when SearXNG and the free guesses found nothing and Brave is not yet allowed. It never calls Brave unless the runner has handed it the key.

## Pausing and resuming
- New record status `awaiting_approval` with `passes.<pass>.awaiting = route`. The worker finishes every free step it can and parks the record at the first paid rung; other records keep moving.
- `tank.approvals (id, tenant_id, batch, route, scope once|batch, approved_by, approved_at, count_at_approval)`. Approving a route for a batch requeues exactly the parked records for that route and lets that rung run for them (`once` = these records only; `batch` = the rest of this batch too).
- Endpoints (founder/Workspace key only, agent keys refused): `GET /v1/approvals/pending` (per tenant, batch and route: records waiting, estimated cost from the ledger's average for that rung), `POST /v1/approvals` to approve, and `PUT /v1/paid-routes/{route}` for off/approve/auto.
- Workspace page **Approvals** (founder only): a list of "Batch X: 412 records waiting for Brave search, est. $0.83" with Approve once, Approve this batch and Set to auto buttons. Every approval is written to `policy_log`.

## Done when
CI green; a batch with records SearXNG cannot place pauses them at `search.brave` while the rest finish; approving resumes exactly those records; `auto` skips the pause; `off` ends them with "paid route off"; agent keys cannot approve (tested); no skill receives `BRAVE_API_KEY` for a record that is not approved (tested).
