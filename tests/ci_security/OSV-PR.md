# OSV finding annotations and security download retries

Branch: `codex/osv-dependency-fixes`, created from fetched main `8b3a6d2fb054ba80c9f08d595d19bf72c60c1b07`. Claude opens the draft PR. The founder merges.

**Items 1 and 3 are implemented. Item 2 is blocked, so this brief is not complete.** The managed cloud proxy rejects `api.osv.dev` with HTTP 403. The required OSV scan cannot retrieve advisories. No dependency pin was guessed or changed, and no clean dependency audit is claimed.

## What changed

| File and line | Change |
| --- | --- |
| [.github/scripts/security_scan.py:166](../../.github/scripts/security_scan.py#L166) | Locate each reported Python pin or npm package object in the committed dependency snapshot. Python names follow PEP 503 normalization; npm nested, scoped and aliased packages are handled. When no exact pin exists, anchor at line 1 of the reported file. Source text is never retained or printed. |
| [.github/scripts/security_scan.py:191](../../.github/scripts/security_scan.py#L191) | Read fixed versions from OSV's matching package/ecosystem records. Keep all declared release branches; exclude unrelated packages and Git commit boundaries. Do not implement another vulnerability matcher or assume a lexically sorted version is the minimum safe upgrade. |
| [.github/scripts/security_scan.py:237](../../.github/scripts/security_scan.py#L237) | Emit one escaped `::error file=<lockfile>,line=<n>::<package> <version> <advisory id> fixed-in <version>` annotation per new finding. Multiple OSV fixes are comma-separated; absent fixes are `unavailable`. No advisory descriptions, source lines, matched values or credentials are emitted. Existing baseline comparison and failure policy remain in place. |
| [.github/scripts/install-security-tools.sh:6](../../.github/scripts/install-security-tools.sh#L6) | Both release downloads use curl's existing three retries with `--retry-all-errors`, a one-second retry delay, a 20-second connection timeout and a 120-second limit per attempt. Initial attempt plus at most three retries; failures still stop installation. Versions and checksums are unchanged. |
| [tests/ci_security/test_security.py:89](test_security.py#L89) | Regression tests cover exact annotation fields, no private advisory content, baseline suppression, fix metadata, pin locations, unfixed findings and workflow-command escaping. Synthetic annotations are captured instead of published in CI. |
| [tests/ci_security/test_security.py:301](test_security.py#L301) | Execute both real curl command lines against a loopback HTTP server: three HTTP 404 failures followed by success; persistent HTTP 404 fails after four requests. No release network calls occur in these retry tests. |

Each changed file was committed and pushed before changing the next tracked file:

- `3992c3f`: OSV annotation implementation.
- `23f5a50`: OSV regression tests.
- `4adb9b6`: download retry options.
- `2c52f25`: real-curl retry regression tests.

## Advisory IDs before and after

| Snapshot | Advisory IDs | Result |
| --- | --- | --- |
| Main `8b3a6d2` before changes | **Unavailable, not zero** | Pinned OSV-Scanner 2.7.0 could not reach `api.osv.dev`; full dependency scan returned `osv: incomplete`, exit 1. |
| Branch after changes | **Unavailable, not zero** | Dependency files are unchanged. No after-pin audit is claimed while advisory access is blocked. |

The full scan was attempted on main's tracked requirements, Python locks and npm locks through the existing script. A separate direct scan of `researcher/requirements.txt` failed at the same OSV destination. A connectivity check confirmed `CONNECT tunnel failed, response 403`; the official offline-database host, `storage.googleapis.com`, is also blocked. No policy bypass or replacement advisory database was used.

**Missing prerequisite:** allow HTTPS access to `api.osv.dev` in this managed cloud environment. Then run the full main scan, use its advisory records to choose each lowest fixed version, and run `tests/market_lab_gpt_researcher`, Market Lab feeds and `tests/test_tank_boots.py` after each pin, as requested. Those after-pin tests were not run because no pins were made. The advisory list, version changes and before/after scan proof remain outstanding.

## Exact commands and results

All commands ran on the managed cloud machine, in `/workspace/tervory-osv-fixes`, unless a temporary output path is shown. No GitHub API was used.

```bash
# Run at main 8b3a6d2, before editing dependency files.
PATH=/tmp/ci-security-tools:$PATH python3 .github/scripts/security_scan.py osv --output /tmp/osv-fixes/before
# Exit 1: osv: incomplete; error_type RuntimeError. OSV service access is blocked.

/tmp/ci-security-tools/osv-scanner scan source --no-resolve --all-packages --all-vulns --no-ignore --format json --lockfile requirements.txt:researcher/requirements.txt --output-file /tmp/osv-fixes/researcher-before.json
# Incomplete: api.osv.dev returned Forbidden through the proxy. Not a clean scan.

PATH=/tmp/ci-security-tools/bin:$PATH python3 -m unittest discover -s tests/ci_security -p test_security.py
# Ran 34 tests in 30.688s: OK.

PATH=/tmp/ci-security-tools/bin:$PATH /tmp/ci-security-tools/test-venv/bin/python -m pytest -q tests/ci_security/test_security.py tests/test_secrets.py
# 36 passed, 14 subtests passed in 75.79s.

/tmp/ci-security-tools/test-venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
# All checks passed!

/tmp/ci-security-tools/test-venv/bin/ruff check .github/scripts/security_scan.py tests/ci_security --select E9,F
# All checks passed!

bash -n .github/scripts/install-security-tools.sh
# Exit 0.

mkdir -p /tmp/osv-fixes/installer
RUNNER_TEMP=/tmp/osv-fixes/installer GITHUB_PATH=/tmp/osv-fixes/installer/github-path bash .github/scripts/install-security-tools.sh
# Exit 0. Gitleaks archive checksum: OK. OSV-Scanner binary checksum: OK.

PATH=/tmp/ci-security-tools/bin:$PATH python3 .github/scripts/security_scan.py gitleaks --base 8b3a6d2 --output /tmp/osv-fixes/gitleaks
# Exit 0: gitleaks: clean. Zero findings at code commit 2c52f25.

git diff --check
# Exit 0.
```

The existing [PR #393 security job](https://github.com/Tervory-AI/tervory-tank/actions/runs/40699058924/job/122853586448) was read through its ordinary HTML page. It confirms installation failure with exit 127 and skipped scanners. Its signed-in log was unavailable; the exact cause of that exit is not established. The new code is proven to retry failed downloads; it does not claim that retries repair an absent command. No new GitHub run or founder-browser screenshot is claimed before Claude opens the PR.

## Decisions I made

- Preserve the scanners' baseline and severity policies and all pinned tool versions/checksums.
- Use curl's built-in retry support. Retain checksum verification and stop on exhausted downloads.
- Show OSV's declared fix boundaries rather than invent an upgrade when no fix is published or several release branches exist.
- Stop dependency pinning at the blocked advisory lookup, per rule 9. Complete the independent annotation and retry work without guessing package versions.

## Exactly what to open and click

After Claude opens this branch as a **draft PR**, open its **Checks → ci → security**. Open **Install pinned security CLIs**, **Test security gate policy**, and **OSV-Scanner — new vulnerable versions**. A new vulnerability must produce an error annotation with only its lockfile/line, package, version, advisory ID and declared fix; click the annotation's file link to reach the pin. Download **Artifacts → security-<run id>-<attempt>** for the sanitized JSON. Baseline findings remain excluded from the PR gate, so a passing PR delta must not be presented as a clean full main scan. The dependency-fix task remains blocked until the full before/after audit and affected tests above are complete. The founder merges; no merge is requested.
