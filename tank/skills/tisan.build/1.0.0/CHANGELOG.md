# 1.0.0

Candidate only; founder approval in Skala is required. Builds validated section plans in the existing room with accepted tenant-bound Trigger copy and supplied media. No template, visual design or publishing changes.

## Review handoff (1 November 2026)

Implementation locations:
- `agents/tisan/builder.py:19`: reuse scaffold functions; `:33`: compile the actual manifest's schema constraints with the existing Pydantic engine (unknown keywords fail closed); `:94`: validate plans; `:136`: Tank planning and one validation retry; `:159`: site/page/array slots and purposes; `:171`: tenant/write-bound accepted copy; `:198`: assemble/check/archive; `:263`: existing ready event.
- `agents/tisan/app.py:100`: build handler and ten-minute timeout; `:136`: build eval selection.
- `agents/tisan/Dockerfile:45`: builder.py added to the existing COPY line only.
- `tank/command.py:45`: founder-only tool; `:907`: typed input; `:1031`: existing Confirm/Skala adapter.
- `tank/main.py:3249` and `:3276`: existing room eval hookup includes the new skill.
- `tank/schema.sql`: one additive `tisan.plan` policy, matching trigger.write's specified rung 1/luna/tenant cache seed, with ON CONFLICT DO NOTHING.
- `tank/skills/tisan.build/1.0.0/`: candidate package, room job adapter and deterministic evals. Quick copy-needed results return through the existing action result; long builds remain queued in the room and emit the existing ready event after success. No new approval is seeded.
- `tests/test_tisan_builder.py` and `tests/test_tisan_builder_adapter.py`: contract, retry, copy isolation, media, archive, failed checks and founder/Confirm coverage.

The sections contract files are unmodified files merged from `origin/tisan/sections-contract` (6cf65168). No fixture manifest is used. Scaffold and template UI are unchanged by the builder implementation.

Validation commands and observed results (run from `/workspace/codex-tisan-builder`):

```sh
PYTHONPATH=tank /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_command.py::test_plans_are_bounded_and_cannot_supply_authority tests/test_command.py::test_adapters_force_identity_and_do_not_accept_paid_route_overrides tests/test_command.py::test_scan_adapter_preserves_packaged_skill_input tests/test_tisan_builder.py tests/test_tisan_builder_adapter.py tests/test_tisan_scaffold.py
```

Result: 49 passed, 1 skipped, 2 warnings in 2.49s. The skip is the separately invoked real npm build. Pydantic warns about `copy` shadowing BaseModel.copy and the pre-existing Trigger `register` field.

```sh
mkdir -p .git/builder-tmp
TMPDIR=/workspace/codex-tisan-builder/.git/builder-tmp TISAN_RUN_BUILD=1 TISAN_NPM_OFFLINE=1 TISAN_NPM_CACHE=/home/ammosync/.npm /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q -s tests/test_tisan_builder.py::test_full_build_with_real_checks
```

Result: 1 passed in 61.37s. Manifest: `ok: true`, `detail: ""`; checks `npm ci`, `npm run lint`, `npm run build`, `npm test` all `ok: true`. Archive: `/workspace/codex-tisan-builder/.git/builder-tmp/pytest-of-ammosync/pytest-0/test_full_build_with_real_chec0/builds/11111111-1111-4111-8111-111111111111/test-build/1.tar.gz`. The written plan includes home and privacy; the copy endpoint is an HTTP test double. No model or paid check was made.

Earlier full-build attempts used the same command without TMPDIR: the first omitted privacy and failed the privacy gate; the next included privacy but failed writing a temporary HTML test file. A standalone Node write reproduced errno -122 (quota exceeded) in /tmp. Using this checkout's own temporary folder resolved the environment failure. The builder returned check failure output and produced no archive on those failures; it did not repair generated code.

```sh
git fetch origin main && git merge origin/main && git diff --check
```

Result: fetch succeeded, already up to date, diff check passed. Main was merged before every push. All pushes succeeded. The first commit attempt needed repository-local Git author configuration; it was then committed and pushed successfully.

Pending proof: Claude opens the PR; PR CI and separate review have not run. No founder staging/browser test or screenshots exist yet. The contract explicitly defers section visuals until approved Figma; this build proves validation, content assembly and existing scaffold checks, not section rendering. The live acceptance flow still depends on the sections, publish and Trigger changes being merged, founder skill approval in Skala, then the founder's /chats → accepted Trigger copy → staging page test. Do not call the live job done before that proof.

Deploy-on-merge: the changes under agents/tisan redeploy the Tisan room and its regional copies; Tank runtime changes deploy with the main stack. No live deployment or production mutation was performed here. The founder merges.
