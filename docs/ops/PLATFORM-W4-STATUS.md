# Platform wave 4 completion

Baseline: `15432cb522a7922359ad9174aed3784480b34b50`, after #682 merged.
No live settings, data, approvals or deployments are changed by this branch.

## Gate 1

- B4 — already on main: `tank/skala_probation.py:10` calculates 30 clean days
  after approval, failed evaluation or rollback; pending revalidations block
  retirement. `tank/skala.py:667` retires state only and retains the package;
  `tank/skala.py:654` permits explicit rollback to a previously approved version.
- A22 — already on main: `litellm/config.yaml:830` and
  `litellm/config.za.yaml:864` select LiteLLM cost-based routing. Multiple
  deployments share their model group; `tank/routing_data.py:16` retains all
  group members. Existing host/privacy restrictions can pin the permitted
  deployment; load balancing must never bypass those restrictions.
- A8 — added deadline-aware scheduling to the existing off-peak queue.
  `RouteRequest.deadline` is an optional timezone-aware timestamp. The selected
  model's published off-peak windows and existing provider batch discount are
  compared with its current price. The cheapest feasible option wins; equal
  prices prefer earlier completion. Foreground work reserves 120 seconds and
  provider batches require their existing 24-hour completion window. No new
  provider, model, paid route or rate is introduced. Requests without a deadline
  retain the existing explicit off-peak behavior. Polls recheck current prices,
  policy and the deadline; an expired job fails without dispatch. Waiting and
  foreground execution are bounded, but provider completion is not guaranteed.
  Receipts preserve actual measured costs; predicted discounts are not savings.
  The protected `run_route` snapshot changes only its authorized dispatch-window
  predicate; cache and task execution snapshots remain intact.

## Gate 2

- C1/N1 — added `tank/tenant_regions.py` and `tank.tenants`. The founder assigns
  a new tenant's `us-east` or `za` home through
  `PUT /api/tenants/<tenant UUID>/home`. The US Tank is the directory. Assignment
  is idempotent; a changed home requires a separate migration. An assignment to
  ZA refuses existing US tenant data, including conversations and product tables.
  Workspace's tenant-aware clients resolve the record before transporting
  content; Zenas uses the same directory. Missing legacy records retain the
  existing box contract. Invalid/unavailable metadata fails before content is
  sent. Other-region content requires its full content key; homes/feeds keys
  retain their existing scope. Direct route/task/skill and command authorization
  checks reject a different recorded home.
- C3/C6 — `tank/workspace_board.py` exposes tenant-owned tasks and results.
  Delivery comes from the ledger; a legacy `done` without delivery proof is
  Unverified. Queued tasks retain their receipt and finish through the existing
  queue. Results contain recorded content, measured cost or an explicit unknown,
  and no fixture download URLs. Useful, Not useful and Wrong feedback keep the
  originating task/ledger identity and an optional 1,000-character note. The
  existing feedback writer still produces the learning evidence.
- B3/A31 — already on main: `tank/schema.sql:2194` queues policy-model changes;
  `tank/skala_revalidation.py:170` drains durable evals, and
  `tank/routes_registry.py:57` installs it. Added live membership observation,
  including current tenant overrides and held proposals. Price/key rotations and
  generated deployment IDs do not fabricate a membership change. Private cases
  use their owner's model permissions. First observation records the baseline.
  Later changes run every approved package's evals and append the fingerprint to
  `models_validated`. Routine writes/promotions wait for roster work; a held
  proposal is rechecked before release. Completed paid evals are not replayed.
  The existing target-model gate and explicit rollback path remain in use.
- D6 — `tank/morning_report.py` builds a regional midnight–07:00 Pacific digest
  from ledger activity, canonical comparable savings, failed jobs, deployment
  observations and candidate comparisons. Deferred work uses its dispatch night;
  evaluation failures count once across their receipts. The scheduled email uses
  existing SMTP setting names and a durable daily claim. Uncertain SMTP delivery
  is not retried. Optional GitHub deployment history is marked incomplete when
  unavailable/truncated; it is not an application-health attestation. No model,
  promotion, deployment or production-data operation builds this report.
- Setting names and conditional regional connections are documented in
  `docs/ops/FOUNDER-SETTINGS.md`; runtime configuration is unchanged.
- The frozen registry extension preserves every tool, adapter, visibility set,
  dispatch branch and existing route order. It adds six routes, the report task
  and SQL inside the existing platform block; the freeze origin is unchanged.

Missing frames: C6 Feedback (desktop/mobile and empty/loading/error states) and
founder Paid steps settings (per-step Ask/Auto plus global pause/resume). These
are listed as uncreated in `docs/figma/workspace/REGISTER.md`. The backend is
available through authenticated APIs while those frames are pending.
