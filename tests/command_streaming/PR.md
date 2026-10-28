# Stream Command answers through the existing chat

Branch `codex/command-streaming`, from `origin/main` at `2929886`.

The current Command route waits for the full model answer before sending its
single text event. This change will forward LiteLLM streaming output into the
existing SSE path and message bubble, retaining the shared router's policy,
tenant cache, ledger, receipts, tool validation and Confirm/Cancel actions.

Scope: Tank's command turn and the shared router's model transport for that
turn, the existing Workspace stream handling, and offline tests/proof here.
No new interface wording, provider, credential or model call to check work.
Claude opens the PR; remote work by this builder uses git only, never GitHub API.

## Proof status

Implementation and offline proof are pending. No live-done result is claimed.
Tests will cover early ordered tokens, exact final saved text, accounting parity,
whole cache hits, broken-stream persistence, tenant isolation and existing cards.

## Founder test after deployment

Open https://app.tervory.com/chats, ask a question, watch the existing answer
bubble grow before completion, and verify the same receipt appears at the end.
The founder's actual live observation and screenshot are still required.
