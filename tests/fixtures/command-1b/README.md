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
- `node tests/command_1b_contract.cjs` checks the actual Next route and Tank helper with mocked identity/network: trusted headers, CSRF, path allowlist, pinned model lookup, raw and text attachments/downloads, upload limits, reference-only turns, unsupported pin errors, split UTF-8/SSE frames, pending receipt reconstruction, client projection and explicit failures. The pytest wrapper runs this in CI.
- `node tests/dashboards-ui.cjs` retains the founder dashboard checks and updates the root-page assertions to the window.
- Install `esbuild` and `playwright` in a temporary folder; point `COMMAND_TEST_TOOLS` at that folder's `node_modules`. Run `node tests/command_1b_browser.cjs` with cloud Chromium at `/usr/bin/chromium`. No production URL, credential or model is used.
- The browser harness uses the actual Squad control and checks mobile focus/escape, no horizontal overflow, search/rename/new chat, explicit cancel, failed/unknown confirmations without blind retry, safe retry only when explicitly permitted, visible targets/results, unsupported pins, text/binary attachments and downloads, visible token streaming, duplicate-event rejection, persisted reload and client-safe labels.

## Lane A integration

Inspected Lane A PR #224 at `6cedeb2ca40759abc07f64f32aa429064317cdb9` (newer than requested `74fd6d6e`) without merging or editing its files. Also checked the compatible `c56880b5f21c8f9260e38bb7333737daa6e0c0f7` follow-up: per-task savings results are projected as bounded named fields, retaining pending/null amounts. The proxy sends the same-box Workspace key and server-derived user/tenant identity. Browser identity and squad headers are never authority.

- Inline UTF-8 text remains `{name,text}` (200,000 characters). Other formats upload as raw bytes to `threads/{id}/attachments?name=…`; turns send only `{attachment_id}`. Both direct and existing message-file download URLs work. The UI caps a selection at five files/5 MiB; the proxy caps each upload at 5 MiB and preserves A's 20-file/20-MiB thread limit. A checks user, tenant and same-thread reference ownership. Binary content is stored only, explicitly disclosed as unreadable by this text router. Downloads force attachment disposition, octet-stream, no-store and nosniff.
- Empty pending receipts retain `status` and `step_id`; saved step/card markers restore them after reload. Cost and baseline pending states remain visible, null totals stay unknown, and SSE evidence deltas preserve earlier rows. Work receipts cannot overwrite an unrelated streaming answer.
- Action cards retain pending, executing, unknown, failed, confirmed and cancelled states. Allowlisted target fields and results appear without raw payload dumps. Founder-only tools are filtered by tool as well as card kind. Unknown outcomes cannot be retried; only an explicit `failed` + `retry_safe: true` allows a retry. A lost confirmation stays uncertain even if a subsequent snapshot still says pending.
- Roster pins are sent unchanged to A; its pending-capability/unsupported error is shown clearly with an instruction to choose Auto. There is no silent fallback or claimed pin support.

**Remaining integration dependency:** No verified server-owned per-user/organization squad entitlement source exists in the inspected Workspace. `activeTenant` returns identity only; `vaultFetch`'s caller-supplied squad is routing context, not a grant. The command helper strips `X-Tervory-Squad` instead of trusting browser values or granting every squad. Client tool execution remains denied by A until the owning access lane supplies an authoritative source. No new authority, backend capability or paid route was invented. PR #225 stays draft for this dependency.

Additional actual-component compatibility screenshots: [1440px action states/targets/results](compatibility-1440.png) , [375px pending costs after reload](pending-375.png), and [375px stored files/pending pin](attachments-375.png). These are synthetic fixtures, not production execution evidence.

## Live proof after founder deployment

After Lane A is available on the same box, open `/chats` (also `/`), create a thread and send both a UTF-8 note and a binary file. Confirm the stored-only disclosure, reload, and download both. Rename/search the thread. A different user or organization must receive no file/thread/evidence data, and an attachment from a different thread must be rejected.

Match header and answer cost links under `/chats/evidence/{thread}` to the thread's `tank.command_events` and tenant-scoped `tank.ledger` rows. Empty pending step/card costs must survive reload as unavailable, and pending baselines must remain labelled. As an authorized founder, confirm and cancel separate cards and observe targets, execution/results/errors and the Work panel. An unknown action must have no retry; a failed action may offer retry only with explicit `retry_safe: true` from A. Verify a pin rejection asks for Auto without a second request. Client tool execution must remain denied until the separate entitlement dependency is resolved. Check the same flows at 375px and 1440px; non-founders see numbered options, plain cost details and no founder tools.
