# Window handover, 4 November 2026

The founder assigned ownership to “Wave 3 — Chat CLI”. This branch preserves
an in-progress snapshot from `/workspace/codex-window`; it is not a completed gate.
Do not merge this snapshot wholesale without reconciling the owner's current work.

Commits inherited by this branch:

- `ed6d3d91`: initial approved-command support on all desktop operating systems,
  CLI version/changelog, README and CLI acceptance updates.
- `2ad00d09`: probes Bubblewrap and Seatbelt usability before choosing the
  approval-only fallback, supplies Windows temporary-directory variables, and
  adds a real approved-command invocation to the Windows CI job.
- The following WIP snapshot: checksum-pinned Code-OSS source preparation,
  product patch, native packaging draft, built-in extension discovery, and
  partially overlapping panel implementations preserved from the shared folder.

Known unfinished work for the owner:

- The panel manifest points at `media/icon.svg`, which is absent. The exact logo
  exists only in the repository's supplied PNG/PDF assets; do not redraw it.
- `extension/extension.cjs` loads `src/extension.mjs`. The other implementation,
  `src/extension.cjs` and `src/controller.mjs`, was already in the shared checkout.
  Reconcile them. `extension/package-lock.json` also predates the new manifest.
- Build scripts moved from `window/scripts/` to `window/build/`. The existing
  `build/extension.mjs` and any caller/documentation referring to the old location
  need reconciliation. Neither a full native build nor six installers were tested.
- The workflow currently runs source/product contracts on PRs; its PR build still
  needs to build Linux and boot the actual desktop headlessly with a folder.
- Gate 3 still needs tested per-hunk editor integration, fake device login,
  end-to-end ask/edit/accept/undo/command and cancellation. Syntax checks alone
  do not establish these behaviors. Gate 5 has not been implemented.
- The founder clarified that the panel must use `cli/src/client.mjs` exclusively
  for login, and display “Trigger sign-in”. The placeholder currently says
  “Sign in”; update this with the Figma wording. No panel provider-specific code
  should be added. US migration is owned by `codex/trigger-signin`.
- The build must discover every `window/extensions/<name>/` directory. Those
  directories belong to the other threads; none was edited in this handover.
- Signing setting names still need adding to `docs/ops/FOUNDER-SETTINGS.md`.

Checks before snapshot: the CLI code-mode suite passed 41 cases with 3 OS skips;
approved-command fallback cases passed 2/2; the source/product contract passed
1/1; panel module syntax and `git diff --check` passed. These are local results,
not CI evidence. Precheck logs live under the handover checkout's `.tmp/`.
The original checkout's earlier Semgrep invocation timed out; no scan exception
or skip was added.
