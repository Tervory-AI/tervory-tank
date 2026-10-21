# COMMAND-1B evidence

The screenshots render the real `CommandWindow` component with recorded, synthetic HTTP responses, local brand files and local fonts in cloud Chromium. No screenshot claims a live paid run or production result.

| Approved Figma | Implementation |
| --- | --- |
| ![Desktop frame 3:2](figma-desktop.png) | ![1440px window](window-1440.png) |
| ![Mobile chat frame 4:84](figma-mobile.png) | ![375px window](window-375.png) |
| ![Mobile work frame 4:114](figma-work.png) | ![375px work](work-375.png) |

[Client view at 375px](client-375.png). Reference: https://www.figma.com/design/ZnphBOJU6657tohGLD3IzS?node-id=3-2

The official repository logo replaces the wireframe's text logo, as required by AGENTS.md. Search, rename, header totals, attach and model selection are implemented in addition to the wireframe. The fixture has four completed steps out of six and one pending paid action. Founder receipts include tokens and entry IDs; clients receive plain cost fields and numbered model options with the same roster prices. Missing amounts are shown as unavailable.

## Reproduce in a cloud environment

- Install Workspace's existing dependencies without adding a lockfile.
- `node tests/command_1b_contract.cjs` checks the actual Next route and Tank helper with mocked identity/network: trusted headers, CSRF, path allowlist, pinned model lookup, text attachments/downloads, split UTF-8/SSE frames, receipt reconstruction, client projection and explicit failures. The pytest wrapper runs this in CI.
- `node tests/dashboards-ui.cjs` retains the founder dashboard checks and updates the root-page assertions to the window.
- Install `esbuild` and `playwright` in a temporary folder; point `COMMAND_TEST_TOOLS` at that folder's `node_modules`. Run `node tests/command_1b_browser.cjs` with cloud Chromium at `/usr/bin/chromium`. No production URL, credential or model is used.
- The browser harness uses the actual Squad control and checks mobile focus/escape, no horizontal overflow, search/rename/new chat, explicit cancel, failed confirmation without changing state, pinning, attachments, visible token streaming, duplicate-event rejection, persisted reload and client-safe labels.

## Lane A integration

Inspected `cursor/command-1a-tank` at `7d669d6` without merging or editing its files. The UI sends the Workspace key and `x-tervory-user` / `x-tervory-tenant` headers, never browser-supplied identity. Mutating JSON contains only the route's allowed fields. Text files use `{name,text}` and remain in this box's conversation storage. Persisted `receipts[]` are associated to messages by `step_id === message_id`; unmatched finished-work rows remain visible separately. Returning viewers use the contract's permitted thread-snapshot polling.

Lane A currently buffers answers before emitting its token event, rejects pinned turns until the router supports them, and implements build confirmation but not every proposed squad/paid action. Lane B consumes token deltas whenever available and surfaces upstream failures without retrying a possibly charged action or silently replacing a pinned model. These are backend follow-ups, outside this lane. No backend readiness is claimed by fixture tests.

## Live proof after founder deployment

After Lane A is available on the same box, open `/chats` (also `/`), create a thread and send a UTF-8 text attachment. Reload and verify the messages/file download survive. Rename/search the thread. Match header and answer cost links under `/chats/evidence/{thread}` to the thread's `tank.command_events` and tenant-scoped `tank.ledger` rows. Confirm and cancel separate cards and observe the saved status/work panel. Check `/chats` at 375px, open Work and return with Escape. A non-founder must see numbered options, plain cost details and no founder cards. Verify a pinned rejection or interrupted response shows an error and makes no automatic second turn. Actual pin routing, incremental provider tokens and paid-tool execution require Lane A support.
