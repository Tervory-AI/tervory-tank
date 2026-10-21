# MOA-1: Mixture of Agents inside Tank, with Skala proving every seat

> Written 21 Oct 2026. Founder's design (with the Gemini infrastructure plan): for complex work, Tank fans the prompt out to several diverse "proposer" models in parallel, then an aggregator combines them. **Tank and Skala optimise each seat independently**: shadow tests prove when a cheaper model can hold a seat, the aggregator steps down when proposers agree, and plain code bypasses the whole thing. Perplexity sits in the research seat.
>
> **Research to respect** (so the engine measures rather than assumes):
> - "Rethinking Mixture-of-Agents" (TMLR 2026) found that mixing different models often scored *below* Self-MoA, where one strong model is sampled several times: 6.6% lower on AlpacaEval 2.0. Weaker proposers drag the average down.
> - "When Agents Disagree: The Selection Bottleneck" (2026) found that *selecting* the best answer with a judge beat *synthesising* all answers (0.810 vs 0.179 win rate), and that diversity only helps when the selector is strong.
>
> So every MoA shape is a policy Tank tests per task, and the founder promotes the shape that wins on cost and quality.

**Files you may change:**
- new `tank/moa.py` (orchestration);
- `tank/main.py` (route registration only);
- `tank/schema.sql` (additive);
- `tank/graduate.py` and `tank/bench.py` (MoA shapes in the bench);
- `workspace/app/tank/` (seat view);
- `requirements` for LangGraph;
- tests.

1. **When MoA runs.** Tank decides per request:
   - plain code if a code skill answers (no fan-out at all);
   - otherwise a single model;
   - MoA only where the task's policy has `moa_enabled` and the request is classed complex.
   - Never for something a user is waiting on in under a few seconds, unless the founder sets it.
2. **Seats.**
   - Each MoA task has named seats in policy, for example `logic`, `context`, `research` (Perplexity Sonar, web-grounded with citations), `data` (DeepSeek or GPT), `speed` (open-weights or a cheap model).
   - Each seat has a current model and a candidate.
   - Diversity is the default, but the bench also tests **Self-MoA**: the best single model sampled N times.
3. **Skala on seats.**
   - On a share of runs, each seat's candidate runs in shadow and is scored against the seat's current answer and against the final result.
   - When a cheaper candidate matches over at least 100 runs (the threshold is set per task), Tank proposes the swap. **The founder promotes.**
4. **The aggregator.**
   - Tank measures agreement between the proposers before calling it.
   - Low variance: a cheap model **selects** the best answer or lightly merges.
   - High variance: a frontier model resolves the conflict.
   - Two aggregation modes, `select` (a judge picks the best) and `synthesize` (one merged answer), are both benched per task; the winner is promoted.
5. **Failure handling**, with LangGraph per-node policies:
   - a hard timeout per seat (default 15s);
   - jittered retries on 429s and transient errors;
   - a circuit breaker that marks a seat `FAILED`;
   - **partial aggregation**: the aggregator receives the answers that arrived, plus a note naming the missing seat, and says when critical data may be missing;
   - never a hang or a blank screen;
   - failures are recorded per seat, so a flaky provider loses its seat on evidence.
6. **Legal stays checked.** For Zenas, the aggregated answer still passes `zenas.cite_check` and the made-up-case gate. Agreement between models never replaces finding the case in the library.
7. **Receipts and proof.**
   - Every MoA run shows each seat's model, tokens and cost, the aggregator's, and the total.
   - Two baselines: **all-frontier MoA** and **the single top model**, with the saving against both.
   - The CORE-1 proof page gets a per-task chart of quality against cost for single model, Self-MoA, diverse MoA and optimised MoA, from the bench.

## Done when
CI green. Tests:
- a code-answerable request never fans out;
- 4 seats run in parallel, so total time is roughly the slowest seat;
- a timed-out seat gives partial aggregation with the note;
- low variance routes to the cheap aggregator and high variance to the frontier one;
- a seat swap is only proposed after the threshold and never applied without the founder;
- Zenas output still fails cite_check on an invented case;
- the receipt shows both baselines.
