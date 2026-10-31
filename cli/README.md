# @tervory/cli

Node 22. macOS Keychain, Windows Credential Manager, or Linux Secret Service is required for login. The CLI uses the pinned `@napi-rs/keyring` binding, never a plaintext credential file. Linux requires a running unlocked Secret Service; an unavailable keychain fails without a storage fallback. Cross-platform native keychain integration has not been exercised in founder acceptance.

Install the draft package locally in an isolated development checkout with `npm ci --prefix cli`, then run `node cli/bin/tervory.mjs help`. This package has not been published to npm. Do not install anything on the founder's laptop as part of automated work.

`tervory login` reads a personal token without echoing it and validates it before saving it in the OS keychain. It accepts no token arguments or environment variables. `tervory logout` removes that keychain entry. Tokens must be created by the authenticated Workspace; the Settings > Access tokens page is blocked until its approved Figma frame and exact copy exist. Do not use a service key in this CLI.

```
tervory chat [thread] [--model auto|name]
tervory ask "question" [--thread id] [--model auto|name] [--file path]
tervory threads
tervory run base batch --file path.csv [--thread id]
tervory run agent task --args '{"argument":"value"}' [--thread id]
tervory build "change" [--thread id]
tervory receipts thread-or-task-id
tervory models
```

Interactive chat ends on `/exit` or EOF. Tool cards require an explicit `y` or `yes`; every other answer cancels. Non-interactive input cannot confirm. `run` uses the existing Tank tool name and argument schema; Base CSV intake maps headers and records to the existing batch contract. Other tool files must use that tool's JSON schema through `--args`. Tank enforces the schema and current role. `build` displays the submitted change as its brief, proposes the existing build card, and waits for confirmation; it does not spend a model call to rewrite the user's text.

The token envelope selects `https://app.tervory.com` or `https://za.tervory.com`. There is no URL override or cross-box fallback. Tank verifies the complete credential hash and region; the envelope alone grants no identity. The public command route forwards only the bearer credential to its fixed local Tank. It never sends a service key or client-supplied user, tenant or role assertions.

Receipt amounts are displayed exactly as Tank returns them. Auto comparisons require actual historical ledger evidence; otherwise they are unavailable. No price-book projection is presented as a measured cost. An interrupted stream is reported and never automatically retried, because a turn may have incurred cost.

The `models`, known-action `run`, and owned task receipt endpoints are supplied by companion draft PR #465. This branch must be tested with that backend before founder acceptance. Confirmed jobs are watched with read-only snapshot polls every 500 ms, for at most 240 polls; Ctrl-C cancels watching, never the already confirmed job. The CLI prints changed steps, produced links and ledger receipts and stops at completion, failure, unknown outcome or the polling bound. Reopen `chat <thread>` to show saved messages and resume watching. No failed or interrupted turn/action is automatically resubmitted.

Interactive terminals show provisional answer text on a single stderr preview line; stdout receives the final answer once. Tank's `replace` event replaces the provisional answer, and duplicate sequence numbers are ignored. Non-interactive stdout receives only the validated final answer, avoiding stale previews in scripts.

`npm test --prefix cli` runs fake-Tank tests with synthetic credentials and data only. No provider requests or live account changes occur. Evidence in `tests/cli_1_20261031/` is labeled offline fake-Tank proof and is not a founder-browser test.
