# Tisan: publish a stored build to staging

This API publishes a tenant's checked build, including its CI workflow, into its
own Git branch and deploys only its registered staging application. It adds no
page, button or visible site wording. Production remains behind the existing
founder-approved [promotion](../../agents/tisan/PROMOTION.md) and Radix gate.

## Founder setup

1. Create a separate Coolify team only for client sites. Put each
   site's staging and production apps in it. Create `TISAN_COOLIFY_TOKEN` inside
   that team with **read, write and deploy**, and **without read:sensitive**, so
   it cannot reach any other Tervory app. `TISAN_COOLIFY_URL` is the Coolify HTTPS
   origin, with or without `/api/v1`. These existing settings belong to the Tisan
   room. The publisher reuses `promotion.py`'s Coolify client; it never requests
   environment values, logs or sensitive application settings.
2. Create one private GitHub sites repository, separate from Tervory's source
   repository, and initialize it with a first commit. Set `TISAN_SITES_REPO` on
   Tank to its `owner/name`. GitHub cannot create a branch in an empty repository.
3. Create `TISAN_GITHUB_TOKEN` with these permissions exactly: **on the one sites
   repository only, Contents read and write, and Workflows read and write.
   Nothing else, and no other repository.** Set it on Tank only. The founder
   enters its value; builders handle the setting's name only. It is never sent
   to the room, logged, journalled or returned. Every site's
   `.github/workflows/ci.yml` is committed unchanged, retaining its CI gate.
4. Once per site, create branch `site/<tenant UUID>/<slug>` in that repository.
   Create the staging and production Coolify apps on that repository and branch,
   with automatic deployment **off** on both. Use the repository root as base
   directory and the same build pack on both apps. Configure their domains and
   Git read access in Coolify. Before publishing, staging must have a finished,
   healthy, non-preview deployment pinned to its deployed full 40-character SHA.
   Before promoting, production must meet the same existing promotion checks.
5. Once per site, register the immutable tenant/site binding using
   `POST /v1/tisan/promotion/sites` with `tenant_id`, `site`, `staging`,
   `production` and `url`. Here `site` must equal the stored build's `slug`;
   `staging` and `production` are distinct existing app UUIDs, and `url` is the
   staging HTTPS origin. An app cannot belong to another registered tenant/site.
   Complete the staging domain proof required by Radix before promotion.

All public calls use the existing Workspace key and founder identity headers
`X-Tank-Key` and `X-Tervory-Admin`. The existing
`TERVORY_ADMIN_USER_IDS` allowlist must be configured on Tank and the room.
Tank forwards `TANK_KEY_TISAN` as the room's `TANK_KEY`; no browser receives it.
No credentials or setting values belong in this document or acceptance evidence.

### Runtime configuration prerequisite

The publish source reads `TISAN_SITES_REPO` and `TISAN_GITHUB_TOKEN` from
Tank's environment. `docker-compose.yml` passes both settings to the Boston
Tank container; empty values keep publishing unavailable. `docker-compose.za.yml`
does not pass these settings through, so this setup targets Boston only.
Before publishing live, deploy the mapping and configure the private repository
and its scoped token. Coolify setting values alone are not proof that the running
Tank container received them. No live runtime settings were changed by this
branch. The only Dockerfile edit adds `publish.py` to its existing COPY.

## Publish and inspect staging

`POST /v1/tisan/publish/build` takes this identity (field names only):

- `tenant_id`: the registered tenant UUID.
- `slug`: the registered site and stored build slug.
- `build`: the positive build number already stored by scaffold/builder.
- `operation_id`: a new stable UUID for this action; retain it when polling.

Tisan reads `/data/builds/<tenant>/<slug>/<build>.tar.gz` and its matching
`<build>.json`. It requires a successful manifest and matching file inventory.
Only regular archive files are accepted; paths outside the build, duplicate
paths, symbolic links and Git metadata are refused. There are at most 5,000 files
and 24 MiB of uncompressed contents. Binary bytes and executable modes survive.
No archive path is extracted to disk and no content is invented or replaced.

Tisan verifies the registered staging app's branch, repository, origin and
pinned deployment, then submits the stored files to Tank over the existing
corridor. Tank independently checks the room key, founder, tenant header and
fixed private repository. It creates blobs, one complete tree and one commit,
with the complete build manifest in the commit message. Omitted files are
removed, rather than inherited from the prior build. The site branch is updated
without force; no code-repository branch or default branch is changed.

Tisan pins staging to the full resulting commit, confirms the pin, and requests
one deployment for that staging app only. The request polls that acknowledged
deployment for up to eight minutes. `succeeded` requires its finished non-preview
deployment at the exact commit and a fresh confirmation that staging is healthy,
pinned to that commit and still running that same latest deployment.

A successful response includes `result: succeeded`, with the staging `url` and
full `commit` under `details`. A queue acknowledgement is only `pending`. If
still pending, call `POST /v1/tisan/publish/status` with the **same four identity
fields** and founder headers. Do not create another operation to retry a timeout.
Open the returned staging URL in the founder's own browser and retain actual
screenshots and the full SHA. No local fake screenshots count as this acceptance.

## Failure and concurrent operations

Publishing reuses `/data/promotion.sqlite3` and the promotion journal's durable
per-site reservation. Publishing and promotion/rollback cannot concurrently
mutate the same registered site. Replaying an identical operation reads its
record; changing its actor or build is refused. No import or startup publishes.

A preflight failure records `refused` and releases the reservation. A lost
acknowledgement after a possible Git write or staging update records `unknown`
and retains the reservation. A failed/cancelled staging deployment records
`failed` and also retains the reservation. Interrupted `committing`, `pinning`
and `submitting` operations stay reserved. No automatic retry or force-unlock
endpoint is provided. The founder/operator must reconcile the Git branch and
Coolify app/deployment read-only before an authorized recovery. Publishing never
calls a production app, including when staging fails.

## Promote the approved staging commit

After the founder has inspected staging, use the **existing**
`POST /v1/tisan/promotion/promote` with `tenant_id`, `site`, a new `operation_id`
and the exact staging `commit`. Poll its existing status endpoint. Its browser
checks and Radix gate remain authoritative; publishing does not bypass them or
approve production. Follow `agents/tisan/PROMOTION.md` for promotion and rollback.

## Verification and acceptance record

Offline command run from this branch's own checkout:

```sh
/home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_tisan_publish.py --basetemp=/workspace/codex-tisan-publish/.publish-test-tmp
```

Result: **17 passed in 2.57s**. `httpx.MockTransport` fakes GitHub and Coolify;
there were no real GitHub publish, Coolify, model or production calls. Tests
cover exact committed bytes (including `.github/workflows/ci.yml`), binary and
executable files, complete manifest commit messages, existing/new branches,
founder and tenant checks, shared reservations, secret-marker exclusion from
logs/results, failed deploys, lost acknowledgements, unsafe archives, and no
production endpoint access. Compilation checks used `python3 -m py_compile` on
`agents/tisan/publish.py`, `agents/tisan/app.py` and `tank/main.py` and passed.
The initial `python -m py_compile` attempt failed because `python` is not installed;
using `python3` succeeded. The initial commit attempt failed because this clone
had no Git author identity; a repository-local Codex identity was configured.
No push failed. No PR has been opened by this thread; Claude opens the PR.

Live acceptance is **not performed**. It requires the authorized runtime mapping,
founder-supplied settings and registered apps, a real accepted-content build,
and founder browser evidence. Required proof: publish operation result and full
SHA, actual staging screenshots, founder approval, then existing promotion
result and actual production screenshots. No such screenshots or success claims
are supplied by this branch. PR CI must also be green before merge.

## API references

- [Git trees](https://docs.github.com/en/rest/git/trees): a tree without `base_tree`
  contains precisely the supplied file inventory.
- [Git references](https://docs.github.com/en/rest/git/refs): branch creation,
  non-forced updates, and Contents/Workflows permission sets.
- Existing Coolify API references and deployment attestation rules are recorded
  in `agents/tisan/PROMOTION.md`.

## PR handoff: source locations and final regression

- `agents/tisan/publish.py:29`: stored archive/manifest validation;
  `:65`: journalled Git commit and staging deployment; `:150`: founder room API.
- `agents/tisan/app.py:149`: the one-line publish mount beside promotion.
- `agents/tisan/Dockerfile:45`: only `publish.py` added to the existing COPY.
- `tank/main.py:4191`: fixed private-repository GitHub commit implementation;
  `:4283`: room/founder/tenant checked Git route; `:4308`: founder publish proxy.
- `tests/test_tisan_publish.py:181`: exact committed content and unchanged
  workflow proof, alongside failure, tenant, archive and authentication cases.
- `docs/ops/TISAN-PUBLISH.md:1`: setup, API, runtime prerequisite and acceptance.

Final regression command:

```sh
/home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_tisan_publish.py tests/tisan_promotion/test_promotion.py tests/tisan_promotion/test_tisan_promotion_api.py --basetemp=/workspace/codex-tisan-publish/.publish-test-tmp
```

Result: **52 passed in 7.00s**. `git diff origin/main --check` passed with no
output. `git diff origin/main -- agents/tisan/Dockerfile` confirmed only the
permitted COPY-line addition. These are offline results, not live acceptance
or PR CI results. No screenshots from the founder's browser are available yet.

## Merge verification against main 858dbffa

Fast-forwarded this branch to the reviewed runbook head
`0d6a0bcfc6fcb1591e4d7acd594a12bec2ee6299`, then merged
`858dbffa9ffcaeb6fb643dcab679cd593a773349` without rebase or force.
Resolved only `agents/tisan/app.py` and `agents/tisan/Dockerfile`, keeping both
publish and quote mounts, all existing handlers, and the complete COPY inventory
including quote schema, SMTP transport and Figma documentation. Trigger's
accepted-copy scaffold changes remain from main. The reviewed dedicated-team
instructions and Boston-only, empty-default runtime mappings remain intact.
No live settings, GitHub publish APIs, Coolify APIs, teams or site apps were used.

Commands and outcomes from `/workspace/codex-tisan-publish`:

```sh
/home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_tisan_publish.py tests/tisan_promotion/test_promotion.py tests/tisan_promotion/test_tisan_promotion_api.py tests/test_tisan_quotes.py tests/test_tisan_scaffold.py tests/test_tisan_figma.py --basetemp=/workspace/codex-tisan-publish/.publish-test-tmp
```

**170 passed in 7.39s**, including all 52 publish/promotion cases.

```sh
/home/ammosync/trigger-crm-venv312/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
/home/ammosync/trigger-crm-venv312/bin/python -m compileall -q agents/tisan tank/main.py
git diff origin/main --check
```

All passed. Comparing the entire staged main merge against the old branch with
`git diff --check --cached` also reported an inherited blank line at EOF in
`cli/src/update.mjs:167`; that file was not changed by publish. The publish diff
against current main is clean.

```sh
mkdir -p .publish-pip-tmp
TMPDIR=/workspace/codex-tisan-publish/.publish-pip-tmp /home/ammosync/trigger-crm-venv312/bin/python -m pip install --no-cache-dir --target .publish-test-deps -r agents/trigger/requirements.txt
PYTHONPATH=/workspace/codex-tisan-publish/.publish-test-deps /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/trigger_gate2/test_gate2.py --basetemp=/workspace/codex-tisan-publish/.publish-gate2-tmp
```

**13 passed, 9 skipped in 1.64s**; skipped cases require a test database.
The initial attempt without the isolated dependency directory failed collection
because the existing test interpreter lacked proselint. The checked-in Trigger
requirements were installed only in this checkout and the rerun passed.

From `workspace/`:

```sh
npm ci --no-audit --no-fund --cache /workspace/codex-tisan-publish/.publish-npm-cache
NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA== CLERK_SECRET_KEY=sk_test_dummy npm run build
```

Both passed; Next compiled, type-checked, generated all 38 static pages and
finished build traces. The build used the existing CI's synthetic Clerk values,
not credentials. No founder browser acceptance or live publish is claimed.
