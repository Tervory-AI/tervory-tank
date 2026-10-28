# Trigger first build — source verification blocked

## Status and exact blocker

Not implemented; not ready for a product PR. The requested upstream `brand-voice-spec` could not be verified on GitHub. The matching public artifact is [thehonestape/brand-voice-spec on Hugging Face](https://huggingface.co/datasets/thehonestape/brand-voice-spec), whose dataset card states CC BY 4.0 and identifies `voice.json` and `SCHEMA.md`. This is a source-location mismatch, not a finding that the Hugging Face artifact prohibits commercial use.

- Blocked action: select and pin the required GitHub `brand-voice-spec` source, then implement its format for Trigger's tenant voice table and checks.
- Missing: the intended GitHub repository URL, or an explicit correction naming the Hugging Face artifact as the intended source.
- Status: unresolved source reference; no permission denial and no uncertain production action.
- Evidence: web searches did not identify the exact GitHub repository. GitHub's public HTML repository search was reachable once; a later read returned HTTP 429. `GIT_TERMINAL_PROMPT=0 git ls-remote https://github.com/thehonestape/brand-voice-spec.git HEAD` returned “Repository not found” (exit 128).
- Rule applied: the owner's rules block, rule 9: “If something blocks you ... stop at that point and report exactly what is missing. Do not ask, do not guess, do not work around it.” Job item 2 also says to stop and report if a named source is unclear or not free.
- No substitute voice format, paid service, model checker, or different brand-voice project was selected.

## What changed (file and line)

Only `tests/trigger_first_build/PR.md:1`: this proof record. No runtime code, schema, compose, tools, policy or page changes. No Trigger capability is available yet.

Branch: `codex/trigger-first-build`, created from `origin/main` at a99f3cb0662516c8fe1b3f27d5b5dcbb90e94fa0.
Early checkpoint: `1ebdc4c` (`docs(trigger): record first build scope and verification checkpoint`).

## Completed source inspection

The following are inspected commit pins, not installed runtime dependencies:

| Requested source | Verified repository and commit | Licence evidence at that commit |
| --- | --- | --- |
| agent-style | https://github.com/yzhao062/agent-style/tree/d1bdb0fa0c6305942bf43805edeae330946e8cf7 | `NOTICE.md`, `LICENSES/MIT.txt`, `LICENSES/CC-BY-4.0.txt`: code MIT, rule content CC BY 4.0; preserve notices and attribution. |
| agent-stylebooks | https://github.com/Neeeophytee/agent-stylebooks/tree/85b318fcb69fbb50b9f066aadf81750d368c6988 | `LICENSE`, `NOTICE.md`, `PROVENANCE.md`: original repository text/code MIT. Third-party source guides retain their separate terms; do not copy those guides. Current source has 16 books and identifies the original 11 separately; the brief requests only those original 11. |
| practical-prose | https://github.com/jlevy/practical-prose/tree/fc0b2a725dd3d8b0dd347f92058b184a01eac44d | `LICENSE`: code MIT, rubric/content CC BY 4.0. Only the rubric is in the requested scope; no scorer was installed or run. |
| brand-voice-spec | No verified GitHub source. Matching artifact: https://huggingface.co/datasets/thehonestape/brand-voice-spec | Dataset card states CC BY 4.0. Not substituted or pinned as a dependency because the brief names GitHub and disallows guessing around blockers. |

MIT and CC BY 4.0 permit commercial reuse subject to their terms. The stylebooks' MIT grant covers their independently written repository material, not the restricted or noncommercial third-party guides discussed in their provenance file. No upstream material was vendored.

Proselint and LanguageTool integration/pinning are not completed. No checker implementation claims are made.

## Commands and results

All commands ran in the saved cloud coding environment, never the owner's computer. GitHub API was not used.

```sh
git status --short                         # clean before branch creation
git fetch origin main                     # success; updated origin/main to a99f3cb
git show origin/main:docs/build/MILESTONES-28OCT-1NOV.md
git show origin/main:AGENTS.md             # both read successfully
git switch -c codex/trigger-first-build origin/main  # success
cat agents/tiger/Dockerfile agents/tiger/docker-compose.yml  # inspected
rg --files agents/tiger                    # inspected existing room structure
rg -n 'agent-style|agent-stylebooks|brand-voice-spec|practical-prose|Trigger' docs plan
# plan/ is absent from this checkout; no intended source URL found in docs.
git add tests/trigger_first_build/PR.md
git commit -m 'docs(trigger): record first build scope and verification checkpoint'
git push -u origin codex/trigger-first-build  # success; 1ebdc4c

git clone --depth 1 https://github.com/yzhao062/agent-style.git /tmp/trigger-agent-style
git clone --depth 1 https://github.com/Neeeophytee/agent-stylebooks.git /tmp/trigger-agent-stylebooks
git clone --depth 1 https://github.com/jlevy/practical-prose.git /tmp/trigger-practical-prose
# all three clones succeeded, for read-only inspection.
GIT_TERMINAL_PROMPT=0 git ls-remote https://github.com/thehonestape/brand-voice-spec.git HEAD
# failed: Repository not found; no repository contents obtained.
git diff --check                          # passed for this record
```

Python `pathlib`/`subprocess` read the cloned repositories' commit hashes and root licence/notice files. `rg` read stylebook provenance and original-11/current-16 inventory references. Public web searches used the exact project names and found the Hugging Face artifact. A Python `urllib.request` GET of GitHub's public HTML repository search succeeded; repeating it to parse structured results returned HTTP 429. These were source-discovery reads, not API calls or product tests.

## Tests and founder proof

No implementation tests, container builds, model calls, deployment, live-data changes or founder browser test were run. No screenshots exist because Trigger has not been implemented or deployed. The requested /chats draft-plus-report and no-model paragraph-check acceptance tests remain unproven. Tests passing would not by itself establish completion under the owner's rules.

## Handoff

Claude opens any eventual PR; none was created here. Grok creates `agent-trigger` in Coolify. The founder merges and performs the live browser acceptance test. Resume implementation only after the intended brand-voice-spec source is unambiguous. Keep all secrets out of code and proof; settings are by name only.
