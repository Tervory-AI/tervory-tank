# Rig prices from Tiger — blocked on the product watch control

Branch: `codex/rig-tiger-prices`.
Base: freshly fetched `origin/main`, `bde4578cfbfbdcdd2ba5fa76cd91d4bc54669df5`.
Rules: `docs/build/MILESTONES-28OCT-1NOV.md`, “The rules block”, rules 1–11.
Claude opens any PR. No GitHub API, merge, main push or deployment.

## Status and exact missing item

Implementation stopped at the required user-control boundary. Missing: an
approved Figma frame and exact wording for the store founder/admin to enable
Tiger updates for a specific Rig product/SKU that has a page address and no
supplier feed. No supplied export specifies that control or its states.

The task explicitly says: **“if a control needs wording, stop and report.”**
Rule 2 also says: **“Do not add text, buttons, empty states or error wording.
If you need one, stop and report it.”** Rule 9 says not to guess or work around
a missing requirement. Accordingly, this branch only records the blocker;
there are no application, schema, UI or setting changes.

The existing Tiger button is for watching a URL and configuring alerts. Making
it implicitly enable Rig catalogue updates or infer a SKU would introduce an
unspecified product-selection/publishing behaviour. No such behaviour was added.

## Evidence on main

| Existing file:line | Observed behaviour |
| --- | --- |
| `workspace/app/rig/admin/products.tsx:25,35` | Product controls are `Delete selected` and `Delete`; there is no watch control. |
| `workspace/app/rig/admin/types.ts:6,13` | Product rows contain SKU/name/price/currency; the admin operation union has no watch operation. |
| `workspace/app/tiger/view.tsx:397,413,418,423,436` | Existing Add a product form accepts a URL, interval and price/stock alert preferences, then `Start watching`. It has no Rig product/SKU or catalogue-update choice. |
| `workspace/app/tiger/actions.ts:26,38` | The form creates a generic tenant watch with URL/label/interval/alert preferences; no Rig SKU is passed. |
| `workspace/app/access/view.tsx:56` | `Match a watched page` asks for a **Distributor item number** for an official feed. It is not an existing no-feed Rig publishing control. |
| `tank/access.py:978` | The Tiger receiver already exists at `/v1/access/rig/tiger` (the router supplies `/v1/access`). It authenticates using the existing setting name `TANK_KEY_TIGER`, then forwards the tenant and SKU to Rig. No setting values were accessed. |
| `agents/tiger/app.py:123,154` | Existing check and dispatch functions use Tiger's watch/schedule machinery. The requested Rig delivery is not implemented by this branch. |
| `docs/figma/README.md:23` | Export inventory contains the client dashboard and founder control panel. No Rig product-watch frame is supplied. Tool discovery also found no available Figma connector. |

## Commands and results

From the existing repository:

```bash
git status --short
git fetch origin main
git worktree add -b codex/rig-tiger-prices /workspace/rig-tiger-prices origin/main
git -C /workspace/rig-tiger-prices rev-parse HEAD
```

The original worktree was clean and was preserved. Fetch advanced main from
`a99f3cb` to `bde4578`. A separate worktree was created on the requested task
branch from that main revision; all commands exited 0.

The focused inspection recorded in [evidence/inspection.txt](evidence/inspection.txt)
uses these exact commands from the new worktree:

```bash
git rev-parse HEAD
nl -ba workspace/app/rig/admin/products.tsx | sed -n '18,39p'
nl -ba workspace/app/rig/admin/types.ts | sed -n '3,13p'
nl -ba workspace/app/tiger/view.tsx | sed -n '397,438p'
nl -ba workspace/app/tiger/actions.ts | sed -n '26,42p'
nl -ba docs/figma/README.md | sed -n '21,30p'
```

Each command exited 0. Trailing whitespace on numbered blank lines was removed
from the saved output after `git diff --cached --check` flagged it; source text
and line numbers are unchanged. This is source inspection, not a functional test.
The four requested integration scenarios have **not** been implemented or run.
No founder-browser screenshot or live result is available, and the one-cycle
live-price acceptance condition is **not met**.

## Files changed

- `tests/rig_tiger_prices/PR.md:1`: this blocker and handoff record.
- `tests/rig_tiger_prices/evidence/inspection.txt:1`: exact source inspection
  output from the main baseline.

Only these documentation/proof files are committed. No new control, wording,
automatic watch, model call, key or live-data change was introduced.
