# Security weekly: complete summaries, pinned Actions and Meshroom Pillow 13

Branch: `codex/security-weekly-findings`. Existing **draft PR #405**. Latest main `93134ec` is merged, including the founder's newly merged work; Claude's proof redaction correction is preserved. Every edited file was committed and pushed before editing the next tracked file. The founder merges.

The weekly run hid findings beyond GitHub's annotation limit. Each scanner now puts its complete deduplicated metadata list first, followed by individual annotations. The Meshroom worker also needs Pillow 13.0.0 for the reviewed vulnerability fixes; its previous Ubuntu 22.04/Python 3.10 base cannot run that version. It now builds on a digest-pinned official Ubuntu 24.04 CUDA runtime with Python 3.12, and CI starts the actual unchanged Meshroom bundle inside that image.

## What changed, file and line

| File | Result |
| --- | --- |
| [.github/scripts/security_scan.py:44](../../.github/scripts/security_scan.py#L44) | OSV groups package/version/lockfile, declared fixes and unique advisory counts. Semgrep groups locations by rule. Gitleaks groups rule/file/line across commits. Full summaries precede individual annotations, use workflow-command escaping and contain no secret values or source snippets. Failure thresholds and baselines are unchanged. |
| [.github/workflows/coolify-ops.yml:50](../../.github/workflows/coolify-ops.yml#L50), [deploy-on-merge.yml:32](../../.github/workflows/deploy-on-merge.yml#L32), [live-check.yml:45](../../.github/workflows/live-check.yml#L45), [retest.yml:25](../../.github/workflows/retest.yml#L25), [rig-admin-review.yml:23](../../.github/workflows/rig-admin-review.yml#L23), [rig-forge.yml:22](../../.github/workflows/rig-forge.yml#L22), [watchdog.yml:43](../../.github/workflows/watchdog.yml#L43) | Mutable Action tags become full commit SHAs with tag comments. All **34 remote Action references**, including the new image job's checkout, are SHA-pinned. Already pinned references are unchanged. |
| [agents/rig/forge/gpu/meshroom-requirements.in:4](../../agents/rig/forge/gpu/meshroom-requirements.in#L4), [meshroom-requirements.lock:1](../../agents/rig/forge/gpu/meshroom-requirements.lock#L1) | Set Pillow **13.0.0** and regenerate with the header's command, changing only its Python target to **3.12**. The Pillow block has **83 SHA-256 hashes**. Every other dependency block is identical to the prior 12.3.0 lock. |
| [agents/rig/forge/gpu/Dockerfile.meshroom:2](../../agents/rig/forge/gpu/Dockerfile.meshroom#L2) | Use official NVIDIA CUDA **12.5.1 runtime / Ubuntu 24.04**, pinned by the digest read from Docker Hub. Install the hashed lock in a Python 3.12 venv. Use Ubuntu 24.04's GLib package name, install the bundle's required Kerberos shared library, and rename the base's existing UID/GID 1000 account to `forge`. This is the only Dockerfile changed for the Pillow 13 follow-up. |
| [agents/rig/forge/gpu/meshroom.lock.json:8](../../agents/rig/forge/gpu/meshroom.lock.json#L8) | Align only `cuda_image` with the Dockerfile. Meshroom **2023.3.0**, AliceVision **3.2.0**, archive URL, checksum and size remain unchanged. |
| [.github/workflows/rig-forge.yml:42](../../.github/workflows/rig-forge.yml#L42) | Build the actual Meshroom image in CI. In a read-only, non-root container without networking or Linux capabilities, assert Ubuntu 24.04/Python 3.12/Pillow 13.0.0; import the unchanged installer and reconstruction worker; exercise measured scaling and PNG/JPEG/WebP; and run the bundled `meshroom_batch --help`. Failures emit only safe diagnostic types, status and library names. |
| [.github/scripts/deploy_changed.py:40](../../.github/scripts/deploy_changed.py#L40), [room_setup.py:40](../../.github/scripts/room_setup.py#L40), [watchdog.py:209](../../.github/scripts/watchdog.py#L209) | Check the existing fixed Coolify HTTPS base before constructing requests, without echoing supplied settings. Watchdog's literal HTTPS site list and GitHub origin already met the requirement and remain unchanged. |
| [tests/ci_security/test_security.py:305](test_security.py#L305), [tests/test_tank_health.py:94](../test_tank_health.py#L94) | Cover summaries beyond ten findings, deduplication, escaping, redaction, individual annotations and rejection of an unapproved URL base before network access. |

## Docker Hub and dependency proof

```bash
BUILDX_CONFIG=/tmp/meshroom-405/buildx docker buildx imagetools inspect nvidia/cuda:12.4.1-runtime-ubuntu24.04
# not found
BUILDX_CONFIG=/tmp/meshroom-405/buildx docker buildx imagetools inspect nvidia/cuda:12.5.0-runtime-ubuntu24.04
# not found
BUILDX_CONFIG=/tmp/meshroom-405/buildx docker buildx imagetools inspect nvidia/cuda:12.5.1-runtime-ubuntu24.04
# Digest: sha256:447c60da64e4e18860b640289274ec0103816aa56d410041b162d48e85fb1058
# linux/amd64: sha256:0e5a4647ccb8589bb364605cca6c2e17b35b226d4b917faccbffba798c434639
# linux/arm64: sha256:37a25acfc46f9ec05b7131639ed9467810b45522a3dfa99038635ed73c3f1e3c

UV_CACHE_DIR=/tmp/security-weekly/uv-cache uv pip compile --python-version 3.12 --generate-hashes agents/rig/forge/gpu/meshroom-requirements.in -o agents/rig/forge/gpu/meshroom-requirements.lock
# Success: Pillow 13.0.0, 83 hashes. Comparing dependency blocks against 09f8da5 changes only Pillow.

UV_CACHE_DIR=/tmp/security-weekly/uv-cache uv pip install --python /tmp/security-weekly/forge-venv/bin/python --require-hashes -r agents/rig/forge/gpu/meshroom-requirements.lock
UV_CACHE_DIR=/tmp/security-weekly/uv-cache uv pip check --python /tmp/security-weekly/forge-venv/bin/python
# Hash-verified install succeeded; all 43 installed packages are compatible.
```

The review reported **59 advisories** against Pillow 12.3.0, including **PYSEC-2026-4326**, fixed in 13.0.0. The PR's new-vulnerability OSV gate passes with the regenerated lock; this does not claim that the repository's whole-history weekly scan has no other findings. No other Python dependency version or Meshroom bundle version changed.

## Exact validation commands and results

All local commands ran in the managed cloud at `/workspace/tervory-security-weekly`.

```bash
RIG_FORGE_TOOL_ROOT=/tmp/security-weekly/native-setup PATH=/tmp/security-weekly/native-tools/bin:/tmp/security-weekly/native-setup/node_modules/.bin:/tmp/security-weekly/forge-venv/bin:$PATH /tmp/security-weekly/forge-venv/bin/python -m pytest -q tests/test_rig_forge_geometry.py tests/test_rig_forge_pipeline.py tests/test_rig_forge_gpu.py tests/test_rig_forge_review.py tests/test_rig_forge_gpu_artifacts.py tests/test_rig_forge_relay.py tests/test_rig_forge_job_state.py tests/test_rig_forge_seal.py tests/test_rig_forge_workflow_concurrency.py
# After merging main 93134ec: 46 passed in 109.63s. No skips.

/tmp/ci-security-tools/test-venv/bin/python -m pytest -q tests/test_secrets.py
# 2 passed in 29.57s, including the updated proof document.

/tmp/ci-security-tools/test-venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
# All checks passed!
/tmp/ci-security-tools/actionlint -color=false -shellcheck= .github/workflows/*.yml
git diff --check
# Both exit 0, no diagnostics.

docker build --progress=plain -f agents/rig/forge/gpu/Dockerfile.meshroom -t tervory-rig-meshroom:ci agents/rig/forge
# CI build passed. This executes the unchanged install_sources.py against the pinned archive.
```

The exact runtime smoke command and assertions are committed at [rig-forge.yml:77](../../.github/workflows/rig-forge.yml#L77). Its container startup, library loading, imports, measured scaling and codecs all pass on Ubuntu 24.04. This is a startup and CPU compatibility check, not a full GPU reconstruction or a model call. No production data or service was changed. The local Forge suite uses preinstalled Blender 4.3.2; CI's existing `forge-image` job builds and tests the pinned production toolchain.

Verified GitHub results at code commit **52709070e0172264c51303d5c89eb816a034daba**, read from ordinary GitHub web pages, without the GitHub API:

| Job | Result |
| --- | --- |
| [security](https://github.com/Tervory-AI/tervory-tank/actions/runs/40727041398/job/122952982839?pr=405) | Passed |
| [tank](https://github.com/Tervory-AI/tervory-tank/actions/runs/40727041398/job/122953099365?pr=405) | Passed |
| [workspace](https://github.com/Tervory-AI/tervory-tank/actions/runs/40727041398/job/122953099333?pr=405) | Passed |
| [forge-image](https://github.com/Tervory-AI/tervory-tank/actions/runs/40727041449/job/122952983194?pr=405) | Passed |
| [meshroom-image](https://github.com/Tervory-AI/tervory-tank/actions/runs/40727041449/job/122952983233?pr=405) | Passed |

Earlier scanner/HTTPS checks passed **43 tests plus 30 subtests** and **17 health/deploy tests**. Their exact commands, verified Action tag refs and historical Gitleaks results are retained in the [original proof](https://github.com/Tervory-AI/tervory-tank/blob/633044b/tests/ci_security/WEEKLY-PR.md) and [machine-readable evidence](evidence/weekly-review.json); that evidence describes its recorded pre-Pillow-13 commit. The two historical Gitleaks entries remain for Claude's weekly triage. No new allowlist was added by this PR.

## Decisions I made

- Docker Hub has no CUDA 12.4.1 runtime for Ubuntu 24.04. Use the nearest available official runtime, CUDA 12.5.1, with its verified multi-platform digest. Keep the source manifest's base-image metadata in sync.
- Ubuntu 24.04 requires a venv for this pip installation, uses `libglib2.0-0t64`, and already owns UID/GID 1000 through its `ubuntu` account. Rename that account and group to preserve `forge`'s non-root identity. Install `libgssapi-krb5-2` because CI proved that the unchanged Meshroom executable requires its shared library.
- Keep every other Python lock block and the upstream Meshroom archive unchanged. Do not call models or launch a paid GPU reconstruction to check the upgrade.
- Emit complete scanner summaries before individual annotations so GitHub's display limit cannot hide them. Preserve baseline and failure policy. Use the already configured fixed Coolify origin; leave watchdog's existing literal site and GitHub origins alone.

## Exactly what to open and click

Open [PR #405 → Checks](https://github.com/Tervory-AI/tervory-tank/pull/405/checks). Select the latest commit and confirm **ci → security**, **ci → tank** and **ci → workspace** are green. Open **rig-forge → meshroom-image** and expand **Build the pinned Ubuntu 24.04 Meshroom image** and **Verify the installed Meshroom bundle and Python reconstruction runtime**; both must be green. **rig-forge → forge-image** verifies the existing production toolchain separately.

After the founder merges, open **Actions → security-weekly → Run workflow → main**. Open each scanner's first error annotation for its full deduplicated list and download the sanitized results artifact if needed. Claude checks the remaining repository findings from that run. The PR stays draft; the founder merges.
