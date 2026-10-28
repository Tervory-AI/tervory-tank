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

| Error on main | Cause | Fix |
| --- | --- | --- |
| `workspace/app/chats/window.tsx:7` TS2307 (`done.svg`) | Next's image declarations are unavailable before Next generates `next-env.d.ts`. | `workspace/types/next-images.d.ts:2` references Next's existing asset declarations. |
| `workspace/app/chats/window.tsx:8` TS2307 (`attention.svg`) | Same missing declaration. | Same reference; no page change. |
| `workspace/app/chats/window.tsx:9` TS2307 (`planned.svg`) | Same missing declaration. | Same reference; no page change. |
| `workspace/app/tiger/plugins-data.test.ts:3` TS5097 | Node's existing TypeScript test imports a `.ts` file; the compiler does not allow that extension yet. | `workspace/tsconfig.json:10` enables `allowImportingTsExtensions` with the existing `noEmit` configuration. The executable test import stays intact. |

## Step 1: compiler fixes

```bash
# From workspace/
source /workspace/tervory-env/activate.sh
npx tsc --noEmit > /tmp/workspace-typecheck-fixed.txt 2>&1
# From repository root
node --experimental-strip-types --test workspace/app/tiger/plugins-data.test.ts > /tmp/workspace-typecheck-tiger.txt 2>&1
git diff --check
```

Typecheck: **exit 0, zero errors, no output**. The existing Tiger tests:
**2 passed, 0 failed**, exit 0 ([output](evidence/tiger.txt)). Diff check: exit 0,
no output. Node `22.23.4`, npm `10.9.9`, installed TypeScript `5.9.3`.

Only compiler configuration and a declaration reference changed. No source
imports, page output, wording, design or runtime behaviour changed. Strict
checking, file inclusion and `noEmit` remain enabled; no error suppressions.

The new CI step and clean/planted-error proof are next. No founder-browser
screenshot exists for this compiler-only task; no live result is claimed.
