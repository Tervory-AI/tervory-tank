# Security weekly: complete finding summaries, immutable Actions and Pillow fix

Branch: `codex/security-weekly-findings`. Started at fetched main `be3935d`; merged latest main `73a0e2f` without conflicts in `a9c319b`. Claude opens this as a **draft PR**. Every edited file was committed and pushed before editing the next tracked file. The founder merges and then re-runs security-weekly.

The [failed weekly run 40706727949](https://github.com/Tervory-AI/tervory-tank/actions/runs/40706727949) hides most findings behind GitHub's per-step annotation limit. Each scanner now emits its complete deduplicated metadata list in one summary annotation, **before** individual annotations, so the summary remains visible within that limit. No secrets, source snippets or matched values enter either form. Finding thresholds and baselines are unchanged; clean tools emit no false error annotation.

## What changed, file and line

| File | Result |
| --- | --- |
| [.github/scripts/security_scan.py:44](../../.github/scripts/security_scan.py#L44) | OSV groups by package/version/lockfile and counts unique advisory IDs, retaining OSV's declared fixes. Semgrep groups unique file/line locations by rule. Gitleaks deduplicates rule/file/line across commits. All three use the existing workflow-command escaping, with no list truncation. Individual Semgrep/OSV annotations remain; Gitleaks also gets metadata-only individual annotations. |
| [.github/workflows/coolify-ops.yml:50](../../.github/workflows/coolify-ops.yml#L50), [deploy-on-merge.yml:32](../../.github/workflows/deploy-on-merge.yml#L32), [live-check.yml:45](../../.github/workflows/live-check.yml#L45), [retest.yml:25](../../.github/workflows/retest.yml#L25), [rig-admin-review.yml:23](../../.github/workflows/rig-admin-review.yml#L23), [rig-forge.yml:22](../../.github/workflows/rig-forge.yml#L22), [watchdog.yml:43](../../.github/workflows/watchdog.yml#L43) | Replace mutable Action tags with verified full commit SHAs and retain their tag comments. All **33 remote Action references** across every workflow are now SHA-pinned; no unpinned reference remains. Already pinned Actions in ci.yml and security-weekly.yml were verified and left alone. The local reusable workflow reference stays local. |
| [agents/rig/forge/gpu/meshroom-requirements.in:4](../../agents/rig/forge/gpu/meshroom-requirements.in#L4), [meshroom-requirements.lock:248](../../agents/rig/forge/gpu/meshroom-requirements.lock#L248) | Pillow **11.3.0 → 12.3.0**, regenerated with the original Python 3.10 `uv pip compile --generate-hashes` command. Only the Pillow dependency block changes; it contains **87 SHA-256 hashes**. The input pin must match so regeneration cannot restore the vulnerable version. |
| [.github/scripts/deploy_changed.py:40](../../.github/scripts/deploy_changed.py#L40), [room_setup.py:40](../../.github/scripts/room_setup.py#L40) | Reject COOLIFY_URL unless its normalized base is the existing fixed `https://coolify.tervory.com`. Construct the request from that literal HTTPS base. Reject before urlopen and never echo the supplied value. |
| [.github/scripts/watchdog.py:209](../../.github/scripts/watchdog.py#L209) | Strengthen the Coolify check from “any HTTPS URL” to the same fixed HTTPS base. The applications request uses the literal approved URL. |
| [tests/ci_security/test_security.py:305](test_security.py#L305), [tests/test_tank_health.py:94](../test_tank_health.py#L94) | Test summaries containing more than ten findings, deduplication, redaction, escaping, unchanged individual annotations, clean reports, and fixed-base rejection before network access. Existing mocked watchdog fixtures use the allowed base; all requests are intercepted. Room setup tests load only its API function, never the module-level room/secret/deploy operations. |

### Existing fixed URLs left unchanged

Watchdog's `SITES` tuple at [.github/scripts/watchdog.py:25](../../.github/scripts/watchdog.py#L25) contains only literal HTTPS health URLs; `collect()` passes those constants to `check_site()` and `http_status()`. Its `GitHub.request()` at [line 326](../../.github/scripts/watchdog.py#L326) concatenates request paths onto the literal `https://api.github.com` base. Those sources already have a fixed HTTPS origin and were left unchanged. No GitHub API call, deployment, room setup, secret generation or production mutation was executed during this work. This documents the source validation; a generic Semgrep rule may still flag a dynamic variable at urlopen for Claude to assess.

### Verified Action tags

Resolved with `git ls-remote https://github.com/<owner>/<action> refs/tags/<tag>`; the peeled `refs/tags/<tag>^{}` ref was also requested to handle annotated tags. Exact commands and returned refs are in [weekly-review.json](evidence/weekly-review.json).

| Action | Tag comment | Full commit SHA |
| --- | --- | --- |
| `actions/cache` | `v6` | `55cc8345863c7cc4c66a329aec7e433d2d1c52a9` |
| `actions/checkout` | `v7` | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `actions/setup-node` | `v7` | `949feb2413d6458794dcd2491c4babbbce0c15c1` |
| `actions/setup-python` | `v7` | `6d4fd22b20465ccc0f7354476588e8df7c9ca0e0` |
| `actions/upload-artifact` | `v7` | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` |

### Pillow advisories

The requested fix covers **PYSEC-2026-165, PYSEC-2026-2249, PYSEC-2026-2250, PYSEC-2026-2251, PYSEC-2026-2252, PYSEC-2026-2253, PYSEC-2026-2254, PYSEC-2026-2255, PYSEC-2026-2256, PYSEC-2026-2257**, as identified in the brief. PyPI confirms Pillow 12.3.0 supports Python >=3.10. The regenerated lock installs with hashes; Pillow 12.3.0 successfully encodes and decodes PNG, JPEG and WebP, and the installed Forge environment passes its dependency compatibility check. No other vulnerable package is changed here. The founder's next weekly run establishes the remaining full-repository advisory list; no new OSV clean run is claimed.

## Exact validation commands and results

All commands ran in the managed cloud at `/workspace/tervory-security-weekly`. [Machine-readable proof](evidence/weekly-review.json) records the code commit, tool versions, Action refs and results.

```bash
UV_CACHE_DIR=/tmp/security-weekly/uv-cache uv pip compile --python-version 3.10 --generate-hashes agents/rig/forge/gpu/meshroom-requirements.in -o agents/rig/forge/gpu/meshroom-requirements.lock
# Success. Compared every generated dependency block with HEAD: only Pillow changes.

UV_CACHE_DIR=/tmp/security-weekly/uv-cache uv pip install --python /tmp/security-weekly/forge-venv/bin/python --require-hashes -r agents/rig/forge/requirements.lock -r agents/rig/forge/requirements-test.lock
UV_CACHE_DIR=/tmp/security-weekly/uv-cache uv pip install --python /tmp/security-weekly/forge-venv/bin/python --require-hashes -r agents/rig/forge/gpu/meshroom-requirements.lock
# Both succeeded. Pillow 12.3.0 installed.

GOMAXPROCS=2 PATH=/tmp/ci-security-tools/bin:$PATH python3 -m unittest discover -s tests/ci_security -p test_security.py
# 41 tests passed in 48.648s.

GOMAXPROCS=2 PATH=/tmp/ci-security-tools/bin:$PATH /tmp/ci-security-tools/test-venv/bin/python -m pytest -q tests/ci_security/test_security.py tests/test_secrets.py
# 43 passed, 30 subtests passed in 95.43s.

/tmp/security-weekly/tank-venv/bin/python -m pytest -q tests/test_tank_health.py tests/test_deploy_changed.py
# After merging latest main: 17 passed, 6 existing warnings in 11.29s.

RIG_FORGE_TOOL_ROOT=/tmp/security-weekly/native-setup PATH=/tmp/security-weekly/native-tools/bin:/tmp/security-weekly/native-setup/node_modules/.bin:/tmp/security-weekly/forge-venv/bin:$PATH /tmp/security-weekly/forge-venv/bin/python -m pytest -q tests/test_rig_forge_geometry.py tests/test_rig_forge_pipeline.py tests/test_rig_forge_gpu.py tests/test_rig_forge_review.py tests/test_rig_forge_gpu_artifacts.py tests/test_rig_forge_relay.py tests/test_rig_forge_job_state.py tests/test_rig_forge_seal.py tests/test_rig_forge_workflow_concurrency.py tests/test_rig_forge_containers.py -rs
# Final complete local run: 46 passed, 1 skipped in 135.74s.
# Skip: the container isolation case requires RIG_FORGE_CONTAINER_IMAGE.

/tmp/security-weekly/tank-venv/bin/python -m pytest -q tests/test_rig_forge_tank.py -rs
# 4 skipped: TRAINING_SCHEMA_DATABASE_URL / POOL_SCHEMA_DATABASE_URL is not configured.

UV_CACHE_DIR=/tmp/security-weekly/uv-cache uv pip check --python /tmp/security-weekly/forge-venv/bin/python
# All 43 installed packages are compatible.

/tmp/ci-security-tools/test-venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
/tmp/ci-security-tools/test-venv/bin/ruff check .github/scripts/security_scan.py .github/scripts/deploy_changed.py .github/scripts/room_setup.py .github/scripts/watchdog.py tests/ci_security --select E9,F
# Both: All checks passed!

/tmp/ci-security-tools/actionlint -color=false -shellcheck= .github/workflows/*.yml
git diff --check
# Both exit 0; no diagnostics.

GOMAXPROCS=2 PATH=/tmp/ci-security-tools/bin:$PATH python3 .github/scripts/security_scan.py gitleaks --output /tmp/security-weekly/gitleaks-weekly
# Exit 1, two whole-history findings. The first annotation contains both entries;
# two individual annotations follow. No values were printed or committed.

GOMAXPROCS=2 PATH=/tmp/ci-security-tools/bin:$PATH python3 .github/scripts/security_scan.py gitleaks --base 73a0e2f --output /tmp/security-weekly/gitleaks-branch
# Exit 0, zero new findings at code commit a9c319b.
```

Forge's initial native pipeline attempts exposed missing local tools. The existing installer verified the pinned gltfpack 0.25 and KTX 4.4.2 archives; `npm ci --ignore-scripts --no-audit --no-fund` installed the committed Forge npm lock in `/tmp/security-weekly/native-setup`. Unchanged Forge helper files were copied there for the test harness. The final run above passes both neutral sample conversions through the actual tools. Local Blender is the preinstalled **4.3.2**; the production lock remains **4.5.3**. No full container-image validation or skipped database test is claimed. Native Gitleaks tests initially hit their timeouts on this worker; limiting its Go concurrency with `GOMAXPROCS=2` passed the existing timeouts without weakening the tests.

The two remaining history entries are `generic-api-key` at `tests/tank_batch_providers/batch-tests-initial.txt:61` and `:97`. Only rule IDs and locations are reported. No new allowlist or baseline exception was added; Claude decides their disposition from the next weekly run. No new GitHub weekly run, screenshot or independent live approval is claimed before merge.

## Decisions I made

- Emit each complete summary first so GitHub's ten-annotation display cap cannot hide it behind individual findings. Deduplicate only the summary; preserve individual findings and the existing failure policy.
- Update the Meshroom `.in` source alongside its generated lock; otherwise the next compile would reinstate Pillow 11.3.0. Preserve every other dependency block exactly.
- Use the already configured default Coolify origin, `https://coolify.tervory.com`, as the fixed allowed base. Preserve watchdog's existing literal site and GitHub origins. Tests make no external requests.
- Keep all dependency fixes beyond the specified Pillow change and all historical-finding triage for Claude after the founder's weekly rerun. The PR remains draft.

## Exactly what to open and click

After Claude opens the draft PR, open **Checks → ci → security** for the policy tests and **Checks → rig-forge** for the pinned container pipeline. After the founder merges, open **Actions → security-weekly → Run workflow → main**. In the resulting run, open each scanner step's annotations: the first error annotation must contain the full deduplicated list for that tool, including entries beyond the tenth finding; individual annotations remain available. Download **Artifacts → security-weekly-<run id>-<attempt>** for the sanitized reports if needed. Claude reads all three summaries, confirms the mutable-Action and specified Pillow findings are gone, and uses the remaining list to pin the rest. The founder merges; no merge is requested.
