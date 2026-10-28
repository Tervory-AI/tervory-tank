# PR #362: document SQL and dependency security fixes

Pulled `codex/market-docs-1-vaults` through Claude's merge `f238247` before editing.
Each finished file was committed and pushed separately. This is the security
proof/addendum for the existing PR; no GitHub API was used to edit its description.
Comparison base: merged main `8b3a6d2fb054ba80c9f08d595d19bf72c60c1b07`.

## What changed

- `agents/market_lab/core/documents.py:92`: replaces both table-name loops with
  explicit DELETE statements for points, events, batch points and batches.
  The existing series/file DELETEs remain explicit. SQL text is entirely literal;
  values use `$1`/`$2`. Order, tenant/source filters and caller transaction stay
  the same. This removes the two `sqlalchemy-execute-raw-query` findings.
- `agents/market_lab/feeds/requirements.txt:5`: pins `pdfplumber==0.11.9` and
  explicitly pins `pdfminer.six==20251230`, the first compatible pair fixing both
  PDF advisories. `tank/requirements-dev.txt` already includes this file.
- `tank/requirements.txt:35`: pins `python-multipart==0.0.31`, the lowest version
  fixing all six OSV advisories. The fixture proof requirements inherit this pin.
- `tests/market_docs_security/prove_deletion.py:33`: adds a standalone, rollback-only
  local Postgres proof covering all six tables, another file, another tenant
  sharing the same file UUID, and repeat deletion. Existing tests are unchanged.
- `tests/market_docs_security/security-proof.json:1`: records sanitized before/after
  reports, fixed-version ranges, scanner versions and database proof output.

## Advisory IDs before and after

The CI OSV scan before the dependency changes reported 24 new entries: six
multipart advisories, each with GHSA/PYSEC aliases, reported through both
`tank/requirements.txt` and `agents/market_lab/fixture_proof/requirements.txt`.
The resolved `pip-audit` check separately found the two transitive PDF advisories.
OSV's CI invocation uses `--no-resolve`; its absence of a transitive PDF finding
was not treated as evidence that pdfminer was safe.

| Package before | Advisory and aliases | First fixed version | After |
| --- | --- | --- | --- |
| pdfminer.six 20250506 | CVE-2025-64512 / GHSA-wf5f-4jwr-ppcp / PYSEC-2026-1762 | 20251107 | Absent at 20251230 |
| pdfminer.six 20250506 | CVE-2025-70559 / GHSA-f83h-ghpp-7wcc / PYSEC-2026-1761 | 20251230 | Absent at 20251230 |
| python-multipart 0.0.22 | CVE-2026-40347 / GHSA-mj87-hwqh-73pj / PYSEC-2026-3038 | 0.0.26 | Absent at 0.0.31 |
| python-multipart 0.0.22 | CVE-2026-42561 / GHSA-pp6c-gr5w-3c5g / PYSEC-2026-3039 | 0.0.27 | Absent at 0.0.31 |
| python-multipart 0.0.22 | CVE-2026-53539 / GHSA-5rvq-cxj2-64vf / PYSEC-2026-3036 | 0.0.30 | Absent at 0.0.31 |
| python-multipart 0.0.22 | CVE-2026-53538 / GHSA-6jv3-5f52-599m / PYSEC-2026-3037 | 0.0.30 | Absent at 0.0.31 |
| python-multipart 0.0.22 | CVE-2026-53537 / GHSA-vffw-93wf-4j4q / PYSEC-2026-3041 | 0.0.30 | Absent at 0.0.31 |
| python-multipart 0.0.22 | CVE-2026-53540 / GHSA-v9pg-7xvm-68hf / PYSEC-2026-3040 | 0.0.31 | Absent at 0.0.31 |

PyPI release metadata confirms that pdfplumber 0.11.7 requires pdfminer 20250506
exactly, 0.11.8 requires 20251107 (still affected by CVE-2025-70559), and 0.11.9
requires 20251230. Overriding pdfminer while retaining pdfplumber 0.11.7 would
create incompatible requirements. Sources: the version-specific JSON at
`https://pypi.org/pypi/pdfplumber/<version>/json`; multipart fixed ranges came from
`https://api.osv.dev/v1/vulns/<GHSA ID>` and are retained in the proof JSON.

After: the resolved PDF graph has **no known vulnerabilities**, and the full CI
OSV comparison has **zero new findings**. The repository-wide count drops from
295 to 271; the remaining 271 are existing baseline findings, not a claim of a
vulnerability-free repository. No suppressions or audited exceptions were added.

## Exact commands and results

Commands ran from `/workspace/tervory-tank` unless another directory is stated.
OSV 2.7.0 and Gitleaks 8.30.1 were downloaded from the exact release URLs in
`.github/scripts/install-security-tools.sh`, with its SHA-256 checks passing.
Semgrep 1.182.1, the same CLI version as CI, ran from an isolated Python environment
instead of the CI container. `pip-audit` version was 2.10.1.

Before changing dependency pins, at `76e7265`:

```sh
PATH=/workspace/market-docs-security/bin:$PATH /workspace/market-docs-security/venv/bin/python .github/scripts/security_scan.py osv --base 8b3a6d2 --output /workspace/market-docs-security/before
/workspace/market-docs-security/venv/bin/pip-audit -r agents/market_lab/feeds/requirements.txt -f json -o /workspace/market-docs-security/pdf-before.json
```

Results: `osv: findings` (exit 1, 24 new entries); pip-audit exit 1, four report
entries representing the two unique PDF advisory IDs above. The proof JSON
deduplicates identical pip-audit entries and omits advisory prose.

After changing dependency pins, at `4ad6d81`:

```sh
PATH=/workspace/market-docs-security/bin:$PATH /workspace/market-docs-security/venv/bin/python .github/scripts/security_scan.py osv --base 8b3a6d2 --output /workspace/market-docs-security/after
/workspace/market-docs-security/venv/bin/pip-audit -r agents/market_lab/feeds/requirements.txt -f json -o /workspace/market-docs-security/pdf-after.json
```

Results: `osv: clean`, exit 0, `findings: []`; `No known vulnerabilities found`,
exit 0, across the complete resolved PDF dependency graph.

Security checks after adding the database proof, at `5f9a122`:

```sh
PATH=/workspace/market-docs-security/venv/bin:$PATH /workspace/market-docs-security/venv/bin/python .github/scripts/security_scan.py semgrep --base 8b3a6d2 --output /workspace/market-docs-security/final
PATH=/workspace/market-docs-security/bin:$PATH /workspace/market-docs-security/venv/bin/python .github/scripts/security_scan.py gitleaks --base 8b3a6d2 --output /workspace/market-docs-security/final
PATH=/workspace/market-docs-security/bin:$PATH /workspace/.tervory-cloud/venv/bin/python -m unittest discover -s tests/ci_security -p test_security.py -v
```

Results: `semgrep: clean`, zero findings and zero fatal errors; `gitleaks: clean`,
zero findings; all 26 security-policy tests pass. Semgrep reports 21 nonfatal
parsing/timeout notices in existing workflow, shell, Dockerfile and Rig bundle
files. They are preserved in the evidence and are notices under CI's policy.
The security-policy test run used the same unchanged policy files before the
standalone database proof was added.

Installed and checked the actual branch requirements before regression tests:

```sh
/workspace/.tervory-cloud/venv/bin/python -m pip install -r tank/requirements.txt -r tank/requirements-dev.txt
/workspace/.tervory-cloud/venv/bin/python -m pip check
/workspace/.tervory-cloud/venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
/workspace/.tervory-cloud/venv/bin/ruff check agents/market_lab/core/documents.py --select E9,F
PYTHONPATH=tank PATH=/workspace/.tervory-cloud/node-v22.23.4-linux-x64/bin:$PATH /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/test_secrets.py tests/test_tank_one_door.py tests/test_market_lab_documents.py tests/test_vault_contract.py tests/test_bucket1_storage.py tests/test_market_lab.py tests/test_market_lab_evidence.py tests/test_market_lab_before_deploy.py tests/test_market_lab_review.py tests/test_market_lab_source_pages.py
```

Results: install succeeded; `No broken requirements found`; both Ruff commands
reported `All checks passed!`; **229 passed, 1 warning in 34.37s**. The installed
versions were pdfplumber 0.11.9, pdfminer.six 20251230 and python-multipart 0.0.31.
The existing PDF extraction, page citations, CSV/XLSX guards, vault contracts,
storage tests, secret gate and Tank one-door gate all pass.

## Real Postgres deletion proof

The database was disposable, loopback-only, and contained test data only:

```sh
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock run --detach --rm --name codex-market-docs-security-postgres --tmpfs /var/lib/postgresql/data:size=512m -e POSTGRES_HOST_AUTH_METHOD=trust -e POSTGRES_DB=market_docs_security_test -p 127.0.0.1::5432 postgres:16
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock port codex-market-docs-security-postgres 5432/tcp
PYTHONPATH=tank DATABASE_URL=postgresql://postgres@127.0.0.1:32771/market_docs_security_test /workspace/.tervory-cloud/venv/bin/python tests/market_docs_security/prove_deletion.py
```

Docker assigned port 32771; a fresh run may assign another. The script refuses
non-loopback databases or names not ending in `_test` and rolls back its rows.
Result, exit 0:

```json
{
  "before": {"points": 2, "events": 1, "batch_points": 2, "batches": 1, "series": 1, "uploaded_files": 1},
  "after": {"points": 0, "events": 0, "batch_points": 0, "batches": 0, "series": 0, "uploaded_files": 0},
  "same_tenant_other_file_preserved": true,
  "other_tenant_same_file_id_preserved": true,
  "repeat_delete_safe": true,
  "result": "passed"
}
```

## Existing process-level proof failure reproduced on the pulled head

```sh
PYTHONPATH=tank DATABASE_URL=postgresql://postgres@127.0.0.1:32771/market_docs_security_test /workspace/.tervory-cloud/venv/bin/python -m pytest -q -s tests/test_market_lab_documents_real_tank.py
git worktree add --detach /workspace/market-docs-security/base f238247
# From /workspace/market-docs-security/base:
PYTHONPATH=tank DATABASE_URL=postgresql://postgres@127.0.0.1:32771/market_docs_security_test /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/test_market_lab_documents_real_tank.py
```

Branch: **1 failed in 6.77s**. Untouched `f238247`, in the same Python environment:
**1 failed in 5.71s**. Both fail at `tests/market_docs_proof.py:194` with
`KeyError: 'facts'`: after the PDF is learned and its cited answer succeeds, the
second tenant's empty answer invokes the web-research fallback merged from main.
The existing document harness has no research service, so that response is an
error rather than the expected facts array. The existing harness and research
behavior were not modified by this security repair. A passing process-level job
is not claimed; this failure remains for the integration thread.

No page text, Figma changes, live data changes or founder-browser screenshots
were created. These are local security and regression results, not a claim of
GitHub Actions or founder deployment acceptance.
