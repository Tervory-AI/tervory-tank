# Base review: rebased full-suite comparison

Fresh cloud clones, Python 3.12 and Node 22.23.4, with CI's dependency installation
order and fresh npm installs. Each checkout has its own loopback PostgreSQL 16
service. The full suites run sequentially to avoid shared fixture interference.

- Main: `2b12945dc78ffe3d43bf6100ba1f1517210a409e` (Tiger #335, Tank #334,
  Market Lab #336 and the main test fixes).
- Rebased application/test code: `1d57d3df61a0752645713bca55064c515d217945`.
- `.github/scripts/ci_scope.py`: `tests=["."]`; no tests deselected.
- Command: `python -m pytest -q -p no:cacheprovider --junitxml=/tmp/full.xml .`.
  PostgreSQL environment settings are listed in README.md.
- Base and Market Lab run together in each full session.

| Fresh clone | Passed | Failed | Errors | Skipped |
| --- | ---: | ---: | ---: | ---: |
| Main `2b12945` | 3639 | 2 | 0 | 17 |
| Rebased branch `1d57d3d` | 3689 | 2 | 0 | 17 |

**0 new failing test identities versus current main.**

```text
Main:   2 failed, 3639 passed, 17 skipped, 53 warnings, 1059 subtests passed in 1118.43s (0:18:38)
Branch: 2 failed, 3689 passed, 17 skipped, 54 warnings, 1059 subtests passed in 1126.24s (0:18:46)
```

Failures on both snapshots:

- `tests.test_rig_forge_pipeline::test_neutral_samples_pass_all_real_tools[ai-sample.glb]`
- `tests.test_rig_forge_pipeline::test_neutral_samples_pass_all_real_tools[scan.obj]`

Rebase preservation checks:

- Tiger's browser file is byte-identical to main: document-only block, per-run
  reset, the shared user agent and the HTML gate remain intact.
- Docker COPY contains the union of main's and Base's entries.
- schema.sql begins with main's complete schema, followed by Base's additive block.
- Tank function ASTs match main except the already-approved startup HTTP hook
  and ledger-summary price-status accounting. Rung-3, masking and the queue/cache
  code are unchanged; Market Lab's router registration remains at line 4103.
- The one-door scanner stays unchanged; three exact fingerprint/count audits
  cover six offline Base Brave literals (Request/Response or MockTransport only).
- `git merge-tree --write-tree origin/main HEAD` succeeds without conflicts.

Focused validation: 23 Base/CSV/boundary tests passed. CSV cases assert sentences
for blocked/missing/unknown reasons, exact ISO dates, unchanged phone values and
source URLs, while the stored reason and count filter stay unchanged. Workspace
production build (CI dummy Clerk settings), CI Ruff and whitespace checks passed.

`tests/test_tank_boots.py`: 1 passed in 8.78s. It starts the real Tank under uvicorn
twice on one empty database and checks /health both times. See tank-startup.txt
for both returned startup logs. Its Redis-cache warning is intentional: the test
points Redis to closed loopback port 9. No Tank stand-in was used.

The independent review at 886074f separately confirmed the real Tank + Base +
Workspace job and the previous fixes. The screenshots remain explicitly local
fixture pages. Signed-in live proof is reserved for Claude after deployment.

This comparison supersedes the older 3261163 baseline. The later plain-column CSV follow-up changes the exporter and its tests; this
full-suite comparison remains evidence for the exact commits above, not a claim
of a new full-suite run. That follow-up passed 32 targeted product/database/
Workspace tests, CI Ruff and the 375/1440 local fixture browser proof. See README.md
and the updated downloaded CSV. No Actions reruns; PR #339 remains a draft.
