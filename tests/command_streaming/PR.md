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

Implementation is in place. No live-done result is claimed.

Tank uses OpenAI SDK 2.54.0 against the existing LiteLLM URL, with retries off.
LiteLLM's built-in `include_cost_in_streaming_usage` is enabled in both regional
configs; its final `usage.cost` enters the existing ledger path. No price is
estimated. Cache/code hits still return whole without opening a model stream.
Jiter previews only the plan's text field; the whole plan is validated before
cards are proposed. Actions still wait for the existing Confirm/Cancel controls.

Only provisional token events are written during generation. Completed messages
and successful receipts are saved after stream completion. Broken streams keep
the existing failed step/error and failed-call accounting: an unknown charge is
marked `not_set` using the existing ledger convention, never displayed as $0.
The Workspace uses the same message bubble and wording, cancels the upstream
reader on disconnect, and removes interrupted previews even if refresh fails.

```sh
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55440/postgres /tmp/command-repo-venv/bin/python -m pytest -q tests/test_command.py tests/test_command_repo_tools.py tests/test_command_streaming.py tests/test_tank_ladder.py tests/test_tank_boots.py tests/test_secrets.py tests/test_model_roster.py --tb=short
```

Result: **192 passed**, no skips, five existing FastAPI deprecation warnings
(68.21 seconds). This includes actual SDK streaming from a stub transport, Tank
over local HTTP, real isolated Postgres, and two complete Tank startups.

```sh
/tmp/command-repo-venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
git diff --check
node tests/command_1b_contract.cjs
node tests/command_1b_pages.cjs
node workspace/node_modules/typescript/bin/tsc --noEmit --project workspace/tsconfig.json
node workspace/node_modules/typescript/bin/tsc --noEmit --allowImportingTsExtensions --project workspace/tsconfig.json
```

Lint, whitespace, both existing Command contract/page suites and the last
diagnostic TypeScript command pass. **Normal TypeScript validation is blocked**
by the unchanged `workspace/app/tiger/plugins-data.test.ts:3` import of
`./plugins-data.ts` (TS5097). The same import is on main at `2929886`; no Tiger
file or project compiler setting is changed in this chat task.

Browser streaming proof and final file/line references are pending.

## Founder test after deployment

Open https://app.tervory.com/chats, ask a question, watch the existing answer
bubble grow before completion, and verify the same receipt appears at the end.
The founder's actual live observation and screenshot are still required.
