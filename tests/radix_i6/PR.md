# Radix I6 — per-app own-repository deploy gate

Audit: fetched main `55b2e224` read-only and checked it and #634/I2. Both had `scanlib/orchestrate.py:90`'s deploy_blocked count, and R5's tenant-owned archive scan; neither had a per-app deploy decision, override or provenance binding. These missing pieces are added here on `codex/radix-w4`, without merging or rebasing on main. Claude opens the PR after #634; no PR is opened, labelled or merged here.

An optional immutable `commit` on the existing `radix.repo.scan` accepts a Git bundle only, founder only. Tank's existing fixed-repository GitHub reader verifies that it is the current main commit of `Tervory-AI/tervory-tank`; no caller repository/host/ref is accepted. Radix then verifies the cloned bundle HEAD equals that exact commit before scanning or stripping .git. Existing client tar/zip scans and their 5 MiB upload bound are unchanged and cannot create deploy holds. An owned source record binds the accepted room job id, tenant and commit; unregistered, foreign or mismatched jobs cannot enter the gate.

The $0 gate read refreshes completed registered scans and records critical observations per app with their source commit. Source-path mapping is shared with deploy_changed.py. A complete descendant scan may resolve older observations only after the fixed GitHub compare API verifies ancestry; partial scans cannot clear a hold, and stale completion cannot overwrite a descendant's complete result. Failed jobs do not become a clean scan. Queries and schema policies are tenant-scoped, following personal_tokens' existing rollout with ENABLE/FORCE and both policies.

Before each affected app's deploy, deploy_changed.py makes an authenticated fixed-host GET to `https://tank.tervory.com/v1/command/radix/deploy/gate`. Only a well-formed, confirmed critical observation holds that app; main being held does not hold ZA or rooms. Existing actual deployment-failure ordering is unchanged. The log and GitHub step summary name the app, finding id, rule, source commit and file. Missing configuration, unreachable Tank or an invalid/unconfirmed response **fails open**, explicitly saying the gate could not be checked. Redirects are disabled and keys/errors are never printed.

`radix.deploy.override` takes `app` and `finding_id`. It is founder-only, requires the durable Confirm context and exact arguments, and writes the override and $0 code receipt in one transaction. It accepts that observation for that app; it is not a global app bypass. A subsequent scan's new critical observation has a new id and requires a new decision. The next deploy of the overridden app goes ahead; another app's copy of a shared-source finding remains held.

## Activation

The workflow reuses the existing `TANK_API_KEY` GitHub repository secret and adds the non-secret repository variable **RADIX_DEPLOY_TENANT_ID**, set to the founder's own workspace UUID. No key is generated and no value is inspected or changed here. With either value missing, deployment goes ahead with the required unchecked-gate summary; production blocking is not claimed before configuration and merge. No new paid service/provider, Coolify value, deployment or live scan was added. Code under Tank/Radix deploys those apps on merge; the workflow then checks each changed app. No compose/runtime limit changes.

Own-main command example: upload a bundle containing the exact current main commit, then `radix.repo.scan <attachment UUID> <40-hex commit>`; Confirm. Client archives still use the existing one-UUID command. Once the scan finishes the deploy read materializes it; no founder findings read is needed to activate it.

## Changes by file/line

- `tank/deploy_scope.py:1`: shared source-to-app mapping, including regional copies and shared room code.
- `tank/radix_deploy.py:1`: main provenance, source registry, critical materialization, descendant checks, per-app read and atomic founder override.
- `tank/schema.sql:2844`: additive `radix_deploy_scans` and `radix_deploy_findings`, above generated memory, with conditional tenant RLS policies.
- `tank/command_repo.py:24`: narrowly allow the existing reader's fixed main ref, immutable git commit and immutable compare paths; no repository/host expansion.
- `tank/radix_repo.py:30`: validate own-main bundle and register its accepted job; existing client path remains.
- `agents/radix/scanlib/archive.py:131`: verify a bundle's actual HEAD before stripping .git.
- `agents/radix/scanlib/orchestrate.py:73`: retain trusted repository/commit provenance on the real scan result.
- `tank/command.py:47`: founder-only override catalogue, argument model, adapter and confirmed dispatch; optional own-commit repo argument.
- `tank/radix_watch.py:10`: explicit override code plan; `tank/radix_repo.py:162` handles the own-commit repo command without a model.
- `.github/scripts/deploy_changed.py:49`: per-app authenticated gate read, independent skip and fail-open summaries; shared mapping import.
- `.github/workflows/deploy-on-merge.yml:45`: pass the existing credential and founder workspace variable to the gate read.
- `.env.example`: document those names, with no values.
- `tests/test_radix_deploy_gate.py:1`: offline app isolation/fail-open, Confirm/receipt, tenant/source validation, partial/complete observations and real local bundle provenance; confirmed R5-to-gate integration.

## Verification

Existing deployment, backup persistence, founder GitHub tools, R5 and I2 selection: **158 passed, 234 warnings in 56.25 seconds**. New focused suite: **8 passed, 14 warnings in 14.39 seconds**, including actual local Git bundle extraction and the confirmed-repo-scan-to-gate path. Tests use a disposable loopback Postgres and fake GitHub/room/Coolify HTTP; no external request, model, live scan or deployment. Ruff E9,F and whitespace checks pass. PROOF.txt preserves commands and exact output. Hosted CI and founder live acceptance remain pending a PR/merge.
