# 1.0.0

Candidate only; founder approval in Skala is required. Builds validated section plans in the existing room with accepted tenant-bound Trigger copy and supplied media. No template, visual design or publishing changes.

## Review handoff (1 November 2026)

Implementation locations:
- `agents/tisan/builder.py:19`: reuse scaffold functions; `:33`: compile the actual manifest's schema constraints with the existing Pydantic engine (unknown keywords fail closed); `:94`: validate plans; `:136`: Tank planning and one validation retry; `:159`: site/page/array slots and purposes; `:171`: tenant/write-bound accepted copy; `:198`: assemble/check/archive; `:263`: existing ready event.
- `agents/tisan/app.py:100`: build handler and ten-minute timeout; `:137`: build eval selection.
- `agents/tisan/Dockerfile:45`: builder.py added to the existing COPY line only.
- `tank/command.py:45`: founder-only tool; `:907`: typed input; `:1031`: existing Confirm/Skala adapter.
- `tank/main.py:3249` and `:3276`: existing room eval hookup includes the new skill.
- `tank/schema.sql:2257`: one additive `tisan.plan` policy, matching trigger.write's specified rung 1/luna/tenant cache seed, with ON CONFLICT DO NOTHING.
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

## PR #571 review fixes

All four review findings addressed on the same branch, with normal pushes and no reset or merge:
- `builder.accepted_copy` now sends the actual #567 endpoint's required `tenant_id` query as well as the tenant/region/key headers. A regression test mounts #567's actual router with ASGI: omission yields 422, the builder read succeeds, a foreign tenant yields 404, and wrong region/header/key are refused. Only database rows are doubled.
- The scaffold call is given only home/contact/privacy names. It no longer generates static custom or about routes that would shadow #570's content catch-all. The complete plan still goes to `content/site.json`. Contact, its existing API and privacy are retained when planned. Archive and real production-server tests cover support/about routes, accepted page titles and stored accepted section props.
- The additive `tisan.plan` seed is before BEGIN GENERATED AGENT MEMORY. The actual `hermes.record_schema.update_files` roundtrip is byte-identical and retains the policy; the generated END marker is at EOF.
- Removed the unused `sys` import from `tests/test_tisan_builder.py` that failed CI Ruff.

Dependency sources used for the interface test (isolated under this checkout's .git, not merged or edited): #567 head `7187e816bad70ddb82abd81933ab297091ade3b5`; #570 head `1b0b64d29ae2c27f384f3d428288b3f371722ead`. The test uses the real manifest, route and template, not a fixture copy. The ASGI test automatically uses the repository route after #567 merges; before then `TISAN_TRIGGER_ROUTES` selects its actual source. The real build similarly selects #570 through `TISAN_TEMPLATE` until it merges.

Exact final focused command:

```sh
TISAN_TRIGGER_ROUTES=/workspace/codex-tisan-builder/.git/tisan-integration/tank/trigger_routes.py PYTHONPATH=tank /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q tests/test_command.py::test_plans_are_bounded_and_cannot_supply_authority tests/test_command.py::test_adapters_force_identity_and_do_not_accept_paid_route_overrides tests/test_command.py::test_scan_adapter_preserves_packaged_skill_input tests/test_tisan_builder.py tests/test_tisan_builder_adapter.py tests/test_tisan_builder_interfaces.py tests/test_tisan_scaffold.py
```

Result: **51 passed, 2 skipped, 2 warnings in 2.13s**. Both skipped tests require explicit real npm build execution; the interface/build test was run separately below. Warnings are the same Pydantic field-shadowing warnings recorded above.

```sh
TMPDIR=/workspace/codex-tisan-builder/.git/builder-tmp TISAN_TRIGGER_ROUTES=/workspace/codex-tisan-builder/.git/tisan-integration/tank/trigger_routes.py TISAN_TEMPLATE=/workspace/codex-tisan-builder/.git/tisan-integration/agents/tisan/templates/next-site TISAN_RUN_BUILD=1 TISAN_NPM_OFFLINE=1 TISAN_NPM_CACHE=/home/ammosync/.npm PYTHONPATH=tank /home/ammosync/trigger-crm-venv312/bin/python -m pytest -q -s tests/test_tisan_builder_interfaces.py
```

Result: **3 passed, 2 warnings in 121.11s**. Actual Trigger ASGI copy reads supplied all text; the original build and unchanged extracted archive each passed offline npm ci, lint, build and test. The production server returned support/about with their accepted title metadata (200), contact/privacy (200), the existing contact POST response (202, `{"ok":true}`), and an unplanned route (404). Generated archive: `.git/builder-tmp/pytest-of-ammosync/pytest-1/test_built_custom_route_uses_a0/data/builds/11111111-1111-4111-8111-111111111111/integration-build/1.tar.gz`.

```sh
/home/ammosync/trigger-crm-venv312/bin/python -m ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
git diff --check
```

Results: **All checks passed!**; diff check clean.

This proves routing/content plumbing, not approved section visuals: #570's section components still await approved Figma and intentionally render nothing. No #570 source was changed here. Founder staging acceptance/screenshots are still pending, and CI for the new pushed head must be green before any merge. PR #571 remains unmerged.
