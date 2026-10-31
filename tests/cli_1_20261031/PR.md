# CLI-1 implementation and bounded evidence

Recorded 2026-10-31, 02:02 PDT / 09:02 UTC. Draft PR #464; companion Tank contract PR #465. Founder acceptance has not occurred. No screenshots of founder testing are claimed. COMMAND-1 audit/screenshots are owned by separate chats after the coordinator narrowed this lane to CLI/PAT.

## What changed (repository line references)

| File | Line | Change |
|---|---:|---|
| cli/package.json | 1 | Pinned @tervory/cli 0.1.0, Node 22, tervory executable, OS keyring/CSV dependencies and lockfile |
| cli/bin/tervory.mjs | 1 | Hidden terminal login, no argv/env credential transport, keychain-only persistence |
| cli/src/client.mjs | 8 | Token-selected fixed app/ZA origins; redirects refused |
| cli/src/client.mjs | 23 | Stateful streamed credential/terminal-control sanitizer; no token/escape chunk-boundary bypass |
| cli/src/client.mjs | 82 | Native persistent OS keychain binding; Linux Secret Service required, no plaintext fallback |
| cli/src/client.mjs | 166 | Explicit yes-only confirmation; default No/EOF cancel |
| cli/src/client.mjs | 174 | SSE tokens, steps, receipts and cards through the same Tank command contract |
| cli/src/client.mjs | 207 | login/logout/chat/ask/threads/run/build/receipts/models; CSV mapped to existing Base schema in code |
| tank/personal_tokens.py | 39 | Full credential hash lookup before accepting server-stored user/tenant; actual local-box check; forged identity headers ignored |
| tank/personal_tokens.py | 67 | Workspace-only mint/list/revoke; never returns stored hashes; one-time creation response disables caching |
| tank/personal_tokens.py | 113 | Existing command dependency reused; no global Tank service-key bypass |
| tank/main.py | 4364 | Single personal-token module registration |
| tank/schema.sql | 2251 | Additive idempotent hash-only table; follows an already enabled tenant RLS rollout |
| workspace/lib/tank.ts | 8 | Bounded public PAT adapter to fixed local Tank; hard route/method/query allowlist, no caller identity/service-key forwarding |
| workspace/app/v1/command/[...path]/route.ts | 1 | Public command route calls the server-side Tank adapter |
| workspace/middleware.ts | 13 | CLI command namespace reaches its PAT authentication boundary; browser pages retain Clerk |
| cli/test/client.test.mjs | 1 | Fake-Tank flows, cancellation, client tools, ledger values, failures, every SSE/UTF-8 boundary |
| cli/test/public-edge.test.mjs | 1 | Actual public adapter invoked by CLI with fake Tank: region, header, route, cursor, signal, body size and refusal checks |
| tests/test_personal_tokens.py | 1 | Offline token hashing, owner scope, region refusal, header escalation and revocation tests |
| .github/workflows/cli.yml | 1 | PR-only Node 22 locked-install, syntax, fake-Tank tests and package dry run |

## Commands and actual results

Commands below ran in the isolated checkout `/tmp/tervory-prompt1-20261031` unless another directory is specified. No provider calls, live database SQL, deployment, worker operations or ZA infrastructure operations were run.

| Exact command | Result |
|---|---|
| `git clone https://github.com/Tervory-AI/tervory-tank.git /tmp/tervory-prompt1-20261031` | Passed |
| `git fetch origin main` | Passed |
| `git checkout -B codex/cli-1-20261031 origin/main` | Passed |
| `ls docs/cursor/CLI-1-tervory-cli.md docs/cursor/COMMAND-1-the-window.md workspace/app/chats tank/command.py` | Passed; both briefs and existing COMMAND files present |
| `git config user.name 'Codex'` and `git config user.email 'codex@openai.com'` | Repository-local identity after initial commit failed with missing identity |
| `npm install --prefix cli --ignore-scripts --no-audit --no-fund` | Passed; pinned lockfile committed |
| `npm test --prefix cli` | Final result: **24 passed, 0 failed**. Earlier edge-test source-path error was corrected and suite rerun |
| `PYTHONPATH=tank /tmp/tervory-job8-python/bin/python -m pytest -q tests/test_personal_tokens.py` | **8 passed**; one pre-existing Pydantic field-name warning |
| `node --check cli/bin/tervory.mjs && node --check cli/src/client.mjs` | Passed |
| `npm pack --dry-run` (cwd `cli/`) | Passed; package contains executable, client, manifest, README and changelog; no publish |
| `npm pack --prefix cli --dry-run` (checkout root) | Failed: npm looked for root package.json; corrected by running command in cli/ |
| `npm ci --prefix workspace --ignore-scripts --no-audit --no-fund` | First attempt reported thousands of errno -122 TAR write errors despite exit 0; **not accepted as success**. After coordinator resume, verified own node_modules was an untracked real directory, removed only that incomplete install, then reran: clean install, 45 packages, no TAR errors |
| `./node_modules/.bin/tsc --noEmit` (cwd `workspace/`) | Passed after clean locked install |
| `PYTHONPATH=tank /tmp/tervory-job8-python/bin/python -m pytest -q tests/test_personal_tokens.py tests/test_command.py tests/test_command_streaming.py` | Failed collection: environment missing yaml |
| `PYTHONPATH=tank /tmp/tervory-job8-python/bin/python -m pytest -q tests/test_personal_tokens.py tests/test_command.py` | 25 passed, 26 skipped, 32 setup errors: environment missing yaml; **not green** |
| `PYTHONPATH=tank /tmp/tervory-rls-python/bin/python -m pytest -q tests/test_personal_tokens.py tests/test_command.py tests/test_command_streaming.py` | 30 passed, 42 skipped, 32 setup errors: existing environment selectolax.parser backend deprecated; **not green**. Independent acceptance lane owns correctly pinned combined integration evidence |
| `node tests/cli_1_20261031/record.mjs` | Passed; generated valid asciicast v2 with scripted fake-Tank chat, steps, synthetic receipt, N cancellation; no native keychain/model/browser call |
| `git rev-parse HEAD` and `git ls-remote origin refs/heads/codex/cli-1-20261031` | Local and remote both 259d95ee after storage failure |
| `git fetch origin codex/cli-1-20261031` | Normal fetch passed after explicit coordinator writable confirmation and resume; no reset/force |

Every completed source/test/document file was committed and pushed. Commit commands use `git add <file> && git commit -m '<subject>' && git push`; `git log origin/main..HEAD --format='%h %s' --name-only` lists each exact subject and file. Initial push used `git push -u origin codex/cli-1-20261031`. One push accepted remote 259d95ee but failed writing the local tracking-ref lock due to quota; work stopped immediately and coordinator was notified. Only after explicit resume and successful write probe/fetch did implementation continue. No push to main, force push, history rewrite or merge occurred.

## Recording

[fake-tank-chat.cast](fake-tank-chat.cast) is a real output capture from the production CLI module invoked by [record.mjs](record.mjs) with a scripted fake transport and scripted input. It is **offline fake-Tank proof**, not a real model run, real ledger measurement, native keychain integration test or founder-browser acceptance. The header and recorded output explicitly state that provenance. Replay with an asciicast v2 player. The recording includes the actual harness command, not a fabricated interactive command invocation.

## Remaining blockers and limits

- **Missing approved Figma frame and exact copy:** Settings > Access tokens, including create/reveal/revoke and empty/error states, at desktop/mobile sizes. Live file ZnphBOJU6657tohGLD3IzS Client screens page 5:114 and Founder screens page 5:115 contain no Access tokens frame/text. C6 terminal presentation 7:292 is explicitly rejected history for unauthorized rand samples. No new UI was invented; no Settings page exists in this draft.
- Companion PR #465 supplies the PAT-authenticated models, known-action proposal and owned task-receipt contracts. This draft alone does not add those routes. The integration lane verifies the combined branches with synthetic data.
- Pinned-model Auto comparison is unavailable without actual historical ledger evidence. No hypothetical price-book amount is shown as measured cost. The CLI never computes receipt money.
- Native macOS/Windows/Linux keychain integration and the founder's own browser acceptance remain unverified. Unit tests inject a keychain interface and synthetic token; they do not claim a native credential-store test.
- Confirmed long-running jobs remain stored in the thread. The current CLI does not continuously poll job progress after a card has been confirmed; its next turn/receipts command can retrieve subsequent evidence. Do not claim complete live-job acceptance.
- All CI checks and independent review must be green before readiness. This PR remains draft and must not merge automatically.
