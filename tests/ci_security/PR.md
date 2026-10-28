# Free CLI security checks

Work in progress on `codex/ci-security`, based on main `4e74b42`.

- Every PR (including docs-only changes) and main push: Gitleaks scans commits; Semgrep uses `--config auto --baseline-commit`; OSV-Scanner checks committed Python requirements/locks and npm locks against the base snapshot.
- Monday 06:00 UTC: full scans with downloadable, sanitized JSON artifacts, blocking on high findings. Any secret blocks. Unscored OSV findings and incomplete scans block for review.
- No paid service, new secret, application change, or dependency version bump. All scanner versions and workflow actions are pinned.
- Keep `tests/test_secrets.py` unchanged; it can be removed once Gitleaks has run clean for two weeks.

## Proof

Pending. GitHub runs require Claude to open the draft PR: feature-branch pushes are not a requested CI trigger. No GitHub API is used and no PR is opened by this builder. Local checks will be recorded separately, without claiming a GitHub run.
