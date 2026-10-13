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

Claude keeps: Tank routing, the cache, shadow/graduation, the queue worker, skills content, Coolify/infra, the FFL data run.
