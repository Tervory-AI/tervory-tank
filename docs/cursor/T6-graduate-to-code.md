# T-6 — Tank: graduate a task from a paid model to plain code

**Why this matters:** this is the core of Tank. Today a task can graduate from an expensive model to a cheaper model (shadow runs, a judge scores agreement, the founder promotes). The founder's goal is the last rung: **no model at all**. Tank must prove, with evidence from live traffic, when a code skill can replace a model (or a paid tool) for a task, and only then switch it over, with approval.

**Lane:** this brief allows changes to the shadow/graduation code in `tank/main.py` (`_shadow`, `/v1/graduation/*`), `tank/schema.sql` (additive), `workspace/app/admin/*` (founder console graduation view), `workspace/lib/admin.ts`, and new tests. Not the router's model call, not the queue worker.

## The ladder (rungs as stored in `tank.ledger.rung` / `tank.policy.rung`)
| Rung | What answers | Cost per call | Status |
| --- | --- | --- | --- |
| 1 | A paid frontier model: the cheapest one with funds, picked live per call | paid | built (PR #41) |
| 2 | An owned model: open-weight, running on our own server | server cost only | not built (T-7) |
| 3 | Code: an approved skill with no model | zero | this brief |
| 4 | Cache: the same question already answered (tenant- or platform-scoped) | zero, no call | built (exact match) |

Every task starts where it must and moves **down** only on evidence plus approval. The cache sits in front of every rung. This brief adds:
- **Rung 4, semantic cache (optional per task):** a near-identical question (embedding similarity from Hermes' local embedding model, no paid call, threshold ≥ 0.97, same tenant scope rules) is answered from the cache. It is proven by the same shadow loop before it is switched on for a task.
- **Rung 3 promotion** (sections 1–3 below), and the search in 1b covers rungs 1 and 3 together. Rung 2 joins the search when T-7 adds owned models.

## 1. Candidates can be code
- `tank.policy.candidate_model` may also hold `skill:<id>@<version>`, e.g. `skill:base.extract@2.0.0`. A code candidate must be an **approved** skill with no `task_type`, so it can never call a model.
- On a shadowed call, Tank runs the code skill on the same input, in the background, after the primary has answered. The client only ever receives the primary's answer while shadowing.

## 1b. Search every available model for the cheapest one that does the job
Tank does not wait for a person to pick a candidate. For each task type it **searches the whole roster** (`litellm/config.yaml`, every model with funds, plus approved code skills) for the cheapest option whose results match the serving route:
- **Screen offline first (cheap):** run the task's eval cases and a sample of its stored real inputs (learning corpus) against every roster model that is cheaper than the serving one, through providers' batch APIs where available. Drop any model below the bar. Code skills are screened the same way at zero cost.
- **Then shadow the survivors live**, cheapest first, one at a time, on a share of real calls, until each has `min_shadow_samples` pairs.
- **Result per task:** a ranked list (cheapest first) with agreement, per-field floors, cost per call and projected monthly saving. The cheapest candidate that clears every bar is **proposed**. The founder promotes it, or sets that task to auto-promote.
- **Re-search automatically** when a new model is added to the roster, when a price changes, or monthly, so the task always sits on the cheapest option that does not hurt the work.
- **Shadow spend has a daily budget per task** (default $1/day, an env setting) so testing never runs away. Code candidates cost nothing and are always tested.

## 2. Agreement without a model where possible
- Structured outputs (JSON) are compared **field by field** in code: exact match for ids, numbers within a tolerance, sets by overlap (Jaccard). The result is a 0–1 agreement and a per-field breakdown stored in `tank.shadow` (`method = 'fields'`).
- The model judge is used only for free text.

## 3. Promotion is evidence plus approval
- A code candidate is **proven** when it has at least `min_shadow_samples` shadow pairs and agreement at or above `eval_threshold`, with no field below its own floor, and client rejects at or under `max_reject_rate`.
- Promotion follows the task's **approval policy** (C14): `ask` (an admin promotes), or `auto` (Tank promotes by itself when the evidence clears a **stricter auto bar**: at least 2× `min_shadow_samples`, agreement at least 0.02 above the threshold, every field above its floor). An auto-promoted task is watched: if client rejects or live agreement drop below the bar in the next 7 days, Tank **rolls back by itself** and notifies the admins. Manual promotion stays available (`POST /v1/graduation/{task_type}/promote`). After promotion the task's policy points to the skill, and **no model is called** for that task. `rollback` restores the model in one call. Both are logged in `policy_log`.
- The founder console shows each task's ladder: paid model → cheaper model → code, with samples, agreement, cost per call before and after, and the projected monthly saving.

## 4. Paid tools, same loop
- The same shadow-and-prove loop works for a paid tool against our own skill (e.g. Brave results vs SearXNG + `base.find_site`): the paid route runs only where the ladder allows it, and the comparison is stored the same way. This is how Tervory learns from a paid tool and then stops paying for it.

## Done when
CI green; a test runs the search over a mocked roster of four priced models and proposes the cheapest one that clears the bar (and not a cheaper one that fails it); a test shadows `base.extract@1.0.0` (model, mocked) against a code candidate on fixtures and reports field-level agreement; promotion does not happen below the bar and happens by itself above it; a quality drop rolls it back by itself; after promotion, a call makes zero model calls (tested); the console shows the ladder for that task.
