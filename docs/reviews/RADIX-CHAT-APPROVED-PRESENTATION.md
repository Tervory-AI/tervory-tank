# Radix chat presentation handoff

Founder explicitly approved the Radix Figma proposal in chat on **1 November 2026 (America/Los_Angeles)**; the coordinator relayed that approval to this implementation task. Approval covers these presentation fields and states, not a production scan/deploy. The Figma board annotation now records the approval; original Window frames were preserved.

Source: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=205-6112

Nodes: DNS proof 205:6116; desktop results 205:6129; mobile results 205:6179; pending 206:711; failed 206:715; zero findings 206:720; expired proof 206:724. Implementation used high-fidelity `get_design_context` and screenshots before editing. Existing Window fonts, colors and component styles are reused.

## Delivered

- Only `radix.domain.prove`, `radix.passive.scan` and `radix.findings` get the new allowlisted projection. No adapter arguments, tenant IDs, arbitrary nested payloads or credentials are sent to the new view.
- TXT record name/value and scan ID are selectable and copyable. Clipboard rejection shows a selection fallback. DNS expiry displays local time and timezone; the expired state updates while open.
- Every returned Radix finding is reachable in an expandable list, including findings beyond five. Rule, severity, tool, location, explanation and remediation render as React text; target/location strings are never converted to links or HTML. Other tools retain the existing five-item policy.
- Proof follow-up controls **prepare an unsent chat message only**. They do not call Tank or a scan endpoint. Existing durable Confirm, role/tenant checks and retry controls remain authoritative.
- Pending, failed, zero-findings and expired-proof states use actual available data. Missing metadata is not invented.

## Validation

Own checkout, own `npm ci` using Workspace lockfile. Production `npm run build --prefix workspace` and final TypeScript check passed. Python 3.12 Workspace regression suite: 3 passed. Added projection regression runs via pytest/Node, covering eight findings, both account modes, hidden nested credential/tenant fields, malformed/hostile data, no invented status and unchanged non-Radix collection handling.

Local browser harness uses the real Radix component and repository fonts with test-only fixtures. Passed clipboard success/failure, eighth finding expansion, hostile HTML remaining inert text, pending/failed/zero/expired states, unsent follow-up draft, no JavaScript errors, and no horizontal overflow at 320, 375, 768 and 1440 pixels. Screenshots are fixture evidence, not live scans:

- [375px mobile](radix-chat-approved/mobile-375.png)
- [1440px desktop](radix-chat-approved/desktop-1440.png)

Commands:

```sh
npm ci --prefix workspace --ignore-scripts
node tests/radix_chat_presentation.cjs
/home/ammosync/trigger-crm-venv312/bin/python -m pytest tests/test_radix_chat_presentation.py tests/test_command_1b_workspace.py -q
npm run build --prefix workspace
./workspace/node_modules/.bin/tsc --project workspace/tsconfig.json --noEmit
npm install --prefix .git/ui-tools --no-package-lock --ignore-scripts esbuild@0.28.2 playwright@1.64.1
node tests/radix_chat_browser.cjs
```

Backend base `dc616753` independently passed 298 tests, 1 expected OSV skip and 437 subtests. Coordinator-supplied provenance: `/workspace/review-radix-final/.git/review-evidence/{README.md,full-tests-final.log,full-tests-final.xml}`. No backend source changed in this presentation task.

## Limits and next step

Tank deliberately returns only `{scan_id}` after a passive scan. The subsequent `radix.findings` card returns finding details; its scan ID comes from the confirmed arguments. The UI does not fabricate absent completion times, target metadata or severity totals. There is no standalone check-proof endpoint: the proof follow-up prepares a message and any scan still requires the existing confirmation flow. Native clipboard availability is browser-dependent and has a visible fallback.

No live scan, model call, deployment or PR creation performed. Claude opens the PR from `codex/radix-chat-approved-presentation`; review and CI precede merging.
