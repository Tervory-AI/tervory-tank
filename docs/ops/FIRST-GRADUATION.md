# First recorded fixture graduation

On **2026-10-26 at 15:10:53 UTC**, Tank's existing automatic graduation loop promoted **`base.normalize`** from the fixture's `haiku` model route to **`skill:base.normalize@1.0.0`**, then served requests from both fixture tenants at rung 3.

This is an executable local fixture record for the patent file. It is **not a production deployment, a live-provider quality study, or measured customer savings**. No paid provider was called. The existing skill was marked approved in the disposable test database; the skill's source and Skala's approval lifecycle were unchanged.

| Recorded fact | Result |
| --- | --- |
| Task | `base.normalize` |
| Skill | `base.normalize@1.0.0` |
| Primary | `haiku`, supplied by an independent fixture provider stub |
| Traffic | 30 distinct synthetic business records, alternated across two generated tenant IDs |
| Minimum shadow samples | 30 |
| Required agreement | 0.97 |
| Observed agreement | 1.0000 across all 30 samples |
| Promotion | `tank.policy_log.action='promote'`, `by_user='tank'`, `detail.automatic=true` |
| Cost before | $0.001 per call reported by the fixture provider; $0.030 fixture total |
| Cost after | $0.000000 per call at rung 3, with a ledger row and transcript |
| Actual external spend in this experiment | $0 |
| After promotion | Both tenants received code answers; no provider call |

The fixture provider supplies complete expected normalized fields and match keys independently of the code candidate. Each primary request runs through `run_route`; the real `_shadow`, `_run_code_candidate`, `_move_task`, SQL evidence aggregation and policy update execute against isolated PostgreSQL. The test waits for each shadow to finish and never invokes the promotion endpoint or sets the promoted policy itself. After sample 30 it reads the promotion record, then makes two further foreground requests through the promoted policy.

Reproduce from the repository root with Python 3.12 and an isolated PostgreSQL instance:

```sh
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55432/pooltest \
PYTHONPATH=tank python -m pytest -q -s \
  tests/test_tank_ladder.py::test_first_fixture_graduation_promotes_itself_and_serves_two_tenants
```

The test creates and drops its own database. Its `FIRST_GRADUATION` output includes the run time, task, skill, sample count, agreement, before/after fixture cost, and the explicit zero-external-spend qualification. Later runs reproduce the transition with new tenant IDs and timestamps; the dated record above identifies the first successful run in this branch.
