# Cursor task queue

Each file here is one self-contained task for a Cursor background agent. Each has a matching GitHub issue labelled `cursor`.
Start one by opening the issue and commenting `@cursor` (or paste the brief into a Cursor background agent). One task = one branch = one PR.

| ID | Task | Lane (files) | Depends on |
| --- | --- | --- | --- |
| C1 | tervory.com marketing site from the approved Figma | `site/` (new) | Founder approves the Figma page |
| C2 | Brand the Workspace (logo, colours, type) | `workspace/app/layout.tsx`, `workspace/app/globals.css`, `workspace/app/icon.png` | — |
| C3 | Data page: filters, search, record drawer | `workspace/app/data/*`, `workspace/app/api/base/route.ts`, `workspace/lib/tank.ts`, `base_records` in `tank/main.py` | — |
| C4 | Tests + CI on every PR | `tests/`, `.github/workflows/`, `tank/requirements-dev.txt` | — |
| C5 | Ledger: daily spend by rung, by task type | `workspace/app/ledger/*`, `workspace/lib/tank.ts`, a new read-only endpoint in `tank/main.py` | — |
| C6 | Agent chassis: own box, files, schedule, identity per Squad member | `agents/`, compose, `tank/schema.sql`, `require_key` + `run_one_skill` only | — |
| C7 | Hermes: per-agent, per-client memory (Qdrant + local embeddings) | `hermes/`, compose, `agents/_chassis/` | C6 |
| C8 | Tiger box: isolated browser sessions, price mining, watchlists, alerts | `tiger/`, `agents/tiger/`, `tank/skills/tiger.*`, compose | C6 (C7) |
| C9 | Market Lab box: series feeds, surge detection, research, prediction ledger | `agents/market_lab/`, `tank/skills/market.*`, compose | C6 (C7) |
| C10 | Boxes for Radix, Tisan, Zenas (isolated, memory, no skills yet) | `agents/radix|tisan|zenas/`, compose | C6, C7 |
| C11 | Founder console: independence %, booked revenue, margin, graduations on the graph (founder-only) | `tank/admin.py`, `tank/schema.sql`, `workspace/app/admin/*`, `workspace/lib/admin.ts` | — |
| Z1–Z6 | Zenas, the legal agent (US + SA, no criminal law): see `Z-zenas-plan.md` | `agents/zenas/`, `tank/skills/zenas.*`, Workspace Matters/Review pages | C6, C7, C10 |

Claude keeps: Tank routing, the cache, shadow/graduation, the queue worker, `base.*`/`ffl.*` skills content, Coolify/infra, the FFL data run, and moving Base out of Tank into its own box (after C6). Claude reviews every PR before merge; nothing merges to `main` without that review.
