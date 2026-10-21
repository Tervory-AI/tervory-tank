# Base sandbox pilot receipt

Recorded in the managed cloud on 2026-10-21T13:54:57.108825+00:00. **Passed.**
This is the owner's replacement for the pre-merge live ATF run. No real model
was called and no production key or endpoint was used.

- [Recording](recording.json): actual HTTP events, model exchanges, database rows,
  approved export, loaded files, containers and isolation results.
- [Task receipt](receipt.json): complete brain receipt.
- [Input](atf-fixture.json): two synthetic Delaware ATF-format rows.
- [Reproduction harness](../../../tests/test_agent1_pilot.py).
- [Claude's live-pilot handoff](../BRAIN.md#how-claude-runs-the-live-pilot).

| Proof | Recorded result |
| --- | --- |
| Task | `1b549a69-e9dc-49e1-92aa-fbeef1c248e5` — done |
| Tenant | `9a933348-605f-481c-891d-f414327b57a6` |
| Tank route | 4 POSTs to `/v1/agents/base/chat/completions`; all validated Base's generated room key and returned 200 |
| Ledger | 4 persisted rows and 4 matching receipts, scoped to the same tenant and task |
| Accounting | Synthetic cost $0.000560; synthetic baseline $0.001120; actual provider spend $0 |
| Memory | Recall first, exactly one own-tenant memory despite a second-tenant decoy; remember last |
| Skills | 11 approved Base versions exported by Skala, matching the installed skill files; existing registry versions unchanged |
| Pipeline | Both fixture records processed; zero ready, zero failed; absent sites remain unknown |
| Browser | Private Base Chromium container and volume; inline fixture rendered; disallowed URL refused with HTTP 403 |
| Sandbox | Actual Hermes Docker tool; network `none`; disallowed `1.1.1.1:443` connection refused; credentials absent; wrote only its work file |

The browser tool's expected refusal is a failed step in the receipt, followed by
successful sandbox work and pipeline continuation. It is not a public-page fetch.
Optional Hermes capability-discovery GETs return 404; all four thinking POSTs
succeed. Site results, LiteLLM answers/prices and the memory store/embeddings are
explicit fixture substitutions. Tank, the Base pipeline, the memory HTTP API,
the pinned Hermes agent, Chromium and Docker execution are real.

Source implementation: `8a689fc670fe02c158e16efc0989c1bcac45006a`. This recording was generated with
the accompanying test harness before its evidence commit. Tests: integrated
pilot **1 passed in 31.04s** after DASH integration; combined adapter/dashboard/schema
checks **48 passed**; real Postgres schema, billing and submission checks **6 passed**.
The thinking route also passes refusal tests for the founder paid pause and an
unavailable control state.
All pilot containers, volumes, networks and its throwaway database were removed.

Evidence SHA-256:

- `recording.json`: `7cdd13f6325461136e8d7f50e26fa48baf3724e6e1ccf58e9969bcc5b8b02dab`
- `receipt.json`: `44b3a3f08a188ddd2b75fce9507423f3958680d73b8168034bc26cb01426a70c`
