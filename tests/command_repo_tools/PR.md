# Founder repository read tools

Branch: `codex/command-repo-tools`, from `origin/main` at `4e74b42`.

## Scope

Add `repo.prs`, `repo.pr` and `repo.file` to Tank's existing founder tool plumbing.
The fixed repository is `Tervory-AI/tervory-tank`. Outbound reads use only GET at
`https://api.github.com`; file reads use main and allow only `docs/**` or `.md`
files. No writes, redirects to another host, new page text or model calls for
repository reads. An empty `TANK_GITHUB_READ_TOKEN` hides and disables the tools.

The setting is documented by name only. Grok creates it; the founder supplies
its fine-grained read-only value. This build does not create, inspect or use a
real token. Tests use an offline GitHub stub. Remote operations by the builder
use git only. Claude opens the PR; the builder does not call GitHub's API.

## Proof status

Implementation and offline proof are pending. No live result is claimed.

The founder's live test after deployment and configuration is to open
`https://app.tervory.com/chats` and ask:

> which PRs are open and are their checks green?

Record the real answer and a screenshot here after the founder runs it.
