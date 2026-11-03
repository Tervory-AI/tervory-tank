# Rung-1 cost report: repeats and the cheapest passing model (2026-10-31)

Scope: which rung-1 (paid model) call patterns should graduate to a Skala skill
(rung 3) or the semantic cache (rung 4), and the cheapest model that passes for
rung 2 and routing. Written from `main` at `d8277de` with LLM credit at zero.

**Short answer: there is not enough data in the repo to rank by measured spend
or to name a cheapest passing model for any task.** What is missing is listed
in section 3, and this PR adds `tank/cost_evidence.py` to produce it. The
ranking below is structural: it comes from the seeded policies, the roster
prices, and how the agents call Tank. It is not based on ledger counts.

## 1. Where rung-1 money goes (structural)

These are the effective platform policies after `tank/schema.sql` is applied
to an empty database. Prices are from `litellm/config.za.yaml`, in dollars per
million tokens (input/output).

| Seat | Price in/out | Rung-1 tasks on it |
|---|---|---|
| astra | 10 / 50 | zenas.apply, scope, case_facts, rule_card, draft, review, compose, plain_language, selftest |
| grok-top | 2 / 6 | market.research, reason.brief (candidate flash-lite already set) |
| flash | 0.75 / 3.75 | tank.judge |
| luna | 0.10 / 0.50 | command.turn, route.request, tier0.*, rig.*, moot.*, trigger.write, agent.rig.think |

All nine Zenas tasks sit on the most expensive seat, which costs 100x luna and
haiku. A single astra call can cost up to this much in output alone (max
output tokens × $50/M):

* rule_card: $0.06
* case_facts: $0.04
* draft/compose/plain_language: $0.04 each
* apply/scope/review/selftest: $0.02 each

## 2. Top repeat patterns, ranked as graduation candidates

The ranking key is likely spend that a repeat would move off rung 1: volume ×
seat price × how repetitive the input is. Use `cost_evidence repeats` (below)
to replace this ranking with measured numbers.

| # | Pattern | Why it repeats | Candidate | Notes |
|---|---|---|---|---|
| 1 | **zenas.apply** (astra, urgent): one call per rule element per case | The same rule-card elements are tested against similar fact patterns, and the answer is a short structured verdict | **Skala code skill** for deterministic elements, **semantic cache** (matter-matched) for the rest | Highest volume × astra price. The semantic cache is already on, so measure its hit rate first. |
| 2 | **zenas.rule_card** (astra, max 1200 out) | The same rule or statute gets carded again across cases and tenants | **Semantic cache** (already on with matter matching, batch_eligible) | The most expensive single call. Its hit rate decides whether anything else is needed. |
| 3 | **zenas.case_facts** (astra, nightly, up to `ZENAS_CONVERT_MAX`=200/night) | The same extraction instruction and policy prompt runs over many documents | **Prompt caching** (PR #468) plus **batch** (PR #472 path); later, a Skala extractor for fixed fields | Background work, so it should never pay the full live price. |
| 4 | **zenas.selftest** (astra, 50 questions nightly) | The same question set every night, against slowly changing matter data | **Semantic cache** keyed on question and matter version | Note: answers must change when the matter changes. Only cache them with matter matching. |
| 5 | **command.turn** (luna, urgent) | The planning prefix (system prompt and tool schemas) is identical on every turn | **Prompt caching only** | Cheap seat. Not a skill or cache candidate, because every turn is different. |
| 6 | **base.extract / base.business_data** (luna fallback for skill rung 3) | Runs when the code skill declines | **Skala**: widen the skill's coverage from the declined inputs | Cheap seat; the ladder already exists. |
| 7 | **tank.judge** (flash, batch) | Comparison prompts with a fixed rubric prefix | Prompt caching; keep it on batch | Small max output (64). |

## 3. Cheapest passing model for rung 2 and routing: no evidence

The selection rule already exists in `tank/bench.py` (`choose_candidate`): the
cheapest model whose bench score is at least the serving model's score. It
writes `policy.candidate_model`, and promotion still waits for the founder.
Nothing in the repo records the result of running it.

* `tank.bench_runs`, `tank.route_evidence` and `tank.shadows` are production
  tables. The repo contains no export or snapshot of them, and
  `docs/ops/FIRST-GRADUATION.md` is a fixture-only record ($0).
* **No platform evals are seeded.** `tank.evals` is empty after the schema is
  applied, and the bench's other sources are approved Skala package cases and
  checked held-out gold. `docs/research/AGENT-TESTS.md` reports tiny sets:
  1–5 examples for most skills, Zenas 38 for scope and 15 for ID protection,
  Tiger 10. None of these is a Tank eval for the astra tasks above.
* Graduation needs ≥30 shadow runs at ≥97% agreement. No shadow data is in
  the repo.

So for every rung 1/2 task, the honest answer is "unknown". To name a model,
each task needs these four things:

1. **≥30 accepted platform eval cases** in `tank.evals` (tenant_id NULL or the
   platform tenant), or held-out gold.
   * Zenas: the 38 scope and 15 ID-protection examples are the obvious start.
     Load them as `tank.evals` rows for `zenas.scope`.
   * apply, rule_card and case_facts have no cases at all.
2. **A complete bench run on the serving model** (astra for Zenas), so that a
   candidate has a score to beat.
3. **A complete bench run on each cheaper candidate.** The obvious
   batch-capable candidates are luna, haiku, sol, sonnet, flash-lite,
   flash-lite-31 and flash. For non-batch seats (deepseek-flash, gpt-oss,
   llama-small, open weights), use the nightly bench.
4. **Shadow agreement** on live traffic for the proposed candidate before any
   founder switch. The existing shadow path does this; it is not a cost-tool
   job.

## 4. Tooling added: `tank/cost_evidence.py`

These are operator CLIs. None of them runs on a request path.

* `PYTHONPATH=tank python -m cost_evidence repeats --days 30`
  * Ranks real rung-1 traffic by task type:
    * calls, cost and average input tokens;
    * exact-repeat share (identical message lists, which is the semantic cache's ceiling);
    * shared-prefix share (everything except the final user turn, which is what prompt caching reuses);
    * JSON share and stable-shape share (structured answers a Skala code skill can replace).
  * Gives a verdict and the movable dollars.
  * Reads all tenants, so it needs `TANK_ADMIN_DATABASE_URL` (BYPASSRLS). It prints aggregates and hashes only, never prompt or answer text.
* `... cost_evidence cheapest`
  * For each rung 1/2 platform policy, prints the cheapest model whose latest complete bench run scores at least the serving model's.
  * Otherwise it says exactly what is missing ("no complete bench run for this task", or "... for the serving model astra").
* `... cost_evidence replay --task T --model M` then `score --task T --model M --batch ID`
  * Evidence through the **batch path**: replays the task's platform eval suite on model M as one provider batch through Tank's existing batch worker. That is half price on OpenAI, Anthropic and Vertex Gemini seats.
  * Records a `tank.bench_runs` row and `tank.route_evidence`, so `cheapest` and the bench dashboards see it.
  * Safety:
    * Candidate answers never reach the semantic cache, shadows, RouteLLM samples or MoA, and the serving policy is not changed.
    * Ledger rows are `agent='bench'` on the platform tenant.
    * The batch id is deterministic per region, task, model, suite and day, so a rerun the same day is idempotent.
    * It refuses when the reservation is over `TANK_BENCH_MAX_USD` (default $5) or the seat has no provider batch.
    * Paid pause applies at submission, as for any batch.
  * `cost_per_call` is stored at the live (undiscounted) price, so it compares directly with synchronous bench runs. The batch cost is reported next to it.

### Live run plan, once credit is on (about $1–3 total)

1. Load the Zenas scope and ID-protection examples as `tank.evals` for `zenas.scope`, and write ≥30 cases each for `zenas.apply` and `zenas.rule_card`.
2. For each of those tasks, run `replay` on `astra` (the baseline), then on `sol`, `luna`, `haiku`, `flash-lite-31` and `flash`. Run `score` after the batches finish (≤24h).
3. `cheapest` then names the model. The nightly bench covers the non-batch seats.
4. Run `repeats --days 30` on each region box (us-east, za) to replace section 2 with measured numbers.
5. Bring the founder a switch only with shadow agreement ≥97% over ≥30 runs.
