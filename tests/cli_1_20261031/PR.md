# CLI-1 implementation and bounded evidence

Recorded 2026-10-31, 02:08 PDT / 09:08 UTC. Draft PR #464; companion Tank contract PR #465. Founder acceptance has not occurred. No screenshots of founder testing are claimed. COMMAND-1 audit/screenshots are owned by separate chats after the coordinator narrowed this lane to CLI/PAT.

## What changed (repository line references)

| File | Line | Change |
|---|---:|---|
| cli/package.json | 1 | Pinned @tervory/cli 0.1.0, Node 22, tervory executable, OS keyring/CSV dependencies and lockfile |
| cli/bin/tervory.mjs | 1 | Hidden terminal login, no argv/env credential transport, keychain-only persistence |
| cli/src/client.mjs | 8 | Token-selected fixed app/ZA origins; redirects refused |
| cli/src/client.mjs | 22 | Stateful streamed credential/terminal-control sanitizer; no token/escape chunk-boundary bypass; static output uses the same C1/CSI/OSC handling |
| cli/src/client.mjs | 81 | Native persistent OS keychain binding; Linux Secret Service required, no plaintext fallback |
| cli/src/client.mjs | 166 | Explicit yes-only confirmation; default No/EOF cancel |
| cli/src/client.mjs | 174 | SSE preview, authoritative replacement, sequence deduplication, final answer once; steps, receipts and cards through the same Tank command contract |
| cli/src/client.mjs | 209 | Bounded read-only job watching, changed steps/links/receipts, stop on terminal state, cancellation or poll limit; no model/action retries |
| cli/src/client.mjs | 257 | login/logout/chat/ask/threads/run/build/receipts/models; CSV mapped to existing Base schema in code; saved-thread resume |
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
| `npm test --prefix cli` | Final result: **30 passed, 0 failed**. Earlier edge-test source-path error and test assumptions about a trailing redaction-prefix character / final request after read-only watching were corrected and suite rerun |
| `PYTHONPATH=tank /tmp/tervory-job8-python/bin/python -m pytest -q tests/test_personal_tokens.py` | **8 passed**; one pre-existing Pydantic field-name warning |
| `PYTHONPATH=tank /tmp/tervory-job8-python/bin/python -m pytest -q tests/test_secrets.py tests/test_personal_tokens.py` | **10 passed**, one existing warning, after changing only two synthetic test-key strings to explicit scanner-recognized dummy placeholders |
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

Independent source review cleared bcaf0f27 and independently reproduced 30 CLI tests plus 8 PAT tests on Python 3.12. Its two synthetic-placeholder follow-up commits change test data only; the same 30 CLI tests and exact secret/PAT suite pass afterward. Hosted [Tank failure on the earlier candidate](https://github.com/Tervory-AI/tervory-tank/actions/runs/41187463111/job/124497228651) was the repository secret scanner rejecting those synthetic strings as unlabeled placeholders (1 failed, 29 passed), not discovery of actual credentials. Fixed by using explicit dummy names without weakening the scanner. Hosted [nonroot failure](https://github.com/Tervory-AI/tervory-tank/actions/runs/41187463156/job/124497244193) occurred in the unchanged `site` Docker build: Jost Google-font loader TypeError null[1]. No site/font code was changed. New-head CI must run normally; only one failed-job retry for the same evidenced font failure is authorized. Neither failure is erased or represented as success.

This evidence-only update initially could not be committed: Git reported `unable to write loose object file: Disk quota exceeded`, then `index.lock write error: Disk quota exceeded`. No push was attempted after those failed commits. Removing only this checkout's untracked 253,927-byte TypeScript incremental cache allowed a 32 KB write/fsync probe, but Git index writes still failed. Coordinator explicitly authorized copying only this own checkout to a private root-filesystem directory, preserving the original. Root filesystem had 219 GB available. Python `tempfile.mkdtemp` (mode 0700) and `shutil.copytree(..., symlinks=True)` copied it to `/home/ammosync/cli-1-20261031-btgvebqz/repo`; `git rev-parse HEAD`, `git diff --binary` and `git diff --cached --binary` matched byte-for-byte before any new edit/commit. Verified HEAD was 64420822e34ac1b5237e62d534a85a0346219b70; uncommitted diff SHA256 was 9efe5b626fe2ab388437a383929123153aa36073c80adfb573fae62b0734705b. Original checkout/source/evidence and other checkouts were not deleted or changed by relocation. No reset/force/history rewrite was used.

## Recording

[fake-tank-chat.cast](fake-tank-chat.cast) is a real output capture from the production CLI module invoked by [record.mjs](record.mjs) with a scripted fake transport and scripted input. It is **offline fake-Tank proof**, not a real model run, real ledger measurement, native keychain integration test or founder-browser acceptance. The header and recorded output explicitly state that provenance. Replay with an asciicast v2 player. The recording includes the actual harness command, not a fabricated interactive command invocation.

## Remaining blockers and limits

- **Missing approved Figma frame and exact copy:** Settings > Access tokens, including create/reveal/revoke and empty/error states, at desktop/mobile sizes. Live file ZnphBOJU6657tohGLD3IzS Client screens page 5:114 and Founder screens page 5:115 contain no Access tokens frame/text. C6 terminal presentation 7:292 is explicitly rejected history for unauthorized rand samples. No new UI was invented; no Settings page exists in this draft.
- Companion PR #465 supplies the PAT-authenticated models, known-action proposal and owned task-receipt contracts. This draft alone does not add those routes. The integration lane verifies the combined branches with synthetic data.
- Pinned-model Auto comparison is unavailable without actual historical ledger evidence. No hypothetical price-book amount is shown as measured cost. The CLI never computes receipt money.
- Native macOS/Windows/Linux keychain integration and the founder's own browser acceptance remain unverified. Unit tests inject a keychain interface and synthetic token; they do not claim a native credential-store test.
- Confirmed jobs are read-only polled at most 240 times, 500 ms apart; completed/failed steps, unknown action outcome, user cancellation and the polling bound stop watching. Reopening a saved thread resumes its confirmed jobs. These behaviors are fake-Tank tested; no live worker was started.
- All CI checks and independent review must be green before readiness. This PR remains draft and must not merge automatically.
