# F06 dashboard evidence

Offline fixtures only. These checks do not sign in, call a model, write to a production database, or prove a deployed journey.

Authority: `docs/figma/client-dashboard-12-2/SPEC.md`, `reference.tsx`, and `states.tsx`. The checked-in `frame.png` still contains the removed “Waiting on you” status; the later explicit removal in SPEC and states controls. Shared menu structure remains unchanged pending the conflicting later merged-menu design; lane 2 owns routing and keyboard behavior. There is no separate approved 375px client-dashboard export in this folder. The 375px capture checks the existing responsive implementation with the approved content, not pixel identity to an unrelated Overview mobile design.

Run from repository root:

```sh
node tests/client-dashboard-f06.cjs
PYTHONPATH=tank python -m pytest tests/test_client_dashboard_f06.py -q
F06_ESBUILD_PATH=/path/to/esbuild F06_PLAYWRIGHT_PATH=/path/to/playwright F06_CHROMIUM=/path/to/chrome node tests/client-dashboard-browser.mjs
node tests/dashboards-ui.cjs
cd workspace && ./node_modules/.bin/tsc --noEmit
```

Set TMPDIR to an isolated directory with free space. Browser dependencies may be provided by the acceptance runner; no application dependency was added. Screenshots are written to `tests/artifacts/f06` (override with F06_SCREENSHOT_DIR). The SSR check generates fixture HTML consumed by the browser check. Screenshots stub the savings panel with an explicit fixture label; production continues to render the real SavingsLive report and its existing drill-through. Existing savings CI checks that panel independently.

Checks cover four statuses and links, four-row limit, exact approved labels, absent removed cards, source-linked whole numbers, granted squads including the market_lab → /market-lab mapping, successful empty state distinct from unavailable reads, greeting boundaries and actual browser-local time, shared shell at 1440/375, no horizontal overflow, and delayed task-card focus without stealing focus on a subsequent poll.

Focused API checks use the actual dashboard function/router and an isolated in-process database double. Every query must carry the requested tenant; grants use existing row-presence semantics (deletion revokes a grant). Read-key and platform-tenant denials are checked. Existing broader test_dashboards.py also asserts grants and tenant scope; its local collection in the audit venv was blocked by missing jiter, so full provisioned checks remain hosted.

Deploy scope on human merge: main app and its ZA counterpart (Workspace/Tank; deploy_changed.py MAIN_PREFIXES). No runtime config change or migration. Rollback: revert PR #543. Final integrated shared navigation and live signed-in acceptance belong to the integration owner after review.
