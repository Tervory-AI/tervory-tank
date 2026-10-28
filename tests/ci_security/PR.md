# PR #374: free CLI security checks and reviewed Gitleaks exceptions

Branch: `codex/ci-security`. Keep this PR draft. The founder merges.

Claude reviewed the historical Gitleaks findings as false positives. The requested exceptions are implemented; the local **weekly whole-history Gitleaks scan passes with zero findings**. GitHub run [40675008503](https://github.com/Tervory-AI/tervory-tank/actions/runs/40675008503), at code commit `935b3d0`, reports **Gitleaks success, OSV success, Semgrep failure**. This is not an all-green CI claim.

## Review changes (file and line)

| File | Result |
| --- | --- |
| [.gitleaksignore:1](../../.gitleaksignore#L1) | 41 unique native Gitleaks fingerprints cover all 43 reviewed findings. A one-line comment explains each group: dummy Clerk publishable test keys, the dummy Stripe test key, Figma file identifiers, and public page tokens in saved HTML fixtures. Two pairs of Figma findings share a native fingerprint. No values or path-wide exemptions are included. |
| [.gitleaks.toml:3](../../.gitleaks.toml#L3) | Keep all built-in rules and add one anchored `regexTarget = "secret"` allowance for the exact existing Clerk publishable CI dummy. Other values with the same prefix remain detectable. |
| [.github/scripts/security_scan.py:29](../../.github/scripts/security_scan.py#L29) | Use the reviewed repository config and fingerprint file for both PR and weekly scans. Continue ignoring inline allow comments; every finding outside these explicit exceptions fails. |
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

## GitHub proof from this PR

[Security job 122771060556](https://github.com/Tervory-AI/tervory-tank/actions/runs/40675008503/job/122771060556), commit `935b3d0`:

| Step | GitHub conclusion |
| --- | --- |
| Install pinned security CLIs | success |
| Test security gate policy | success |
| Gitleaks — PR commits or main push | success |
| Semgrep — new high findings | **failure** |
| OSV-Scanner — new vulnerable versions | success |
| Save security results | success |

[Recorded step metadata](evidence/review-github-security.json) was read from the normal GitHub HTML job page, **without the GitHub API**. The Semgrep annotation says `Process completed with exit code 1.` The page requires sign-in to view logs, so whether this was a finding or an incomplete scan is not established here. Access to the signed-in log or downloaded security artifact is missing for that diagnosis. No Semgrep rule or failure threshold was weakened. No screenshot or independent assessor approval is claimed.

The original local throwaway-commit proof remains in [gitleaks-fail.json](evidence/gitleaks-fail.json) and [gitleaks-pass.json](evidence/gitleaks-pass.json): the synthetic probe failed, then the scan passed after removing that commit. These are local CLI runs, not GitHub run links.

## What this PR installs

- Every PR, including docs-only changes, and every main push runs an independent security job. Gitleaks scans the commit range; Semgrep uses `--config auto --baseline-commit`; OSV-Scanner compares committed Python requirements/locks and npm locks with the base snapshot, including the package version in its comparison.
- Monday **06:00 UTC** runs all three tools without a baseline. Artifacts contain sanitized JSON and are retained for 14 days. High/critical findings block; any remaining Gitleaks finding blocks; unknown OSV severity and incomplete scans block for review.
- No paid service or new secret. Gitleaks and OSV binaries are pinned and checksum-verified; Semgrep is pinned by version and image digest; workflow actions use full commit SHAs. Semgrep metrics are off.
- `tests/test_secrets.py` remains unchanged. It can be removed after Gitleaks has run clean for **two weeks**; that observation period has not yet been established.

## Decisions I made

- Keep every historical exception tied to its native fingerprint. Only the exact reviewed Clerk dummy receives an allowance for future copies. No broad key-prefix, file, fixture-directory, Stripe or private-key exemption was added.
- Deduplicate the two repeated native fingerprints; all 43 reviewed findings remain covered by 41 entries.
- Keep all three scanners independent and save reports on failure. Keep Semgrep's failing gate intact and report the actual GitHub result.
- Retain the earlier redacted evidence as historical evidence. Write review evidence to separate files so the initial failure is not presented as a current failure.

## Exactly what to open and click

1. Open [PR #374](https://github.com/Tervory-AI/tervory-tank/pull/374) → **Checks → ci → security**. Inspect the three scanner steps. For the reviewed code, the linked run above shows Gitleaks and OSV passing and Semgrep failing.
2. Open that run's **Artifacts → security-40675008503-1** and download the JSON. A signed-in reviewer can inspect the Semgrep status/report to identify the failure; the upload step passed.
3. For the whole-history local proof, open [review-weekly-gitleaks.json](evidence/review-weekly-gitleaks.json): `base` is null, `result` is clean, `exit_code` is 0, and `findings` is empty.
4. After the founder merges, open **Actions → security-weekly → the Monday 06:00 UTC run → Artifacts** and download the weekly reports. This PR remains draft while Semgrep fails. No merge is requested.
