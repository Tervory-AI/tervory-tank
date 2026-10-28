# Job 8 — Custom Nation on Rig

Branch: `codex/job8-custom-nation-rig`.
Base: `origin/main` at `6c28239`.
Brief: `docs/build/TONIGHT-2026-10-27.md`, section 8, including rules 1–11.
The founder confirmed job 2 (Rig SMTP delivery) complete on 28 October 2026.

## Status

Implementation has not started. This first checkpoint records the brief before
code changes. Claude will open the PR; this thread uses git only and does not
call the GitHub API or merge.

1. Store theme and embed snippet: pending inspection and implementation.
2. Privacy slot: pending inspection of existing Figma evidence. The brief says
   to build the slot and stop if approved notice wording is unavailable.
3. Notice version/time and restricted quote fields: pending step 2.
4. Custom Nation publishable key: pending step 2 and the founder's test-page
   address. No live key has been issued or inspected.
5. Real catalogue, quotes inbox and founder browser test: pending step 2 and
   founder-provided inputs. No live store data has been changed.

## Commands and evidence

Run from `/workspace/tervory-tank`:

```text
git status --short
  No output: the previous task's worktree was clean.
git fetch origin main
  origin/main advanced from 62db0f8 to 6c28239.
git show origin/main:docs/build/TONIGHT-2026-10-27.md
  Read section 8 and its rules 1–11.
git switch -c codex/job8-custom-nation-rig origin/main
  Created the job branch from main.
```

## Founder proof

No founder-browser test or screenshot has been captured for this job. No live
catalogue, quote submission or email delivery is claimed. Offline tests and
file/line changes will be recorded here as each step completes.
