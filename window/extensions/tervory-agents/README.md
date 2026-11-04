# Window agents

This extension runs in the existing VS Code compatible Tervory window on Windows,
macOS and Linux. It installs nothing on the user's laptop beyond the window.
Use Connect Tervory to store the personal credential in the window's secret store.
Use Save GitHub credential to send a masked field directly to the server vault;
subsequent tasks select its name. Never paste a GitHub credential into chat.

Start task queues work on the worker server, independent of this extension's
lifetime. Only a fresh `worker/window-<job-id>` branch is published, followed by a
draft PR on the selected repository. The worker never merges. Auto routing and
usage receipts come from the existing command code-turn and policy ladder.

Visible strings are plain placeholders awaiting `docs/figma/window/REGISTER.md`.
Frames needed: task launch (repository, credential name, prompt), named GitHub
vault credential form, task progress with one Cancel action, failure/interrupted
state, PR result with receipt link, and running/finished task list. The PR-review
launch, webhook opt-in and review result frames will be listed with Gate 2.
