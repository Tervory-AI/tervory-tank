# T-6 — Tank: graduate a task from a paid model to plain code

**Why this matters:** this is the core of Tank. Today a task can graduate from an expensive model to a cheaper model (shadow runs, a judge scores agreement, the founder promotes). The founder's goal is the last rung: **no model at all**. Tank must prove, with evidence from live traffic, when a code skill can replace a model (or a paid tool) for a task, and only then switch it over, with approval.

**Lane:** this brief allows changes to the shadow/graduation code in `tank/main.py` (`_shadow`, `/v1/graduation/*`), `tank/schema.sql` (additive), `workspace/app/admin/*` (founder console graduation view), `workspace/lib/admin.ts`, and new tests. Not the router's model call, not the queue worker.

## 1. Candidates can be code
- `tank.policy.candidate_model` may also hold `skill:<id>@<version>`, e.g. `skill:base.extract@2.0.0`. A code candidate must be an **approved** skill with no `task_type`, so it can never call a model.
- On a shadowed call, Tank runs the code skill on the same input, in the background, after the primary has answered. The client only ever receives the primary's answer while shadowing.

## 2. Agreement without a model where possible
- Structured outputs (JSON) are compared **field by field** in code: exact match for ids, numbers within a tolerance, sets by overlap (Jaccard). The result is a 0–1 agreement and a per-field breakdown stored in `tank.shadow` (`method = 'fields'`).
- The model judge is used only for free text, and only when the judge rung is allowed (C14 ladder).

## 3. Promotion is evidence plus approval
- A code candidate is **proven** when it has at least `min_shadow_samples` shadow pairs and agreement at or above `eval_threshold`, with no field below its own floor, and client rejects at or under `max_reject_rate`.
- Promotion stays a founder action (`POST /v1/graduation/{task_type}/promote`). After promotion the task's policy points to the skill, and **no model is called** for that task. `rollback` restores the model in one call. Both are logged in `policy_log`.
- The founder console shows each task's ladder: paid model → cheaper model → code, with samples, agreement, cost per call before and after, and the projected monthly saving.

## 4. Paid tools, same loop
- The same shadow-and-prove loop works for a paid tool against our own skill (e.g. Brave results vs SearXNG + `base.find_site`): the paid route runs only where the ladder allows it, and the comparison is stored the same way. This is how Tervory learns from a paid tool and then stops paying for it.

## Done when
CI green; a test shadows `base.extract@1.0.0` (model, mocked) against a code candidate on fixtures and reports field-level agreement; promotion is refused below the bar and accepted above it; after promotion, a call makes zero model calls (tested); the console shows the ladder for that task.
