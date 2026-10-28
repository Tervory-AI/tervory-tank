# Market Lab: cited web research through GPT-Researcher and Tank

Branch: `codex/market-lab-gpt-researcher`, started from `origin/main` at `bde4578`.
Initial implementation/test commit: `9787b5e`, initial proof commit: `ef13ba2`.
Existing draft PR: https://github.com/Tervory-AI/tervory-tank/pull/389 . Main `1c78aaa` was merged into this same branch in `5383fea` before the CI repairs below. Git was used for every push; no GitHub API was used. This file is the updated PR description/proof for Claude.

Market Lab's research job previously used the inactive Perplexity gate, while the client Ask route only searched saved feeds. Ask now returns a saved answer first; otherwise it runs GPT-Researcher against our SearXNG. Each returned claim links a page actually found and fetched during that request and includes its recorded UTC fetch time. Every model request goes through Tank's existing `market.research` policy at `/v1/route`.

## PR #389 CI repair after merging main

- `tests/market_lab_gpt_researcher/test_researcher.py:8`: removed the unused `os` import. All subsequent line references in that file move up by one.
- `tests/test_tank_one_door.py:224`: added four canonical AST fingerprint entries covering exactly the five reported occurrences, each with an occurrence count and one-line audit reason. No file/directory exclusion or detector change.
- `tests/test_tank_one_door.py:299`: includes both newly audited files in the existing relocated-checkout test, proving their fingerprints/counts survive checkout paths and line shifts. Added occurrences still fail the gate.

The production model path is **GPT-Researcher → loopback compatibility handler → Tank `/v1/route`**. `researcher/app.py:66` rejects every model destination except the exact loopback URL. `researcher/app.py:119` declares the inbound handler; it is not an outbound provider call. Inside that handler, the sole outbound `client.post` is the literal **`http://tank:8000/v1/route`** at `researcher/app.py:136`, with redirects disabled at line 135. The tenant/home region come from the active request; neither a model-selected URL nor a request-body endpoint is used. Its complete HTTP URL literal list is the loopback base, loopback completion path, and Tank `/v1/route`: **there is no provider address in the production model adapter**. The pinned dependency's endpoint override cannot escape `LocalModelTransport`.

| Reported occurrence (line after import removal) | Fingerprint | Count | Audited reason |
| --- | --- | --- | --- |
| `researcher/app.py:66` | `9f3fd5c68c992e75` | 1 | Exact loopback destination guard; the adapter's only upstream is Tank. |
| `researcher/app.py:119` | `bfc9f701a06f6902` | 1 | Inbound compatibility handler; fixed Tank `/v1/route` upstream, redirects disabled. |
| `tests/market_lab_gpt_researcher/test_researcher.py:64` (reported 65) | `7c773e03813fb599` | 1 | Offline provider response via `MockTransport` behind the real Tank route; sockets are forbidden. |
| `tests/market_lab_gpt_researcher/test_researcher.py:309,321` (reported 310,322) | `bfc9f701a06f6902` | 2 | In-process ASGI tests of adapter authentication and immutable tenant/model policy; no network request. |

[Endpoint/fingerprint audit output](evidence/ci-repair-endpoint-audit.txt) records all HTTP URL literals, the sole outbound POST and the five reviewed findings. Existing runtime tests also verify the only Tank destination (`test_researcher.py:91`), reject `OPENAI_BASE_URL` overrides without sending a key/prompt (`:200`), verify tenant/policy immutability (`:316`) and ledger every model call (`:149`). No production routing code changed in this repair.

Commands run from the repository root after merging main and applying the repairs:

```sh
/workspace/.tervory-cloud/venv/bin/ruff check tank tests --select E9,F --per-file-ignores "tank/skills/base.socials/1.0.0/run.py:F401"
PYTHONPATH=tank /workspace/.tervory-cloud/venv/bin/python -m pytest -q tests/test_tank_one_door.py
PYTHONPATH=tank /workspace/market-lab-gpt-researcher/venv/bin/python -m pytest tests/market_lab_gpt_researcher -q
```

Results: **Ruff: all checks passed** using the CI command's exact scope/options ([output](evidence/ci-repair-lint.txt)); **one-door gate: 27 passed** ([output](evidence/ci-repair-one-door.txt)); **researcher proof: 18 passed**, six warnings from Tank's existing lifecycle/Trigger declarations ([output](evidence/ci-repair-researcher.txt)). All exit 0. The researcher suite uses the real pinned package and actual Tank routing/ledger SQL with offline search/page/model transports and a mocked database connection. No live provider call, deployed check, or green GitHub CI run is claimed.

## What changed

| File and line | Change |
| --- | --- |
| `researcher/requirements.txt:45`, `researcher/Dockerfile:1` | GPT-Researcher **0.16.1**, MIT, with all Python runtime dependency versions pinned, isolated from Tank's dependencies. Fixed Python image version, non-root user, no provider credentials or public host port. The optional build CA mount contains a certificate, not a credential. |
| `researcher/app.py:58`, `researcher/app.py:120` | Local model transport allows only the loopback adapter. The adapter takes tenant/home region from the authenticated run, calls Tank `/v1/route`, and returns Tank usage/ledger receipts. Caller model names, tenant fields and token requests cannot override Tank policy. A Tank refusal cancels upstream research/retries. |
| `researcher/app.py:158`, `researcher/config.json:1` | Uses upstream `GPTResearcher.conduct_research()` and `write_report()`, its planner, SearXNG retriever and context pipeline. No embeddings, source-review model, image generation, MCP tools or alternate search providers. The internal alias `tank` does not select a provider; Tank policy does. |
| `researcher/sources.py:25`, `researcher/sources.py:46` | Restricts the existing upstream SearXNG retriever to `http://searxng:8080/search`. Reuses upstream BeautifulSoup extraction. Only public HTTP(S) search-result pages are eligible, with no redirects, a truthful Tervory user agent, per-host spacing, and bounded searches/page sizes. Blocks stop that host for the request. Search snippets are never evidence. |
| `researcher/app.py:75` | Checks each claim URL against successfully fetched search results and its supporting quote against extracted page text. Supplies actual fetch time, never a model date. Preserves `facts`/`sources` presentation and research-job `answer`/`citations` fields. |
| `researcher/app.py:44`, `researcher/app.py:187`, `researcher/app.py:214` | Separate source registry, researcher and receipts per request. Deletes active state on success, failure and timeout. No research history endpoint or shared report logging. |
| `docker-compose.yml:166`, `docker-compose.yml:178`, `docker-compose.yml:284`, `docker-compose.yml:462` | Adds the service and an internal network shared only with Tank/SearXNG. Separate egress network permits public page reads. The service does not join the default network containing LiteLLM/stores. |
| `tank/market_lab_routes.py:51` | Room-key-only corridor to a fixed service URL; region checked before forwarding. No changes to `run_route`, cache, policy selection, ledger implementation or spend controls. |
| `agents/market_lab/core/research_adapter.py:10`, `agents/market_lab/app.py:92` | Uses the Tank corridor for research jobs. Old Perplexity adapter and tests remain; the job no longer calls it. `tank/research.py` is unchanged. |
| `agents/market_lab/core/http.py:34` | Connects existing Ask after saved-feed lookup. Releases DB connection before research; retains existing no-sources wording when no evidence is found. |
| `agents/market_lab/docker-compose.yml:23` | Passes existing `TANK_REGION` into the room. |
| `tank/market_lab_routes.py:36`, `workspace/lib/tank.ts:1074` | Extends Ask timeout for research; other operations retain prior timeouts. |
| `workspace/app/market-lab/view.tsx:173` | Distinct React keys for multiple claims from one source. No new page text, labels, controls or layout. |
| `tests/market_lab_gpt_researcher/test_researcher.py:149`, `tests/market_lab_gpt_researcher/test_corridor.py:16`, `tests/market_lab_gpt_researcher/requirements.txt:1` | Isolated test environment and 18 offline cases: citations, tenant separation, ledger/cache, full Ask corridor, source boundaries, endpoint overrides, failure handling, free saved-answer path. |
| `tests/test_market_lab_before_deploy.py:166` | Existing unconfigured-research test now stubs the new adapter. Zero-cost/no-sources assertions remain; it no longer stubs the unused Perplexity adapter. |

Upstream: https://pypi.org/project/gpt-researcher/0.16.1/ and https://github.com/assafelovic/gpt-researcher . Downloaded wheel SHA-256: `1c0fe74a1c3319b2ac2caa910808c61b638634d2b75361521e8c4627a8b5a8cf`.

## Initial implementation commands and results (before the main merge)

Commands ran from `/workspace/tervory-tank` unless stated otherwise. **No live model call.** Search, public pages and provider are offline fixtures. Tests use the actual pinned researcher and actual Tank app, auth, `route`, `run_route`, cache logic and ledger SQL. PostgreSQL persistence is replaced at the connection seam; this is not a live database/deployment claim.

Environment setup, all successful:

```sh
/workspace/.tervory-cloud/venv/bin/python -m venv /workspace/market-lab-gpt-researcher/venv
/workspace/market-lab-gpt-researcher/venv/bin/pip install gpt-researcher==0.16.1 uvicorn==0.34.2 pytest==8.3.5 pytest-asyncio==0.25.3
/workspace/market-lab-gpt-researcher/venv/bin/pip install asyncpg==0.30.0 redis==5.2.1 selectolax==0.3.27 reportlab==4.4.9
```

For a fresh clone, use a separate Python 3.12 venv and install `tests/market_lab_gpt_researcher/requirements.txt`, which includes the runtime lock and test dependencies. Do not install this lock into Tank's venv. Tank's test environment skips the package-dependent module if GPT-Researcher is absent; the dedicated run below has **no skips**.

```sh
PYTHONPATH=tank /workspace/market-lab-gpt-researcher/venv/bin/python -m pytest tests/market_lab_gpt_researcher -q
```

**18 passed**, five existing FastAPI lifecycle warnings. [Output](evidence/offline-tests.txt).

```sh
PYTHONPATH=tank /workspace/.tervory-cloud/venv/bin/python -m pytest tests/test_market_lab*.py tests/test_market_research_code.py tests/test_perplexity_research.py -q
```

**204 passed, 4 skipped**, five lifecycle warnings. [Output](evidence/regressions.txt). The skips require local test PostgreSQL: `test_market_lab_postgres.py`, `test_market_lab_real_tank.py`, `test_market_lab_warning_real_tank.py`, and the PostgreSQL policy test in `test_perplexity_research.py`.

```sh
PYTHONPATH=tank /workspace/market-lab-gpt-researcher/venv/bin/python -m pytest tests/market_lab_gpt_researcher/test_researcher.py::test_real_tank_ask_corridor_reaches_room_researcher_and_model_route -q -s --disable-warnings
```

**1 passed**. [Full job output](evidence/real-tank-offline.txt). Tank `/v1/market-lab/ask` calls the real room route, new Tank corridor, actual researcher and Tank `/v1/route`. The offline question returns the BLS fixture URL/fetch time, two distinct ledger IDs, 30 input / 40 output fixture tokens per call, total fixture cost **0.008**, and **0 live model calls**. This is fixture accounting, not actual spend or a price estimate. Concurrent-tenant/cache tests separately prove ownership, new receipts on cache hits, and no cache reuse across tenants.

```sh
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock build --secret id=proxy_ca,src="$CODEX_PROXY_CERT" -t codex-market-research:offline researcher
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock run --detach --name codex-market-research-proof --read-only --tmpfs /tmp:size=64m,mode=1777 codex-market-research:offline
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock exec codex-market-research-proof python -c 'import os, urllib.request; print("uid", os.getuid()); print("health", urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=5).read().decode())'
```

Build/startup succeeded: UID **65532**, health **`{"status":"ok"}`**. [Container evidence](evidence/container.txt). No credentials were supplied to this health-only container. Initial startup exposed source ownership permissions; `COPY --chown` fixed them and the non-root check was repeated successfully.

```sh
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock compose -f docker-compose.yml config --no-interpolate --quiet
git show bde4578:docker-compose.yml > /workspace/market-lab-gpt-researcher/main-baseline/docker-compose.yml
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH docker --host=unix:///var/run/docker.sock compose -f /workspace/market-lab-gpt-researcher/main-baseline/docker-compose.yml config --no-interpolate --quiet
```

Both Compose checks exit **1** on the unchanged `services.agent-roles.exclude_from_hc` property, which this Docker Compose version rejects. [Branch](evidence/compose-validation.txt), [main](evidence/main-compose-validation.txt). That existing setting was not changed. The standalone image build and startup above passed; deployment through the founder's stack has not been tested.

```sh
/workspace/.tervory-cloud/node-v22.23.4-linux-x64/bin/node workspace/node_modules/typescript/bin/tsc --project workspace/tsconfig.json --noEmit --incremental false
```

Exit **2**: existing Tiger `plugins-data.test.ts:3` TS5097 (`.ts` import without `allowImportingTsExtensions`). [Branch output](evidence/workspace-types.txt). Stale `.next` output from a previous branch was moved outside the checkout first.

Baseline exported with `git archive bde4578 workspace | tar -x -C /workspace/market-lab-gpt-researcher/main-baseline`, using the same `node_modules` and generated `next-env.d.ts`. In `/workspace/market-lab-gpt-researcher/main-baseline/workspace`:

```sh
/workspace/.tervory-cloud/node-v22.23.4-linux-x64/bin/node node_modules/typescript/bin/tsc --noEmit --incremental false
```

Exit **2**, the same Tiger TS5097 and no other errors. [Main output](evidence/main-workspace-types.txt). No Tiger source/configuration changed. With only a command-line allowance for that existing import:

```sh
/workspace/.tervory-cloud/node-v22.23.4-linux-x64/bin/node workspace/node_modules/typescript/bin/tsc --project workspace/tsconfig.json --noEmit --incremental false --allowImportingTsExtensions
git diff --check
```

Both exit **0**. No CI run was requested/retried and no GitHub API was used.

## Founder acceptance still required

No founder browser session is available to this task. No founder screenshot, live answer, live ledger cost or deployment is claimed. The job output is **local, fixture pages**. Tests passing is not the founder's definition of done.

After the founder deploys the main stack, Market Lab room and Workspace changes, Claude should capture the founder asking a market question needing web research, the answer's source/fetch-time rows, and corresponding costs on that tenant's ledger. Those screenshots remain the outstanding rule 11 proof. The service reuses existing `TANK_KEY_MARKET_LAB`; no new key names/values are needed. Existing Tank policy and paid-work controls still decide whether a model request can run. No merge is requested.
