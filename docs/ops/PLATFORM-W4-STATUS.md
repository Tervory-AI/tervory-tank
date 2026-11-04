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
