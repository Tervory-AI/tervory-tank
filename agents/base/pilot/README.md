# Base sandbox pilot receipt

Recorded in the managed cloud on 2026-10-21T17:02:53.082578+00:00. **Passed.**
This is the owner's replacement for the pre-merge live ATF run. No real model,
production key or production endpoint was used.

- [Recording](recording.json): authenticated HTTP events, model exchanges, ledger,
  transcripts, approved export, loaded files, containers and isolation results.
- [Task receipt](receipt.json): complete brain receipt.
- [Fallback proof](fallback.json): real default pipeline with the brain unavailable.
- [Input](atf-fixture.json): two synthetic Delaware ATF-format rows.
- [Reproduction harness](../../../tests/test_agent1_pilot.py).
- [Claude's live-pilot handoff](../BRAIN.md#how-claude-runs-the-live-pilot).

| Proof | Recorded result |
| --- | --- |
| Task | `f724c84c-bdfd-4a16-b647-5bf24e2cf28b` — done |
| Tenant | `2237aeb0-cef2-4521-b0f1-878cb48ba38e` |
| Tank route | 4 POSTs to `/v1/agents/base/chat/completions`, authenticated with the generated Base room key, all 200 |
| Accounting | 4 persisted ledger rows, 4 joined transcripts and 4 receipts for the same tenant/task |
| Spend | Synthetic cost $0.000560; synthetic baseline $0.001120; actual provider spend $0 |
| Memory | Recall first, one own-tenant memory despite a second-tenant decoy; remember last |
| Skills | 11 approved versions exported by Skala match installed files; existing versions unchanged |
| Pipeline | Both fixture rows processed; zero ready, zero failed; absent sites remain unknown |
| Browser | Own Chromium container and cookie/history volume; inline fixture rendered; metadata URL refused with HTTP 403 |
| Sandbox | Unprivileged sibling exec API, read-only root, no added capabilities or shared volumes; WASI scratch has no sockets or provider credentials |
| Fallback | Task `53ceffdd-2863-45b9-b84e-8582bbcc1422` processed 2 rows with the brain down and 0 additional model calls |

The expected browser refusal is a failed step followed by successful scratch work
and pipeline continuation. It is not a public-page fetch. Optional Hermes
capability-discovery GETs return 404; all four thinking POSTs succeed. Site results,
LiteLLM answers/prices and the memory store/embeddings are fixture substitutions.
Tank, its database/accounting, the Base pipeline, pinned Hermes, memory HTTP API,
Chromium and CPython/WASI execution are real. The scratch tool supports Python's
standard library only; it cannot run native shell commands or install packages.

Source implementation: `4b01093fbefe795160ae7e6b20ea980ad9825b97`. Integrated pilot: **1 passed in
34.03s**. Separate cloud checks: **78 passed, 1 skipped**; real Hermes runtime
**1 passed**; unprivileged sandbox/browser container checks **2 passed**; real
Postgres schema/billing/submission checks **8 passed**. The browser checks also
exercise JavaScript, age confirmation, cookies, private redirects and proxy
interface binding. All pilot containers, volumes, networks and its throwaway
database were removed.

**live ATF run: done by Claude on Boston after merge**

Evidence SHA-256:

- `recording.json`: `647a1dfe1e9710f12e859d77476c9d2944f1c9518284e11ba93a48b8dec87034`
- `receipt.json`: `3e9806151925254daedefd9c439e7eead3343dc93b27f3c235c6d85d5e7a4ec8`
- `fallback.json`: `ecfb63e7dbe806de3284d33d972081f4a28127035528b8c24e055b29ff585451`
