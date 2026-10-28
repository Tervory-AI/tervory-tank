# Check Workspace TypeScript before the build

Branch: `codex/workspace-typecheck`.
Base: `origin/main` at `a99f3cb0662516c8fe1b3f27d5b5dcbb90e94fa0`.
Rules: `docs/build/MILESTONES-28OCT-1NOV.md`, “The rules block”, rules 1–11.
Claude opens the PR. No GitHub API, main push, merge or deployment.

## Main baseline

An isolated worktree was created from freshly fetched main. It has no `.next`,
`next-env.d.ts` or prior TypeScript build cache. It uses the already installed
Workspace dependencies through a local node_modules symlink.

```bash
git fetch origin main
git worktree add -b codex/workspace-typecheck /workspace/workspace-typecheck origin/main
git -C /workspace/workspace-typecheck rev-parse HEAD
ln -s /workspace/tervory-tank/workspace/node_modules /workspace/workspace-typecheck/workspace/node_modules
```

Main advanced from `4e74b42` to `a99f3cb`. From the new worktree's `workspace/`:

```bash
source /workspace/tervory-env/activate.sh
npx tsc --noEmit > /tmp/workspace-typecheck-main.txt 2>&1
```

Exit **2**, four errors. [Full output](evidence/main.txt).

| Error on main | Cause | Planned smallest fix |
| --- | --- | --- |
| `workspace/app/chats/window.tsx:7` TS2307 (`done.svg`) | Next's image declarations are unavailable before Next generates `next-env.d.ts`. | Reference Next's existing image declarations from a checked-in type-only file. |
| `workspace/app/chats/window.tsx:8` TS2307 (`attention.svg`) | Same missing declaration. | Same reference; no page change. |
| `workspace/app/chats/window.tsx:9` TS2307 (`planned.svg`) | Same missing declaration. | Same reference; no page change. |
| `workspace/app/tiger/plugins-data.test.ts:3` TS5097 | Node's existing TypeScript test imports a `.ts` file; the compiler does not allow that extension yet. | Enable `allowImportingTsExtensions` with the existing `noEmit` configuration. Keep the executable test import. |

The source fixes, new CI step and clean/planted-error proof are pending.
No UI, wording, design or runtime behaviour change is planned. There is no
founder-browser screenshot for this compiler-only task; no live result is claimed.
