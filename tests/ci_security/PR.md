# Free CLI security checks on every PR and weekly

Draft handoff for Claude. Branch: `codex/ci-security`.
Started from main `4e74b4269fd91220a52970bd73cee03a3d3b89ba`; merged newer main `a99f3cb0662516c8fe1b3f27d5b5dcbb90e94fa0` without conflicts. Final code was tested at `1acfd7ccac0bd98284471d4ca50583ddce155422`; the following commit adds only this description and sanitized evidence.

**The local Gitleaks failure/pass proof is recorded below. Full GitHub job proof and screenshots remain pending.** Feature-branch pushes do not trigger the requested PR/main workflow, and Claude has not opened this task's PR. No GitHub API was used and no PR was opened by this builder. Local Semgrep/OSV live scans could not complete because this cloud environment denies their upstream hosts.

## What changed (file and line)

| File | Change |
| --- | --- |
| [.github/workflows/ci.yml:4](../../.github/workflows/ci.yml#L4) | Remove workflow-level docs filters, so every PR and main push runs security. Existing path selection still controls build jobs. |
| [.github/workflows/ci.yml:22](../../.github/workflows/ci.yml#L22) | Independent `security` job: policy tests, direct Gitleaks CLI, Semgrep CLI, OSV-Scanner CLI, and downloadable sanitized JSON, including when a scan fails. |
| [.github/workflows/ci.yml:177](../../.github/workflows/ci.yml#L177) | The existing `tests/test_secrets.py` / Tank boot command is retained unchanged. All action references in this workflow are now full commit SHAs. |
| [.github/workflows/security-weekly.yml:3](../../.github/workflows/security-weekly.yml#L3) | Monday 06:00 UTC on the default branch: the same three tools scan without a baseline; reports retained for 14 days. |
| [.github/scripts/install-security-tools.sh:1](../../.github/scripts/install-security-tools.sh#L1) | Verify release checksums for Gitleaks and OSV-Scanner; run the Semgrep CLI from its exact container digest. No Gitleaks Action, paid platform, or new secret. |
| [.github/scripts/security_scan.py:29](../../.github/scripts/security_scan.py#L29) | Gitleaks scans `base..HEAD` for PR/main pushes and all HEAD history weekly. No findings baseline or repository allow comments suppress results. |
| [.github/scripts/security_scan.py:47](../../.github/scripts/security_scan.py#L47) | Semgrep uses `--config auto`, with `--baseline-commit` on PR/main runs. New high/critical findings block. Weekly checks have no baseline. Metrics are off. |
| [.github/scripts/security_scan.py:67](../../.github/scripts/security_scan.py#L67) | Scan every committed `*requirements*.txt`, `*requirements*.lock`, and `package-lock.json`, including nested files. Compare OSV output by lockfile, ecosystem, package, version and advisory. A different vulnerable version fails even when the advisory ID is unchanged. |
| [.github/scripts/security_scan.py:135](../../.github/scripts/security_scan.py#L135) | Incomplete scans fail. Artifacts exclude source snippets, matches, secret values, messages and author identities. |
| [tests/ci_security/test_security.py:26](test_security.py#L26) | Offline regression tests for version comparisons, severity thresholds, scanner errors, commit ranges and report redaction. |

No app, page, dependency manifest, lockfile, or existing test was changed. `tests/test_secrets.py` can be removed once Gitleaks has run clean for **two weeks**; that period has not been established here.

## Pins

| Tool | Exact pin |
| --- | --- |
| Gitleaks | `8.30.1`; release archive SHA256 `551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb` |
| Semgrep CLI | `1.182.1`; Linux amd64 image digest `sha256:c8f333ab0ad103d2bcd3b55cbeabcfc556bfeaa7446ba18594a4320f3807ffc9` |
| OSV-Scanner | `2.7.0`; binary SHA256 `160c6253e2922e9e0a6a9771c5c4c40a4b3c6090b34a3cdd5e80c96cc2e4218b` |
| Security job Python | `3.12.14` |
| checkout | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| setup-python | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` |
| setup-node (existing jobs) | `949feb2413d6458794dcd2491c4babbbce0c15c1` |
| cache (existing jobs) | `55cc8345863c7cc4c66a329aec7e433d2d1c52a9` |
| upload-artifact | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` |

The requested `--config auto` and live OSV database remain current upstream data; their contents are not frozen with the CLI versions.

## Exact validation commands and results

All commands ran on the cloud machine in `/workspace/tervory-ci-security`. Lint/workflow/shell results: [validation.txt](evidence/validation.txt).

```bash
python3 -m unittest discover -s tests/ci_security -p test_security.py -v
# 15 tests passed. evidence/unit-tests.txt

/tmp/ci-security-tools/test-venv/bin/python -m pytest -q tests/ci_security/test_security.py tests/test_secrets.py
# 17 passed, 7 subtests passed in 21.74s. evidence/pytest.txt

/tmp/ci-security-tools/test-venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
# All checks passed! Ruff 0.17.2, exactly main's pin.

/tmp/ci-security-tools/test-venv/bin/ruff check .github/scripts/security_scan.py tests/ci_security --select E9,F
# All checks passed!

/tmp/ci-security-tools/actionlint -color=false -shellcheck= .github/workflows/ci.yml .github/workflows/security-weekly.yml
# Exit 0; no diagnostics. actionlint 1.7.12; shellcheck integration disabled.

bash -n .github/scripts/install-security-tools.sh
# Exit 0.

RUNNER_TEMP=/tmp/ci-security-tools/install-test GITHUB_PATH=/tmp/ci-security-tools/github-path bash .github/scripts/install-security-tools.sh
# Exit 0; both downloaded release checksums OK.
```

Main's pytest 9.1.1, pytest-asyncio 1.4.1 and Ruff 0.17.2 were installed in the temporary test environment using a generated hash lock and `uv pip install --require-hashes`. An initial lint attempt with an older pre-existing Ruff 0.11.12 reported five F811 diagnostics in untouched main tests; the exact current pin passes. No tests were edited to suppress them.

### Throwaway commit: actual local failure and pass

The deliberately fake string was never issued by a provider, used for authentication, printed, or retained in this branch's final tree/history. The probe commit was pushed with git, tested, then removed with a lease guarded update of this branch only. A deletion commit would leave it in Gitleaks' history scan.

| Local run | Commit | Exit | Finding count | Evidence |
| --- | --- | --- | --- | --- |
| Synthetic probe pushed | `1efaded52a10d721bd80a8a5a1bbe594a430df75` | 1 | 1 (`github-pat`) | [gitleaks-fail.json](evidence/gitleaks-fail.json) |
| Probe commit removed | `83853ba8742f0db4cf7f6d4a20eb408176e4dc6d` | 0 | 0 | [gitleaks-pass.json](evidence/gitleaks-pass.json) |
| Final code after main merge | `1acfd7ccac0bd98284471d4ca50583ddce155422` | 0 | 0 | [gitleaks-final-pass.json](evidence/gitleaks-final-pass.json) |

Exact commands for the failure and immediate pass (same command on both heads):

```bash
PATH=/tmp/ci-security-tools/bin:$PATH python3 .github/scripts/security_scan.py gitleaks --base 4e74b42 --output /tmp/ci-security-tools/proof/fail
# gitleaks: findings; exit 1
PATH=/tmp/ci-security-tools/bin:$PATH python3 .github/scripts/security_scan.py gitleaks --base 4e74b42 --output /tmp/ci-security-tools/proof/pass
# gitleaks: clean; exit 0
PATH=/tmp/ci-security-tools/bin:$PATH python3 .github/scripts/security_scan.py gitleaks --base a99f3cb --output /tmp/ci-security-tools/proof/final-pass
# gitleaks: clean; exit 0
```

These are the workflow's actual Gitleaks command path and pinned CLI, **not GitHub Actions runs**. There are no run links or screenshots to claim. Full-job fail/pass evidence still needs the PR and working upstream access.

### Live scan limits and weekly history

```bash
PATH=/tmp/ci-security-tools/venv/bin:$PATH SEMGREP_SETTINGS_FILE=/tmp/ci-security-tools/semgrep-settings.yml SEMGREP_LOG_FILE=/tmp/ci-security-tools/semgrep.log SEMGREP_ENABLE_VERSION_CHECK=0 python3 .github/scripts/security_scan.py semgrep --base 4e74b42 --output /tmp/ci-security-tools/proof/live
# semgrep: incomplete; exit 1
PATH=/tmp/ci-security-tools:$PATH python3 .github/scripts/security_scan.py osv --base 4e74b42 --output /tmp/ci-security-tools/proof/live
# osv: incomplete; exit 1
PATH=/tmp/ci-security-tools/bin:$PATH python3 .github/scripts/security_scan.py gitleaks --output /tmp/ci-security-tools/proof/weekly
# gitleaks: findings; exit 1; 43 historical findings
```

- `semgrep.dev` and `api.osv.dev` each returned proxy diagnostic `Tunnel connection failed: 403 Forbidden`. Reports: [Semgrep incomplete](evidence/semgrep-incomplete.json), [OSV incomplete](evidence/osv-incomplete.json). The native Semgrep 1.182.1 CLI was used for this local attempt; its CI container execution has not been verified here. No alternate endpoint, disabled TLS check or offline substitute was used to claim a pass.
- Weekly Gitleaks was run at `83853ba`; all 43 finding commits are ancestors of starting main `4e74b42`, verified with `git merge-base --is-ancestor`. [Summary](evidence/weekly-summary.json). They are findings, not a claim that all are active credentials. They have not been inspected, suppressed, baselined, or changed. The full-history job will require their review.
- No application build was run: this branch changes CI only. No GitHub job result, founder screenshot or independent assessor approval is claimed.

## Decisions I made

- Keep scanners independent: one failed scanner does not prevent the other two or the artifact step from running. Use GitHub-hosted Linux runners and read-only repository permission.
- Use the PR base SHA, or the pre-push main SHA. An initial main push with an all-zero base gets a full scan.
- Leave detection, advisory lookup and CVSS calculation to the three free tools. The wrapper only applies commit scope, compares OSV's returned records, applies thresholds and removes sensitive report fields. No replacement regex scanner or vulnerability database was added.
- OSV PR checks fail on any new vulnerable version. Weekly checks fail at CVSS 7 or above, and on unknown severity for review. Semgrep ERROR is its legacy high severity; HIGH and CRITICAL also block. Scanner errors block as incomplete.
- Do not add a feature-branch push trigger or open a PR to manufacture GitHub proof. Claude opens the draft PR, as requested. Required-check branch protection is repository configuration and was not changed through an API.

## Exactly what to open and click to prove it

1. Claude opens one **draft** PR from `codex/ci-security` to `main`, using this description.
2. Open that PR's **Checks → ci → security**. Inspect the Gitleaks, Semgrep and OSV steps. Open the workflow run's **Artifacts → security-<run id>-<attempt>** and download the JSON reports. The local JSON files above are evidence of the local checks only.
3. The required full-job failure/pass proof is still outstanding: on this same PR, push a synthetic probe commit, record the failed Gitleaks step/run and screenshot, remove that throwaway commit from the branch history, then record the fully green security job/run and screenshot. Do not add a real credential or an allowlist. Keep the PR draft until the requested checks are green.
4. After the founder merges, open **Actions → security-weekly → the Monday 06:00 UTC run → Artifacts** and download `security-weekly-<run id>-<attempt>`. Existing historical findings must remain visible and fail the scan until separately reviewed. No merge is requested here.
