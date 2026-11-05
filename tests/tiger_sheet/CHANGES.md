# Tiger change locations

Base: `d5d3ea2eeb08c9b7a9061274504f0acf53bab2a6`. Step 1 pushed at `2e64a1fa94b46fd659cbafb70ee1fad7534f0040`; sheet pushed at `5418c3c3341b313369572250ac58b7a4cce7d081`. This table covers every changed file in the final branch. First changed lines come from the diff; binary images have no source line.

| File | First changed line |
| --- | --- |
| `.github/workflows/ci.yml` | 261 |
| `docs/acceptance/tiger.md` | 1 |
| `docs/ops/FOUNDER-SETTINGS.md` | 12 |
| `tank/access.py` | 1508 |
| `tank/command.py` | 43 |
| `tests/acceptance/test_tiger.py` | 1 |
| `tests/acceptance/tiger-browser/package-lock.json` | 1 |
| `tests/acceptance/tiger-browser/package.json` | 1 |
| `tests/acceptance/tiger_ui.cjs` | 1 |
| `tests/rig_tiger_prices/test_cycle.py` | 14 |
| `tests/test_access1.py` | 263 |
| `tests/test_command.py` | 49 |
| `tests/test_personal_tokens.py` | 49 |
| `tests/test_tiger_app_page.py` | 67 |
| `tests/test_tiger_competitors.py` | 185 |
| `tests/tiger_alert_page/score.py` | 13 |
| `tests/tiger_g5/test_integration.py` | 13 |
| `tests/tiger_position/PR.md` | 1 |
| `tests/tiger_position/browser.cjs` | 1 |
| `tests/tiger_position/evidence/README.md` | 1 |
| `tests/tiger_position/evidence/browser.txt` | 1 |
| `tests/tiger_position/evidence/build.txt` | 1 |
| `tests/tiger_position/evidence/chats-contract.txt` | 1 |
| `tests/tiger_position/evidence/chats-header.txt` | 1 |
| `tests/tiger_position/evidence/chats-stalls.txt` | 1 |
| `tests/tiger_position/evidence/cli-sign-ins.txt` | 1 |
| `tests/tiger_position/evidence/device-next-fetch.txt` | 1 |
| `tests/tiger_position/evidence/frame-sha256.json` | 1 |
| `tests/tiger_position/evidence/guards.txt` | 1 |
| `tests/tiger_position/evidence/lint.txt` | 1 |
| `tests/tiger_position/evidence/screenshots/256-10.png` | image artifact |
| `tests/tiger_position/evidence/screenshots/256-170.png` | image artifact |
| `tests/tiger_position/evidence/screenshots/256-283.png` | image artifact |
| `tests/tiger_position/evidence/screenshots/256-406.png` | image artifact |
| `tests/tiger_position/evidence/screenshots/256-471.png` | image artifact |
| `tests/tiger_position/evidence/screenshots/256-609.png` | image artifact |
| `tests/tiger_position/evidence/screenshots/267-19232.png` | image artifact |
| `tests/tiger_position/evidence/screenshots/267-19356.png` | image artifact |
| `tests/tiger_position/evidence/screenshots/267-19424.png` | image artifact |
| `tests/tiger_position/evidence/screenshots/267-19562.png` | image artifact |
| `tests/tiger_position/evidence/site-time.txt` | 1 |
| `tests/tiger_position/evidence/tank-flow.txt` | 1 |
| `tests/tiger_position/evidence/tiger-node.txt` | 1 |
| `tests/tiger_position/evidence/tiger-regression-initial.txt` | 1 |
| `tests/tiger_position/evidence/tiger-regression-retry.txt` | 1 |
| `tests/tiger_position/evidence/typecheck.txt` | 1 |
| `tests/tiger_position/evidence/visual-results.json` | 1 |
| `tests/tiger_position/evidence/workspace-existing.txt` | 1 |
| `tests/tiger_position/evidence/workspace-python.txt` | 1 |
| `tests/tiger_position/evidence/workspace-unit.txt` | 1 |
| `tests/tiger_position/fixture.ts` | 1 |
| `tests/tiger_position/frames/256-10.png` | image artifact |
| `tests/tiger_position/frames/256-170.png` | image artifact |
| `tests/tiger_position/frames/256-283.png` | image artifact |
| `tests/tiger_position/frames/256-406.png` | image artifact |
| `tests/tiger_position/frames/256-471.png` | image artifact |
| `tests/tiger_position/frames/256-609.png` | image artifact |
| `tests/tiger_position/frames/267-19232.png` | image artifact |
| `tests/tiger_position/frames/267-19356.png` | image artifact |
| `tests/tiger_position/frames/267-19424.png` | image artifact |
| `tests/tiger_position/frames/267-19562.png` | image artifact |
| `tests/tiger_position/frames/README.md` | 1 |
| `tests/tiger_position/frames/copy.json` | 1 |
| `tests/tiger_position/workspace.test.cjs` | 1 |
| `tests/tiger_sheet/CHANGES.md` | 1 |
| `tests/tiger_sheet/PR.md` | 1 |
| `tests/tiger_sheet/evidence/verification.json` | 1 |
| `tests/tiger_works/workspace.test.cjs` | 13 |
| `workspace/app/tiger/page.tsx` | 6 |
| `workspace/app/tiger/parts.tsx` | 1 |
| `workspace/app/tiger/plugins.tsx` | 25 |
| `workspace/app/tiger/position-actions.ts` | 1 |
| `workspace/app/tiger/position-load.ts` | 1 |
| `workspace/app/tiger/position-model.ts` | 1 |
| `workspace/app/tiger/position-views.tsx` | 1 |
| `workspace/app/tiger/tiger.css` | 684 |
| `workspace/app/tiger/view.tsx` | 3 |
| `workspace/lib/tank.ts` | 697 |
| `workspace/public/tiger/checked-dot.svg` | 1 |
| `workspace/public/tiger/neutral-dot.svg` | 1 |
| `workspace/public/tiger/search.svg` | 1 |
| `workspace/public/tiger/warning-dot.svg` | 1 |

## PR #690 CI follow-up

- `.github/workflows/ci.yml:264`: disable lifecycle scripts for the pinned Tiger browser install.
- `tests/tiger_position/browser.cjs:59`: use deterministic Chromium text rendering; keep the 5% pixel limit.
- `tests/tiger_position/frames/README.md:34`: document the rendering setup.
- `tests/tiger_position/evidence/browser.txt:1`, `visual-results.json:1` and the ten `screenshots/*.png` artifacts above: refresh the passing ten-frame evidence.
- `tests/tiger_sheet/PR.md:5` and `tests/tiger_sheet/evidence/verification.json:59`: record the CI failures, focused validation and unchanged security policy.
