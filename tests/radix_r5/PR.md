# Radix R5 — Checkov and client repository scans from /chats

An owned `/chats` upload can now be scanned by Radix's existing archive job after durable Confirm. `radix.repo.findings` reads that job for the caller's tenant and projects the approved Radix finding fields. The room adds offline Checkov checks alongside secrets, dependencies and static analysis.

Implementation and offline proof are complete on `codex/radix-r5-repo-scan`. **Founder browser acceptance and CI's full Tank job remain pending. This is not a DONE claim.** Claude opened [PR #605](https://github.com/Tervory-AI/tervory-tank/pull/605); the founder merges. No approval of `scan.iac`, deployment or production-data change was performed.

## Changes and review locations

| File and line | Final behavior |
| --- | --- |
| `agents/radix/Dockerfile:28`, `:54`, `:84` | Exact Checkov 3.3.21 pin in `/opt/checkov`, separate from chassis and Semgrep; `CHECKOV_BIN` points to it. |
| `agents/radix/scanlib/iac.py:23`, `:54`, `:98` | Bounded Checkov execution, JSON parsing, skipped folders, offline proxy environment and eval-file intake. Each failed check becomes one `scan.iac` finding, with its own rule ID and check text; severity is always `unknown`. |
| `agents/radix/scanlib/orchestrate.py:48`, `:79`, `:115` | Collects IaC, preserves `tool_status` and `scan_complete`, redacts with existing secret handling and stores via existing `scan_job`. Missing/failed/timed-out Checkov is `not run`; an empty partial scan does not say "No findings". Only critical findings from other tools can block a build. Scanner work runs off the event loop so job reads remain responsive. |
| `agents/radix/app.py:61`, `:87`, `:95` | Archive jobs get 360 seconds for the four bounded scanners. Room-key-only `/evals/run` allows exactly `scan.iac@1.0.0`, executes code in a worker thread and does not approve a skill. |
| `tank/main.py:3262`, `:3292` | Extends the existing Tisan room-eval path to `scan.iac`, selecting Radix and existing `TANK_KEY_RADIX`. Other eval/lifecycle behavior is retained. |
| `tank/radix_repo.py:8` | Requires the existing durable confirmation context, reads the upload by attachment ID + tenant + user, retains 5 MiB cap and the exact Ghost archive signature check, then calls Radix `/jobs` with the caller's tenant and attachment name as `ref`. |
| `tank/radix_repo.py:39` | Reads `/jobs/{id}` with the caller's tenant; checks job tenant, job ID, kind and completed result ownership again. Foreign or malformed results are refused. Queued/done job states map to the existing pending/complete presentation values. Pending/failed jobs do not fabricate findings or expose exception text. |
| `tank/radix_repo.py:70`, `:89` | Uses existing `_record_local` for genuine zero-dollar `model=code`, `agent=radix` receipts. Existing identity, squad authorization and Confirm remain authoritative. No new table or new receipt implementation. |
| `tank/radix_repo.py:108` | Explicit `radix.repo.scan` and `radix.repo.findings <scan_id>` commands bind metadata in code, without model calls. An upload-only scan command requires exactly one UploadRef in that owned turn. |
| `tank/command.py:42`, `:476`, `:1223`, `:1368`, `:1576`, `:1953` | Adds both tools to client catalogue and adapters; binds identity through existing actor headers; adds scan to confirmed dispatch; routes explicit commands through code-only planning; mounts the narrow router. Existing tool lists are retained. |
| `workspace/app/chats/radix-presentation.ts:2`, `:10`, `:15` | Adds both names next to the three existing tools; reuses existing scan/findings projection, states and severity display. Repository critical counts are excluded from the view. |
| `workspace/app/chats/presentation.ts:40` | Suppresses generic repo-result details so summaries and operational fields cannot appear outside the approved Radix projection. No component markup, CSS, static assets or visible copy was added. |
| `tank/skills/scan.iac/1.0.0/skill.yaml:1`, `run.py:1`, `engine.py:1`, `CHANGELOG.md:1` | Candidate package with threshold 1.0. Engine is a byte copy of room scanner. Existing skill versions are untouched. |
| `tank/skills/scan.iac/1.0.0/evals/cases.jsonl:1` | Five distinct cases with exact rule-set expectations captured from the real pinned Checkov in a network-disabled Radix container, including refusal evidence. |
| `tank/skills/scan.iac/1.0.0/evals/fixtures/terraform/open.tf:1`, `fixtures/kubernetes/privileged-pod.fixture:1`, `fixtures/docker/root-container.fixture:1`, `fixtures/clean/Dockerfile:1`, `fixtures/clean/main.tf:1` | Actual fixture files; tests enforce equality with inline eval-file inputs. Fixtures are never displayed on a live product screen. |
| `tests/test_rx1_scans.py:98`, `:118` | Adds byte-identity pair and Checkov image pin assertions. |
| `tests/test_radix_iac.py:1` | Fake Checkov subprocess contract, own rule text, unknown severity, skipped paths, unavailable/failed/timeout evidence, non-blocking IaC, fixture equality, unsafe-input refusal and room auth/version limits. |
| `tests/test_command_radix_repo.py:1` | Real disposable-Postgres Command/room tests: Confirm/no repeat, tar and zip, owned uploads, caller tenant, redaction, code receipts, malformed responses and actual persisted cross-tenant job refusal. Also verifies Tank's room-eval executor. |
| `tests/radix_chat_presentation.cjs:33`, `tests/radix_chat_browser.cjs:1` | Both account modes, repo state projection, unknown severity, >5 findings, hidden fields and actual component rendering with clipboard/escaping/responsive checks. |
| `tests/radix_r5/room_eval_proof.py:1`, `archive_image_proof.py:1` | Reproducible real-image scripts: actual authenticated room eval route and four real scanners with planted fake-key redaction, both under `--network none`. |

No changes to `passive_*.py` or `tank/schema.sql`. No new table, paid service, approval action or model call was introduced. Runtime uses existing room-key settings by name only; no real setting value was inspected or written.

## Approved presentation reuse and fields kept out of the view

Founder follow-up explicitly authorizes reuse of Figma `205:6112`: durable Confirm, pending `206:711`, results `205:6129` / `205:6179`, failed `206:715` and zero findings `206:720`. The existing `RadixCard` and styles are unchanged. Design context/screenshots were read for pending and both results frames. Existing fallback wording remains unchanged; no new text, button, empty state or error wording was added to the view.

The adapter returns `scan_id`, normalized `status`, and, on completion, the existing finding fields: `rule`, `severity`, `tool`, `file`, `line`, optional `explanation`, and `remediation` from the scanner's `fix`. No explanation or fix is invented. For Checkov, `fix` is its own `check_name` text. Severity `unknown` passes through the ordinary severity value.

Every returned field deliberately kept in tool data and outside the Radix view:

- `summary`
- `critical`
- `tools`
- `tool_status`
- `scan_complete`
- `ledger_id`
- `cost_usd` (the existing separate receipt still shows the measured zero cost)

The attachment ID remains an argument, not a new visible field. Tenant/user IDs, source archive and raw room errors never enter the projection.

## Pin, licence and image size

Checkov **3.3.21**, **Apache-2.0**. Installed metadata prints `3.3.21` and `Apache License 2.0`; see [upstream licence at this pin](https://github.com/bridgecrewio/checkov/blob/3.3.21/LICENSE). No platform/API key is used to obtain severity.

| Local image | Image ID | Docker `.Size` bytes |
| --- | --- | ---: |
| Before R5 (`radix-r5:before`) | `sha256:e570a76c7905e052d326e354b1a8ce20bcee1a7a0de3117635a95b401c06a309` | 2,031,659,694 |
| Final (`radix-r5:final`) | `sha256:03da7febe915049df2c17aedf80822f7b5c6b7c66e65ccf9602450514232fe95` | 2,391,039,726 |

Increase: **359,380,032 bytes**. These are Docker image sizes, not compressed registry sizes. Both images built successfully from the repository Dockerfile. Final image hashes of app, IaC scanner and orchestrator match this branch's source. Builds may download tools/advisories; all runtime proof containers use `--network none`.

## Validation

Commands and complete captured outputs, including initial failures, are in [PROOF.txt](PROOF.txt). This file's final test result is **352 passed, 1 skipped, 437 subtests passed** for the named Radix suites plus Command regressions. Skip: `tests/test_radix_osv_real.py` has no baked real OSV SQLite on the host; the real archive image proof uses the image's baked OSV database.

- Real Radix room evals: **5/5, score 1.0, eligible true, $0, no model calls**. Real Terraform rules include `CKV_AWS_24`, privileged pod `CKV_K8S_16`, root Dockerfile `CKV_DOCKER_8`; all expected rule sets come from actual output, not guesses.
- Real network-disabled archive image: **8 findings**, all four scanner tool IDs, IaC severity `unknown`, `leaked=false`; planted fake-key value absent from serialized result.
- Projection checks, TypeScript check, Ruff and secret/projection pytest guards passed.
- Local browser harness passed clipboard success/failure, eighth-finding expansion, hostile text escaping, repo unknown-severity projection and no horizontal overflow at 320/375/768/1440 pixels.
- Initial two summary-contract test failures, one isolated-module Pydantic failure, missing test-import configuration and unused-import lint findings were corrected. Captured initial pytest failures are retained in proof. No unrelated origin/main failure was changed or suppressed.

CI's `tank` job is the **full-suite test of record**, per the founder's follow-up. The initial report above predates PR #605; current review validation and hosted results are recorded below. No local full-Tank run is substituted for CI.

## Screenshots and remaining founder acceptance

**Founder test screenshots: pending. The founder has not yet run this branch in his own browser.**

Local-only fixture harness screenshots: [375px](local-browser-375.png), [1440px](local-browser-1440.png). These prove the existing component/projection behavior under controlled test data; they are not a live scan or founder acceptance.

After CI/review and the founder's merge:

1. In `/chats`, run the existing `skala.evals` tool for `scan.iac` version `1.0.0`; capture the pass in the founder's browser. Approval remains the founder's action in Skala.
2. Upload one small tar/tar.gz/zip with Terraform, a planted fake key, vulnerable dependency and injection pattern. Send `radix.repo.scan` with that one upload attached. Confirm the existing card; the returned job ID appears as Scan ID in the approved pending state.
3. Send `radix.repo.findings <scan_id>` and use the existing confirmation flow. On completion, verify all four tools, redaction and IaC `unknown` severity in the approved Radix results card.
4. Under another tenant, read that ID and verify refusal. Capture the founder's screenshots and attach them to the PR.

No production SQL, live scan or deployment has occurred in this task. The separate review thread's findings must be fixed on this same PR. R4's changes must be retained when merging any newer `origin/main`; each file's publication fetched and merged main before a serialized branch push. The builder never pushed to main and does not open or merge the PR.


## #605 review fixes

The initial implementation/proof above is retained as history. Review fixes are on this same branch and PR after merging `origin/main`; the merge retains both the Radix repository tools and incoming Zenas tools.

- `tank/radix_repo.py:8` and the scan route: attachment ownership is checked before receipt creation. Both other-user and other-tenant tests upload a valid tar and a valid zip, assert the confirmed card fails with the existing dispatch response `404 {"detail":"Attachment not found"}`, verify `call_room` is never awaited, and verify no ledger row or snapshot receipt is written. The same-user non-archive case separately asserts the existing 422 archive-type refusal and its code receipt.
- `workspace/app/chats/radix-presentation.ts:20`: an empty repository result with `scan_complete=false` projects the existing failed state (206:715). A completed zero-finding result still uses the approved zero-findings state. Partial scans with findings keep showing the findings. No wording or component markup changed. Unit and browser tests cover both empty states and retention of partial findings.
- CI's older security job identified intentionally unsafe R5 fixture files as deployable Docker/Kubernetes source. Those stored data files now use `root-container.fixture` and `privileged-pod.fixture`; their actual eval filenames and bytes, expected Checkov rule sets and engine bytes are unchanged. No security policy or rule was disabled.

Local review validation: **22 Command repo tests passed**, **16 IaC/secret/projection guards passed**, projection and browser checks passed, TypeScript and Ruff passed, and real network-disabled Radix room evals remained **5/5, score 1.0, eligible true, $0**. Exact commands and outputs: [REVIEW-PROOF.txt](REVIEW-PROOF.txt).

The first full CI run at `790a8214` reported three R5-specific harness failures (old three-tool expectation, attempting room-only IaC evals in Tank, and a cached Tiger `gold_sources` import). A fresh main archive passed the unchanged comparison tests (**31 passed**); the affected tests after correction passed **44 tests**. The generic harness now treats `scan.iac` like Tisan's room-only packages; actual Checkov evals remain in Radix at threshold 1.0. The room test explicitly reproduces the foreign cached-module condition. No unrelated baseline failure was changed. Evidence and the failed run link are retained in [REVIEW-PROOF.txt](REVIEW-PROOF.txt).

### Hosted full-suite result

CI's `tank` job is the full-suite test of record. **SUCCESS** for final code/test head `9bfa0ef579eda1f0f27366dd10dba2d2fcfae35f`: [run 41650099511, Tank job 125966380828](https://github.com/Tervory-AI/tervory-tank/actions/runs/41650099511/job/125966380828).

Exact hosted command: `python3 .github/scripts/offline_suite.py`, exit 0. Its three runs reported:

- Main group: **6,788 passed, 42 skipped, 1,804 subtests passed** in 1039.90 seconds.
- `tests/tiger_g5`: **46 passed** in 14.84 seconds.
- `tests/zenas_regulation_alerts`: **40 passed** in 6.13 seconds.

Security, Command acceptance and Workspace also passed for that head. The earlier three-failure run and fixes remain documented above; no unrelated baseline failure was changed.

**Final report-head CI result:** [the `tank` job in #605's current-head checks](https://github.com/Tervory-AI/tervory-tank/pull/605/checks). That link tracks the final report commit as well as its code/test checkpoint; the builder waits for its completed result before handoff. The source checkpoint and immutable completed-job link above are retained so documentation-only publication cannot obscure which code was tested.

The founder's own `skala.evals` run, upload/Confirm/findings test and screenshots follow **after merge**. No founder acceptance or production change is claimed. The builder does not merge.
