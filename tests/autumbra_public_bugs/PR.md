# Autumbra public-page bugs

Branch: `codex/autumbra-public-bugs`.
Base: `origin/main` at `4e74b42`.
Rules: `docs/build/MILESTONES-28OCT-1NOV.md`, “The rules block”, rules 1–11.
Claude opens the PR; no GitHub API calls, main push or merge in this thread.

## Initial inspection

On this main revision, `workspace/app/shell.tsx:64` already calls
`usesOwnShell(pathname)`, imported from `workspace/app/product-nav.ts`.
That helper already includes `/autumbra` in both its exact and nested route sets
(`product-nav.ts:80,93,101`). `/admin/autumbra` is a shared-shell route.
The requested private-console line and its `Link` import are still present in
`workspace/app/autumbra/page.tsx`.

Offline render and sign-in-boundary verification is pending. No live result or
founder-browser screenshot is claimed. The final changes, commands and results
will be recorded here before the final push.

```text
git status --short
  Clean worktree before starting.
git fetch origin main
  origin/main advanced from 6c28239 to 4e74b42.
git switch -c codex/autumbra-public-bugs origin/main
  New branch from main.
```
