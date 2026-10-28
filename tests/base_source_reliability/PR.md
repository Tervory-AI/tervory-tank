# Base: measured field reliability and source conflict resolution (job 6)

Base previously computed source scores from whole-record verdicts and never used them in enrichment. This PR now measures only explicit human field checks, sends aggregate scores through the existing Base corridor, and keeps the higher Wilson-bound source when observed values disagree. Both candidates remain in the record evidence.

Continues existing PR #413 and branch `codex/source-reliability`; no duplicate PR. Original head `c851b1f`; synchronized with main `7a13687` through merge `21c5847`. Claude already opened this PR; founder merges. No production operation or model call was performed.

## Changes and line evidence

| File and line | Result |
| --- | --- |
| `tank/base_source_scores.py:20`, `:49`, `:57` | Shared standard-library source classification and selection: reference file, own site, engine registry, socials, archives, Places, OpenCorporates and other web. Host boundaries prevent URL-substring misclassification. Highest Wilson lower bound wins; ties retain first candidate; unmeasured sources rank below measured ones. No measurements preserves legacy pipeline output. |
| `tank/base_reliability.py:32`, `:67`, `:86` | Correct / (correct + wrong), counts, contributing-audit count and 95% Wilson lower bound per source/field. Only explicit resolved field checks contribute. Serialized recompute reads inputs after its lock and stores aggregate numbers under platform owner only. |
| `tank/schema.sql:1877`, `:1881`, `:1894` | Additive field-verdict column and platform aggregate table/ownership. Applied only to disposable local databases in this task. |
| `tank/base_audit.py:162` | Validate field verdicts against sampled verified fields. Save immutable verdicts and recompute in one transaction; a failed recompute rolls back the review. Existing record-accuracy CSV and measurements stay intact. |
| `tank/base_product.py:65`, `:354`, `:362`, `:371` | Optional `field_verdicts` on the existing founder review API; founder aggregate read and Base-room aggregate read. Room endpoint uses existing Base key and US-region guard; no audit snapshots or client identifiers leave it. |
| `agents/base/room.py:213`, `agents/base/Dockerfile:12` | Load score snapshot once per bound batch, under a lock, and package the shared selector. No extra model/skill call or setting. |
| `agents/base/pipeline.py:69`, `:284`, `:420` | Apply source ranking to field merges and observed contacts; preserve selected and competing values, source URLs and check dates in existing passes evidence. |
| `tank/base_evidence.py:178`, `:195` | Preserve chosen primary through verified export, retaining alternatives. Ranking cannot override blocked/archive/final-check failures. Handle existing string social-access errors without crashing collection. |
| `tests/test_base_source_reliability.py`, `tests/test_base_audit.py` | Known counts, mixed wrong-email/correct-phone measurement, uncertainty, legacy exclusion, taxonomy, stable ties, real room-client/pipeline fake-HTTP proof, guarded route, atomic rollback and concurrent batches. |

## Additive audit contract

`POST /v1/base-product/campaigns/{campaign_id}/audits/{audit_id}/review` still accepts `tenant_id` and the existing checked `csv`. It additionally accepts `field_verdicts`, a map from sampled record IDs to field-name verdict maps. Allowed verdicts are `correct`, `wrong`, `unsure`; keys must identify verified fields in that saved audit. It can be sparse: unreviewed and unsure fields never contribute to source scores. Send it with the first review; saved reviews are immutable. An identical retry is accepted; changed checks return 409.

Legacy record-only reviews remain valid record-accuracy evidence and produce **no field-reliability measurements**. No field checks are inferred from historical records. Review findings identified and corrected the old per-record proxy; this report supersedes the original PR body's proxy-score and incomplete-pipeline descriptions.

Sources without an actual verified field check have no score row. This work adds no Google Places/OpenCorporates fetcher, provider, payment or fabricated measurement. Audit records remain tenant-scoped; the platform table stores source names, field names and numbers only. Per-record source/value alternatives stay in that record's own evidence.

## Exact commands and results

Working directory: `/tmp/tervory-source-reliability-413`. Python 3.12.16. Test data and PostgreSQL are isolated and disposable. No production SQL was run.

```sh
gh api repos/Tervory-AI/tervory-tank/commits/main --jq .sha
gh pr list -R Tervory-AI/tervory-tank --state open --json number,title,headRefName,url
gh pr view 413 -R Tervory-AI/tervory-tank --json headRefOid,comments,reviews,files
git clone --single-branch --branch codex/source-reliability https://github.com/Tervory-AI/tervory-tank.git /tmp/tervory-source-reliability-413
git ls-remote --heads origin
git fetch origin main
git merge --no-edit FETCH_HEAD
```

Main returned `7a13687de256896c488a0f28e0906fbcbce5b046`; exact existing owner was #413/codex/source-reliability. No reviews/comments existed initially. First merge attempt stopped because local committer identity was unset. Set repository-local identity, then retried successfully with no conflicts:

```sh
git config user.name 'Codex'
git config user.email 'codex@users.noreply.github.com'
git merge --no-edit FETCH_HEAD
git push origin codex/source-reliability
```

Every completed file was separately committed and immediately pushed with `git add <file>`, `git commit -m <recorded commit subject>`, `git push origin codex/source-reliability`. All pushes succeeded; the PR commit list preserves every checkpoint and subject.

Environment setup, no repository dependency changes:

```sh
/home/ammosync/.local/bin/python3.12 -m venv /tmp/base-reliability-venv
/tmp/base-reliability-venv/bin/python -m pip install pytest pytest-asyncio ruff asyncpg==0.30.0 httpx==0.28.1 fastapi==0.162.0 pydantic==2.10.6 selectolax==0.3.27 PyYAML==6.0.3 rapidfuzz==3.10.1 cryptography==50.0.2 pypdf==6.21.2 > /tmp/base-reliability-install.txt 2>&1
/tmp/base-reliability-venv/bin/python -m pip install jiter==0.18.0 reportlab==4.4.9 uvicorn==0.54.0 redis==5.2.1 tiktoken==0.14.0 openai==2.54.0 > /tmp/base-reliability-extra-install.txt 2>&1
docker run --detach --rm --name base-reliability-413-postgres --publish 127.0.0.1:55446:5432 --env POSTGRES_HOST_AUTH_METHOD=trust postgres:16.15
```

All succeeded. The second install supplied dependencies missing during the initial exploratory run (jiter/reportlab). No real key was used or inspected.

```sh
BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55446/postgres BASE_RELIABILITY_PROOF_DIR=tests/base_source_reliability /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_base_source_reliability.py tests/test_base_audit.py tests/test_base_product.py tests/test_base_database.py --tb=short > /tmp/base-reliability-core.txt 2>&1
BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55446/postgres /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_b3b_base_wiring.py tests/test_b3_base_room.py -k 'not tank_proxies_base and not scrape_1_2_0_returns_joined_html_capped_at_400_kb' --tb=short > /tmp/base-reliability-room-tests.txt 2>&1
POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55446/postgres timeout 150 /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_tank_boots.py tests/test_secrets.py --tb=short > /tmp/base-reliability-ci-tests.txt 2>&1
```

Results: **69 passed in 55.25s**, **10 passed / 2 deselected in 0.79s**, **3 passed in 23.30s** respectively. [Core](core.txt), [room](room-tests.txt), [startup and secret checks](ci-tests.txt). Tank starts twice against an empty local database, covering additive reapplication.

After improving the offline conflict proof to derive its scores from known human field checks:

```sh
BASE_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:55446/postgres BASE_RELIABILITY_PROOF_DIR=tests/base_source_reliability /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_base_source_reliability.py --tb=short > /tmp/base-reliability-focused.txt 2>&1
```

Result: **8 passed in 12.82s**. [Focused](focused.txt). [Actual offline conflict output](conflict.json): own site 50 correct / 100 checked; social profile 100 / 100. The social phone wins on its measured Wilson bound and both sourced phones survive in exported evidence. This is explicitly an offline fixture, not DC acceptance.

```sh
/tmp/base-reliability-venv/bin/ruff check tank tests --select E9,F --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401' > /tmp/base-reliability-lint.txt 2>&1
/tmp/base-reliability-venv/bin/ruff check agents/base/pipeline.py agents/base/room.py --select E9,F >> /tmp/base-reliability-lint.txt 2>&1
git diff --check >> /tmp/base-reliability-lint.txt 2>&1
```

Both lint selections passed; whitespace check passed. [Output](lint.txt). No Workspace build: no page or Workspace file changed.

### Incomplete regression checks

The unrestricted initial Base/room selection was interrupted while the existing Tank proxy test stalled. A second run excluding it reached the unchanged large-HTML scrape test and was terminated. Diagnostic command:

```sh
timeout 75 /tmp/base-reliability-venv/bin/python -m pytest -vv tests/test_b3b_base_wiring.py -o faulthandler_timeout=20 --tb=short > /tmp/base-reliability-wiring.txt 2>&1
```

These are unresolved regression stalls in existing tests; no same-command main baseline was run, so they are not established pre-existing baseline failures. Stack points at the unchanged `EMAIL.findall(body_text)` in approved `tank/skills/base.scrape_site/1.2.0/run.py:133`. Terminated that diagnostic process at about 46 seconds; no pass claimed for the two deselected tests. [Recorded diagnostic stack](wiring.txt). Approved skill code was not edited. The initial run before environment setup also had missing-dependency failures and skipped DB tests; the isolated DB regression commands above supersede those checks, except these two explicit exclusions.

After adding the proof/report files, reran:

```sh
/tmp/base-reliability-venv/bin/python -m pytest -q tests/test_secrets.py --tb=short > /tmp/base-reliability-final-secrets.txt 2>&1
git diff --check
```

Result: **2 passed in 9.61s**; whitespace passed. This repeats checks already covered in the three-test startup/secret selection; it is not two additional distinct tests.

## Review and live acceptance

Independent reviewer accepted the explicit-field measurement correction through `7a2c798` and reviewed implementation/proof at `24cd13a` with no new actionable source defect. This documentation-only follow-up clarifies that the two stalls lack a main baseline. Hosted checks must be assessed on the final PR head, not earlier checkpoints. No merge, deploy, production SQL, paid/provider work, live campaign, customer input, page copy, Figma change or real model call was performed.

**Founder acceptance remains pending:** the next actual DC audit must supply real field verdicts. Show resulting aggregate scores and a subsequent actual record whose higher-scoring source won, with the retained alternative evidence, in the founder's own browser. No DC records, screenshot, inbox, tenant identity or founder-browser success is fabricated here. This branch proves the behavior offline only.
