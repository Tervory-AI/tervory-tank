# Skala improvement loop

Branch: `codex/skala-improve`, from main `3f469b0`.

Scope: confirmed mistakes become tenant-scoped skill eval cases; nightly data-only
candidate versions must pass existing and new cases before staging. Founder
approval and rollback remain mandatory. Learning-curve data is API-only; no UI.

## Work and proof

Implementation and tests pending. Read AGENTS.md, docs/cursor/CONTEXT.md and the
rules block in docs/build/MILESTONES-28OCT-1NOV.md. Work runs only in the managed
cloud checkout. No GitHub API, production SQL, secrets, paid calls or deployments.

```sh
git fetch origin main
# exit 0, main advanced to 3f469b0
git switch -c codex/skala-improve origin/main
# exit 0
```

Commit and git push after every finished file. Stop if any push fails. Claude
opens the PR; the founder merges. Grok configures the nightly Coolify task using
the command to be documented here once implemented. No scheduled task has been
created by this thread. No founder-browser acceptance or screenshots are claimed.
