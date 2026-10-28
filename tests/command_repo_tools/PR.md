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

Implementation is complete. No live result is claimed.

Offline verification uses a socket-free `httpx.MockTransport` for GitHub and an
isolated local Postgres. The existing Command tests and actual Tank boot test
also run: **140 passed**, with five existing FastAPI lifespan deprecation warnings.

```sh
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55439/postgres COMMAND_REPO_SNAPSHOT=/tmp/command-repo-snapshot.json /tmp/command-repo-venv/bin/python -m pytest -q tests/test_command_repo_tools.py tests/test_command.py tests/test_tank_boots.py --tb=short
```

The new tests prove founder-only discovery and dispatch, clients in two tenant
contexts denied, empty-setting/revoked-founder checks before Confirm, GET-only
routes/transport, fixed repository and main ref, path/symlink/submodule refusal,
checks plus legacy statuses, pagination without following remote Link URLs,
sanitized failures, and confirmed results persisted/replayed only to their owner.
The actual Tank starts twice against an empty local database.

`tank/command.py:39` adds the founder tools; `:94` gates discovery;
`:738` defines argument schemas and authenticated GET handlers; `:889` registers
the existing command adapters. `tank/command_repo.py:18` fixes the repository
and endpoint allowlist; `:37` manages the runtime client; `:50` permits only GET;
`:91` reads head checks/statuses; `:125` lists PRs; `:140` reads files changed in
a PR; `:155` reads main through Git tree modes and blob hashes.
`.env.example:34` and `docker-compose.yml:211` add the empty setting by name.
`tank/Dockerfile:5` includes the new helper in the Tank image.

The UI is unchanged. Results use its existing Response field; this includes
the complete requested page rather than relying on the five-item preview.
Every read retains the existing Confirm action. Checks are for the PR's head
commit and include both check runs and legacy commit statuses; missing or
incomplete checks are unknown, never green. This does not assert mergeability
or that every branch-protection requirement is satisfied. PR/file pagination
returns `has_more` and `next_page`. File content is UTF-8, at most 64,000 bytes;
binary files, symlinks, submodules and truncated tree responses are refused.

The first test attempt used only minimal dependencies: existing command tests
reported missing `redis`, with database cases skipped. Installing the checked-in
Tank requirements and starting isolated Postgres resolved that environment gap.
The first new-suite run had four test assertions assuming a tools envelope;
the existing endpoint returns a list. Corrected those assertions before the
successful combined run above.

```sh
/tmp/command-repo-venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
git diff --check
/tmp/command-repo-venv/bin/python -m pytest -q tests/test_secrets.py --tb=short
```

Results: all lint checks passed with the pinned Ruff 0.17.2; no whitespace
errors; both secret-scan tests passed. An earlier Ruff 0.15.0 run flagged
fixture-import F811 errors; after matching the repository's pinned version,
the full lint command passes. The new suite also passes separately: 64 passed.

Browser rendering proof is pending.

The founder's live test after deployment and configuration is to open
`https://app.tervory.com/chats` and ask:

> which PRs are open and are their checks green?

Record the real answer and a screenshot here after the founder runs it.
