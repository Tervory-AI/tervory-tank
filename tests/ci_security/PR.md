# PR #374: free CLI security checks with a working Semgrep scan

Branch: `codex/ci-security`. Keep this PR draft. The founder merges.

## Latest review: Semgrep report startup failure fixed

Code commit `27496125e8f594626461cda5becbf966e7190801` fixes the runner failure. Latest main `678d47e` was merged first. **The GitHub security job now passes**, including Gitleaks, Semgrep, OSV, and report upload: [run 40693368869, security job 122833615354](https://github.com/Tervory-AI/tervory-tank/actions/runs/40693368869/job/122833615354). [Recorded step conclusions](evidence/runner-github-security.json).

### What was missing and why

The missing file was `/home/runner/work/_temp/security-uscc8m4h/semgrep.json`, the expected report. The launcher and baseline checkout were present. The diagnostic commit distinguishes a missing executable (`SemgrepExecutableMissing`) from a missing report (`SemgrepReportMissingExit<code>`) and includes only the path and error type. The [diagnostic run](https://github.com/Tervory-AI/tervory-tank/actions/runs/40692303376/job/122829962660) reported `SemgrepReportMissingExit2`; [safe metadata](evidence/runner-before-diagnostic.json).

Pinned Semgrep **1.182.1** rejects `--config auto --metrics off` before scanning or writing JSON. A local run of that exact pinned CLI reproduced exit **2**, no report, and its fixed diagnostic: `Cannot create auto config when metrics are off. Please allow metrics or run with a specific config.` [Reproduction result](evidence/runner-startup-reproduction.json). This command-line rejection, before configuration download, caused the failure; the earlier local network-access limitation did not establish its cause.

The fix uses **`--config auto --metrics auto`**, which the pinned CLI supports. A regression assertion checks these flags. No rules, baselines, tool versions, finding thresholds, or application code changed. Missing reports still fail closed; new HIGH / ERROR / CRITICAL findings still fail and produce metadata-only annotations.

### How it was tested

- Local policy/native Gitleaks suite: **26 tests passed** in 38.182s. [Log](evidence/runner-unit-tests.txt).
- Policy suite plus the existing secret tests: **28 passed, 7 subtests passed** in 85.70s. [Log](evidence/runner-pytest.txt).
- Exact CI lint command: `/tmp/ci-security-tools/test-venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'` — **All checks passed!**
- Focused lint: `/tmp/ci-security-tools/test-venv/bin/ruff check .github/scripts/security_scan.py tests/ci_security --select E9,F` — **All checks passed!**
- `git diff --check` passed.
- GitHub on `2749612`: install, policy tests, **Gitleaks, Semgrep, OSV**, report upload, and job completion all **success**. The startup-error annotation is gone. This is the security job's result, not a claim that every unrelated PR check passed.

All work ran in the cloud. Git was used to push; GitHub results were read from ordinary HTML pages without the GitHub API. The uploaded artifact has not been downloaded locally, so no unobserved per-finding count is claimed. The PR remains draft for Claude's review.

## Previous review: readable Semgrep diagnostics

Code commit `9f49cf4aae3b2c3db752b7889a222c426118c284` implements the previous annotation review. Main `4bda46b` was merged first. Claude can classify any findings from their annotations; this change does not assume that any finding is a false positive.

- [.github/scripts/security_scan.py:29](../../.github/scripts/security_scan.py#L29): each finding emits `::error file=PATH,line=N::RULE_ID severity`. Only the rule ID, severity, file and line are emitted. Workflow-command characters in metadata are escaped.
- [.github/scripts/security_scan.py:43](../../.github/scripts/security_scan.py#L43): each reported scan error emits one `::notice` containing only its type and available path. Structured error payloads, source tokens, messages and matched values are never emitted or retained in the sanitized report.
- [.github/scripts/security_scan.py:82](../../.github/scripts/security_scan.py#L82): non-fatal partial parsing, HTML/fixture syntax errors and per-file timeouts become notices without failing the scan. Results include `error_count`, `non_fatal_error_count`, `fatal_error_count`, and sanitized error metadata.
- Fatal-level errors, the pinned CLI's `Fatal error` type, and rule-download failures still mark the scan incomplete. The JSON report is read before deciding the result, including on CLI exit 3 (target parsing errors). Missing/malformed reports and fatal process/configuration exits still block.
- The finding gate is unchanged: new **HIGH / ERROR / CRITICAL** findings fail. Other severities are annotated as requested but do not change the exit status.

Exact local validation commands on the cloud machine:

```bash
PATH=/tmp/ci-security-tools/bin:$PATH python3 -m unittest discover -s tests/ci_security -p test_security.py -v
# 25 tests passed. evidence/annotations-unit-tests.txt
PATH=/tmp/ci-security-tools/bin:$PATH /tmp/ci-security-tools/test-venv/bin/python -m pytest -q tests/ci_security/test_security.py tests/test_secrets.py
# 27 passed, 7 subtests passed in 34.04s. evidence/annotations-pytest.txt
/tmp/ci-security-tools/test-venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
# All checks passed!
/tmp/ci-security-tools/test-venv/bin/ruff check .github/scripts/security_scan.py tests/ci_security --select E9,F
# All checks passed!
```

Tests cover annotation escaping and redaction, fatal and download failures, notices for non-fatal errors, missing reports, and high findings alongside non-fatal notices. Tests capture their synthetic annotations, so they do not pollute GitHub's real scan annotations. No Semgrep rules, baselines, tool versions or application code were changed for this review.

To prove this change, open **PR #374 → Checks → ci → security → annotations** on the new head. Each real finding identifies its rule, severity and source location; each scan-error notice identifies only its type and path. Download the security artifact for the non-fatal/fatal counts. Claude reads and triages those annotations. These validation results predate the startup fix and passing GitHub run recorded above.

## Previous review and historical evidence

Claude reviewed the historical Gitleaks findings as false positives. The requested exceptions are implemented; the local **weekly whole-history Gitleaks scan passes with zero findings**. GitHub run [40675008503](https://github.com/Tervory-AI/tervory-tank/actions/runs/40675008503), at code commit `935b3d0`, reports **Gitleaks success, OSV success, Semgrep failure**. This is not an all-green CI claim.

## Review changes (file and line)

| File | Result |
| --- | --- |
| [.gitleaksignore:1](../../.gitleaksignore#L1) | 41 unique native Gitleaks fingerprints cover all 43 reviewed findings. A one-line comment explains each group: dummy Clerk publishable test keys, the dummy Stripe test key, Figma file identifiers, and public page tokens in saved HTML fixtures. Two pairs of Figma findings share a native fingerprint. No values or path-wide exemptions are included. |
| [.gitleaks.toml:3](../../.gitleaks.toml#L3) | Keep all built-in rules and add one anchored `regexTarget = "secret"` allowance for the exact existing Clerk publishable CI dummy. Other values with the same prefix remain detectable. |
| [.github/scripts/security_scan.py:63](../../.github/scripts/security_scan.py#L63) | Use the reviewed repository config and fingerprint file for both PR and weekly scans. Continue ignoring inline allow comments; every finding outside these explicit exceptions fails. |
| [tests/ci_security/test_security.py:142](test_security.py#L142) | Native Gitleaks tests prove an exact copy is allowed and two altered values still fail. Their reports and values are never printed. |
| [.github/workflows/ci.yml:34](../../.github/workflows/ci.yml#L34), [.github/workflows/security-weekly.yml:22](../../.github/workflows/security-weekly.yml#L22) | Install the pinned CLI before the policy tests, so the new tests exercise the real tool in CI too. |

The pinned scanner emitted no additional private-key fingerprint in this full-history scan, so no invented fingerprint or blanket private-key exemption was added. No app, page, dependency version or existing secret-test change is included. Latest main `89a7234` was merged into this branch before the fix.

## Local proof

The before scan returned 43 findings. After applying the reviewed config/fingerprints, the exact weekly command at `935b3d0` returned `gitleaks: clean`, exit **0**, findings **[]**. [Machine-readable proof](evidence/review-weekly-gitleaks.json).

```bash
PATH=/tmp/ci-security-tools/bin:$PATH python3 .github/scripts/security_scan.py gitleaks --output /tmp/ci-security-review/committed-weekly
# gitleaks: clean; exit 0; no --base, so this scans the whole HEAD history.

PATH=/tmp/ci-security-tools/bin:$PATH python3 -m unittest discover -s tests/ci_security -p test_security.py -v
# 18 tests passed, including three native Gitleaks allowlist checks.

PATH=/tmp/ci-security-tools/bin:$PATH /tmp/ci-security-tools/test-venv/bin/python -m pytest -q tests/ci_security/test_security.py tests/test_secrets.py
# 20 passed, 7 subtests passed in 41.23s.

/tmp/ci-security-tools/test-venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
# All checks passed!

/tmp/ci-security-tools/test-venv/bin/ruff check .github/scripts/security_scan.py tests/ci_security --select E9,F
# All checks passed!

/tmp/ci-security-tools/actionlint -color=false -shellcheck= .github/workflows/ci.yml .github/workflows/security-weekly.yml
# Exit 0; no diagnostics.
```

Logs: [native/policy tests](evidence/review-unit-tests.txt), [pytest](evidence/review-pytest.txt). Python 3.12.14; Gitleaks 8.30.1; pytest 9.1.1; pytest-asyncio 1.4.1; Ruff 0.17.2; actionlint 1.7.12. All work ran on the cloud machine.

## Historical GitHub proof from this PR

[Security job 122771060556](https://github.com/Tervory-AI/tervory-tank/actions/runs/40675008503/job/122771060556), commit `935b3d0`:

| Step | GitHub conclusion |
| --- | --- |
| Install pinned security CLIs | success |
| Test security gate policy | success |
| Gitleaks — PR commits or main push | success |
| Semgrep — new high findings | **failure** |
| OSV-Scanner — new vulnerable versions | success |
| Save security results | success |

[Recorded step metadata](evidence/review-github-security.json) was read from the normal GitHub HTML job page, **without the GitHub API**. The Semgrep annotation says `Process completed with exit code 1.` At that point the page required sign-in to view logs and the cause was unknown. The later diagnostic run and local pinned-CLI reproduction above identify the startup failure. The finding severity threshold remains unchanged; the latest section describes the requested non-fatal error policy. No screenshot or independent assessor approval is claimed.

The original local throwaway-commit proof remains in [gitleaks-fail.json](evidence/gitleaks-fail.json) and [gitleaks-pass.json](evidence/gitleaks-pass.json): the synthetic probe failed, then the scan passed after removing that commit. These are local CLI runs, not GitHub run links.

## What this PR installs

- Every PR, including docs-only changes, and every main push runs an independent security job. Gitleaks scans the commit range; Semgrep uses `--config auto --baseline-commit`; OSV-Scanner compares committed Python requirements/locks and npm locks with the base snapshot, including the package version in its comparison.
- Monday **06:00 UTC** runs all three tools without a baseline. Artifacts contain sanitized JSON and are retained for 14 days. High/critical findings block; any remaining Gitleaks finding blocks; unknown OSV severity and incomplete scans block for review.
- No paid service or new secret. Gitleaks and OSV binaries are pinned and checksum-verified; Semgrep is pinned by version and image digest; workflow actions use full commit SHAs. Semgrep uses `--metrics auto`, as required by `--config auto` in the pinned CLI.
- `tests/test_secrets.py` remains unchanged. It can be removed after Gitleaks has run clean for **two weeks**; that observation period has not yet been established.

## Decisions I made

- Keep every historical exception tied to its native fingerprint. Only the exact reviewed Clerk dummy receives an allowance for future copies. No broad key-prefix, file, fixture-directory, Stripe or private-key exemption was added.
- Deduplicate the two repeated native fingerprints; all 43 reviewed findings remain covered by 41 entries.
- Keep all three scanners independent and save reports on failure. Keep Semgrep's high-severity and incomplete-scan gates intact and report the actual GitHub result.
- Use supported `--metrics auto` with the required `--config auto`; changing the rule configuration would change the requested scan coverage. Distinguish missing launchers from missing reports without printing process output.
- Retain the earlier redacted evidence as historical evidence. Write review evidence to separate files so the initial failure is not presented as a current failure.

## Exactly what to open and click

1. Open [PR #374](https://github.com/Tervory-AI/tervory-tank/pull/374) → **Checks → ci → security**. For the tested code commit `2749612`, open [security job 122833615354](https://github.com/Tervory-AI/tervory-tank/actions/runs/40693368869/job/122833615354): **Gitleaks**, **Semgrep**, and **OSV-Scanner** each show success. Compare the [earlier diagnostic job](https://github.com/Tervory-AI/tervory-tank/actions/runs/40692303376/job/122829962660) and its `SemgrepReportMissingExit2` notice.
2. Open [run 40693368869](https://github.com/Tervory-AI/tervory-tank/actions/runs/40693368869) → **Artifacts → security-40693368869-1** to download the sanitized JSON. Inspect `semgrep.json` for finding metadata and fatal/non-fatal error counts. Any future finding annotations contain only rule, severity, path and line; scan-error notices contain only type and path.
3. For historical whole-history local proof, open [review-weekly-gitleaks.json](evidence/review-weekly-gitleaks.json): `base` is null, `result` is clean, `exit_code` is 0, and `findings` is empty.
4. After the founder merges, open **Actions → security-weekly → the Monday 06:00 UTC run → Artifacts** and download the weekly reports. This PR remains draft for Claude's review. No merge is requested.
