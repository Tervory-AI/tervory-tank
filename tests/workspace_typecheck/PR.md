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

## Step 2: CI gate and deliberate failure

`.github/workflows/ci.yml:171` adds `typecheck`, running `npx tsc --noEmit`
in `workspace/`, after Install and before Build. It has no conditional skip or
`continue-on-error`; Build retains its normal success-only execution.

`tests/workspace_typecheck/prove_ci_step.py:12` reads that actual YAML step,
checks its ordering and failure handling, and executes its exact command using
Bash with `-e -o pipefail`. It creates a temporary `workspace/typecheck-proof.ts`
assigning a string to a number, verifies TS2322/exit 2, removes the file in a
`finally` block, and verifies exit 0 again. It never changes an existing source
file. The planted error is not committed or pushed.

From the repository root:

```bash
source /workspace/tervory-env/activate.sh
python tests/workspace_typecheck/prove_ci_step.py > /tmp/workspace-typecheck-step.txt 2>&1
python -m pytest -q tests/test_ci_minutes_workflows.py > /tmp/workspace-typecheck-workflows.txt 2>&1
ruff check tests/workspace_typecheck --select E9,F
git diff --check
test ! -e workspace/typecheck-proof.ts
```

The proof runner exits **0**, with these individual compiler results:

| Run | Compiler output | Exit |
| --- | --- | --- |
| Clean branch | No output; zero errors | 0 |
| Planted error | `typecheck-proof.ts(1,14): error TS2322: Type 'string' is not assignable to type 'number'.` | 2 |
| Plant removed | No output; zero errors | 0 |

[Full step output](evidence/step-working-tree.txt). Its revision is the Step 1
commit; the CI step and proof runner were working-tree changes for this run.
Existing CI workflow tests: **66 passed in 1.40s**, exit 0
([output](evidence/workflows.txt)). Those tests use a local fake curl; no GitHub
API request was sent. Ruff reports `All checks passed!`; both remaining commands
exit 0 without output. This executes the CI step locally, not on GitHub Actions.
Claude opens the PR, which triggers the hosted workflow.

## Changed-file scope

| File:line | Change |
| --- | --- |
| `workspace/tsconfig.json:10` | Permit explicit TypeScript import extensions while retaining `noEmit`. |
| `workspace/types/next-images.d.ts:1` | Reuse Next's existing asset declarations before a Next build. |
| `.github/workflows/ci.yml:171` | Add the compiler gate between install and build. |
| `tests/workspace_typecheck/prove_ci_step.py:1` | Reproducible clean/failing/clean workflow-step proof. |
| `tests/workspace_typecheck/PR.md:1` | Description, error inventory, commands and results. |
| `tests/workspace_typecheck/evidence/` | Captured text outputs linked above. |

No founder-browser screenshot exists for this compiler-only task. There is no
page change to demonstrate and no live result is claimed. No new service,
dependency, key or setting; no production data access or model calls.
