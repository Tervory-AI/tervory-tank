# PR 329: security and supply-chain audit — 4 Nov 2026

Compared existing PR head `59c3c26abd3f95a12cc83eb585ac6431c9bc99d2`
with current main `fa34a9f0d9e8323358ebb47c82ba5e9f2eed9fab`. The old PR is
not discarded because of its number. GitHub reported MERGEABLE; no main merge
was necessary and none was performed. No dependency bumps or application runtime
changes are part of this update.

## Component decisions and evidence

| Proposed component | Today's evidence on main | Final disposition |
| --- | --- | --- |
| Separate full-history secret baseline wrapper | `.github/workflows/ci.yml`, job `security`, runs on every PR and merge group; `.github/scripts/security_scan.py:leaks` runs redacted Gitleaks with checked reports and rejects findings/scanner failures. `.github/workflows/security-weekly.yml` runs the whole-history scan. | Superseded. Remove `.github/gitleaks-baseline.json`, `check_secret_baseline.py`, their tests and the duplicate `secrets.yml` from this PR. These were additions from this proposal, not files on main. Do not expand or change main's existing `.gitleaks.toml`, `.gitleaksignore` or scanner behavior. |
| Install-pin enforcement | Main's `ci.yml` still includes `pip install --upgrade pip`, requirements-text installs and `npm ci` without `--ignore-scripts`; image/manifest pinning is not enforced by `security_scan.py`, which scans secrets, code and vulnerabilities. | Retain additive `install-pins.yml` and the literal-command/lock checker. Run on every PR and merge group using the trusted base SHA; unchanged debt is reported and new/changed violations fail. No new allowlist or migration claim. |
| OSV scan | Main already has PR/merge-group OSV enforcement and a weekly all-lock scan. | Preserve unchanged. The read-only watch complements this with independent GitHub advisory queries, exact CISA KEV matches and custom software-lock/source identity coverage; it does not replace, weaken or claim to satisfy `ci.security`. |
| Automatic dependency resolution and draft-PR publication | The old `supply-chain.yml` ran `--publish` nightly and requested a new write-capable `SUPPLY_CHAIN_GITHUB_TOKEN`. No such publication/credential grant is included in this backlog authorization. | Remove `fixes.py`, CLI publication mode, Node setup/resolver, publication tests and write-token reference. Retain advisory fixed-version candidates only as report data. HTTP rejects write methods; no package install, branch, PR, publication, merge, deployment or credential creation path remains. |
| Market Lab public source list | `git ls-tree -r origin/main agents/market_lab` has no `supply_chain` namespace; it is owned entirely by this PR. | Retain the existing proposed registry in this PR unchanged. No writes to another product checkout or its live source registry. OSV/GitHub/CISA are public/free; no paid source. |

## Focused proof

- `tests/test_install_pins.py`: rejects mutable Python/Node/Docker installs,
  missing/unhashed/transitive locks, npm flag overrides, duplicate and changed
  violations; line shifts alone do not create migration churn. It verifies both
  PR and merge-group trigger contracts without a second secret baseline. A stale
  PR event base is replaced only with the verified synthetic merge first parent:
  its second parent must equal the event head, and the first must descend from
  the advertised base and belong to the fetched trusted base branch. Head-only
  checkouts, unrelated base parents and wrong heads fail. This fixes #329 event
  metadata reporting `feccd797` while checkout merged onto `fa34a9f0`, without
  excusing any actual PR violation.
- `tests/test_supply_chain_watch.py`: fixture advisory/KEV attribution, independent
  source queries, incomplete/truncated coverage, withdrawn advisories, nested
  identities and no import-time I/O. Read-only CLI tests cover clean/findings/error
  exits and persisted reports. The removed publication option fails before I/O;
  GitHub POST/PATCH/DELETE attempts fail before transport.
- Parse-only audit of **current main's** committed lock blobs: 15 locks, 1,196
  dependency records, no unsupported format. One model-weight lock is explicitly
  data-only. This is parser coverage, not a live clean-advisory result.
- Static install-gate audit of current main plus the retained PR additions:
  **0 new violations, 136 inherited violations**. This exported-file comparison
  leaves the branch/history untouched and does not claim migration debt is fixed.
- No live watch or publication was run locally. Final-head hosted CI, including
  strict security and the new install gate, is the acceptance evidence; local
  checks are limited to these focused regressions and lint.

## Acceptance after review

Open this PR's final-head Checks: `security` must retain current main's strict
policy, and `install-pins` must reject new violations. The existing full-suite
merge queue remains authoritative; this PR does not change its timing or checks.
After the reviewed workflow lands, its scheduled read-only report is visible in
Actions → supply-chain → run summary. A feed outage or finding produces a failed
watch with an explicit report; it never publishes a fix or means permission to
change production. No UI, model, production SQL or Skala action is involved.

No install-debt migration or Dependabot alert-count clearance is claimed. Existing
mutable installs on main remain outside this additive gate's retroactive scope;
changing one must meet the gate. Source outages/rate limits remain explicit failed
coverage, not suppressed findings.
