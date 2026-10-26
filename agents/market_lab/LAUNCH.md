# Market Lab local review

Branch: `codex/market-lab-works`. Keep the PR draft.
The evidence below comes from a clean clone of implementation commit `5639cae`,
fresh Python and JavaScript dependencies, and a new empty local Postgres database.
It covers fixtures only. Finding 5, the client's own signed-in session, is outside
this brief and remains under **Founder must decide**.

## The job, step by step, as a client does it

Intended client journey; the signed-in journey has not been verified here:

1. Open `/market-lab` in the client's workspace and choose **Refresh feeds**.
2. Read **On**, which counts feeds with observations retained by their latest collection. Missing keys show **Off, needs key**; blocked sites show **Off, blocked**.
3. Ask a question about a stored feed. The local proof uses “What are the latest population figures for California?”
4. Read the brief and open each linked statement. Its stored document shows the observation, place name, date, value and unit.

## What changed

- `agents/market_lab/core/jobs.py:39`, `core/evidence.py:22` and `schema.sql:137` store tenant-owned source documents and collection results. Fixtures cover all 14 copyable feeds. Answers use saved rows and stable citations. The legacy model-calling `/api/market-lab/chat` route is deleted.
- Review finding 1: `agents/market_lab/feeds/geo.py:77` handles both county-producing title patterns: Census population and active listings. Alameda, Los Angeles and Harris are named with their states. Tests enumerate every county row produced by the complete fixture run.
- Review finding 2: `agents/market_lab/feeds/presentation.py` formats count-dependent units for both answers and source pages: **1 listing**, **2 listings**, **1 person**, **2 people**, and the other stored units. Source units remain unchanged in storage.
- Review finding 3: `agents/market_lab/core/evidence.py:97` selects the last stored version for each observation/date. Answers use that version. `workspace/app/market-lab/source-view.tsx:5` labels **Current figure (acs-v2)** and **Earlier figure (acs-v1)** while retaining old row anchors. Tests cover immutable originals, older citations, page boundaries and a later version that returns to an earlier value.
- Review finding 4: `agents/market_lab/core/http.py:19` and `core/evidence.py` receive the engine from their caller, with a default of `None`. Unconfigured refresh/overview requests fail without a database write. `agents/market_lab/app.py` supplies its selected engine's plan. Tests check a different caller-supplied engine, the queued job payload and the absence of every engine name in all core Python files.
- Client-text review: `workspace/app/market-lab/view.tsx`, `plugins.ts`, `plugin-actions.ts`, `vault-server.ts`, `quarantine-view.tsx` and `feeds/presentation.py` replace internal errors and unexplained codes with plain words. Search now names and filters the feeds and linked pages it actually searches; saved keys say **Key provided**; connection statuses explain when sign-in is needed; file/page counts use singular forms; the review panel formats its dates. Publisher notices and licence text remain intact.
- `tank/main.py` and `tank/Dockerfile` remain unchanged from their approved `73be8e6` versions. Changes to `workspace/lib/tank.ts` remain limited to Market Lab's types/helper.

**Decisions I made**

- Treat collection order as revision order, matching how the source adapters append versions. Do not sort version labels as text or assume the largest number is newest. Compute the current version across the whole document before paging. Retain earlier figures with explicit labels and stable citation links.
- Format names and units for display while preserving the original title, geographic code, unit, value and revision in storage. Translate climate codes into measurement names; identify numeric categories as source categories rather than guessing their meaning.
- Keep engine selection in the room caller. Core has no implicit industry or engine name. No model, paid service, key or replacement endpoint is added.
- Review the page, answer/empty/error states, source pages, Plugins tabs and founder feed-review text. The browser proof opens all fourteen saved source documents and checks both population and listing questions; it does not claim authenticated Plugins or founder actions.
- Follow the existing public-page rule: truthful Tervory identity, per-host pacing, stop blocked hosts, skip missing named keys. Live availability is not claimed.
- Keep the fixture proof isolated and labelled **local, fixture page**. Its test entry points supply a fixed tenant; production sign-in entry points are unchanged. The PR stays draft, and finding 5 from the first review remains outside this brief.

## How it was tested

Run on a cloud machine. Prerequisites: Git, Python 3.12 with venv, Node 24/npm,
Docker with the local socket available, and Chromium at `/usr/bin/chromium`.
The clean run used Python 3.12.14, Node 24.19.0, Docker 28.4.0 and Chromium 154.0.8037.57.
An installed Chromium at another path can be passed with `--browser`.

**Fresh-clone setup**

```bash
git clone --branch codex/market-lab-works https://github.com/zenascapetown-code/tervory-tank.git tervory-tank-review
cd tervory-tank-review
python3 -m venv .venv
.venv/bin/python -m pip install -r agents/market_lab/fixture_proof/requirements.txt
npm_config_cache=/tmp/market-lab-review-npm npm --prefix workspace install --no-package-lock --no-audit --no-fund
npm_config_cache=/tmp/market-lab-review-npm npm --prefix agents/market_lab/fixture_proof install --no-package-lock --no-audit --no-fund
```

The validation checkout was cloned locally from the same Git commit before it was pushed. Both dependency installations started empty. The explicit npm cache keeps writes within the cloud workspace's permitted temporary directory.

**Offline product tests** — from the repository root:

```bash
PYTHONPATH=tank .venv/bin/python -m pytest -q tests/test_market*.py tests/test_feeds*.py
```

Result: **174 passed, 1 skipped, 5 warnings**. The skipped test requires a local database and passes separately below. The 13 TypeScript model tests run within this suite. The warnings are existing FastAPI startup-handler deprecations.

**Empty local Postgres** — this temporary database contains no production data or credentials. The published port is loopback only:

```bash
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
  docker --host=unix:///var/run/docker.sock run --detach \
  --name market-lab-review-postgres --publish 127.0.0.1:54330:5432 \
  --env POSTGRES_HOST_AUTH_METHOD=trust --env POSTGRES_DB=market_lab_review_test \
  --tmpfs /var/lib/postgresql/data \
  postgres@sha256:9e2cf6287f25c3151f4c9421ccce2b17f3e60061c111a29165e0d2cdd9ff0a97
```

Wait until this reports `accepting connections`:

```bash
env -u DOCKER_HOST -u DOCKER_CONTEXT -u DOCKER_TLS -u DOCKER_TLS_VERIFY -u DOCKER_CERT_PATH \
  docker --host=unix:///var/run/docker.sock exec market-lab-review-postgres \
  pg_isready -U postgres -d market_lab_review_test
DATABASE_URL=postgresql://postgres@127.0.0.1:54330/market_lab_review_test PYTHONPATH=tank \
  .venv/bin/python -m pytest -q tests/test_market_lab_postgres.py
```

Result: **1 passed**. The test applies the schema twice, stores all 14 fixture feeds, reads cited records, denies another tenant, excludes fixtures from production reads and preserves earlier documents. Its writes roll back.

**Production build**:

```bash
cd workspace
NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_ZHVtbXkuY2xlcmsuYWNjb3VudHMuZGV2JA== CLERK_SECRET_KEY=sk_test_dummy npx next build
cd ..
python3 - <<'PY'
import json
from pathlib import Path
manifest = json.loads(Path('workspace/.next/server/app-paths-manifest.json').read_text())
assert '/api/market-lab/chat/route' not in manifest
assert '/market-lab/ask/route' in manifest
print('Legacy chat route absent; stored-evidence ask route present.')
PY
```

Result: **build passed**, including type checking; **route assertions passed**. The values in the build command are the brief's dummy build values. No sign-in was attempted.

**Local page and screenshots** — from the repository root:

```bash
DATABASE_URL=postgresql://postgres@127.0.0.1:54330/market_lab_review_test \
  .venv/bin/python agents/market_lab/fixture_proof/run.py
```

After the local page reports ready, run in a second cloud terminal at the same repository root:

```bash
node agents/market_lab/fixture_proof/capture.mjs --browser /usr/bin/chromium
```

Result: **Local fixture page: 12 screenshots, 7 exact citations, no external browser requests or errors.**
The page is `http://127.0.0.1:3046/market-lab`. The fixture server first stores the saved feed inputs in Postgres; browser requests then read those records. The capture rejects external browser requests and checks:

- 14 On cards and correct singular/plural observation counts;
- both population and active-listings questions submitted through the local page;
- every number in the answer inside a source link;
- every citation in both answers opening with matching title, date, value and displayed unit;
- all fourteen source documents opening, county names present on listing rows, singular listing units, and current/earlier population revisions clearly labelled;
- readable collection timestamps and place names, and no heading over an empty downloads list;
- screenshots at 375px and 1440px, each carrying the local-fixture label.

Ctrl-C stops the runner and both local services. Stop/remove only the `market-lab-review-postgres` test container when finished; its temporary database is disposable.

## Proof

These are **local, fixture page** captures from the clean checkout, not a signed-in or live-data proof.

| Step | 375px | 1440px |
| --- | --- | --- |
| Feed page | [Feeds](evidence/feeds-375.png) | [Feeds](evidence/feeds-1440.png) |
| Entered question | [Question](evidence/question-375.png) | [Question](evidence/question-1440.png) |
| Cited brief | [Brief](evidence/brief-375.png) | [Brief](evidence/brief-1440.png) |
| Population source and revisions | [Source](evidence/source-375.png) | [Source](evidence/source-1440.png) |
| Listing brief | [Listing brief](evidence/listing-brief-375.png) | [Listing brief](evidence/listing-brief-1440.png) |
| County and listing source | [Listing source](evidence/listing-source-375.png) | [Listing source](evidence/listing-source-1440.png) |

[Browser receipt](evidence/browser-proof.json) records the actual source identifiers and rendered rows. Local fixture tenant: `00000000-0000-0000-0000-000000000905`. The values 110 and 50 people are saved test inputs, not real population claims. Each new run creates new stored-document identifiers and timestamps; use that run's receipt.

## Founder must decide

**Finding 5 — client's own session:** outside this brief. Claude owns signed-in proof in the founder's browser after the founder deploys. No test access is requested, and this PR does not claim that proof is complete.

**Live feeds:** Grok owns this run in the Market Lab room with its existing database and named feed-key environment bindings:

```bash
python -m feeds run --engine ffl --tenant '<the signed-in workspace tenant UUID>' --live --backfill
```

Use the workspace UUID derived by `workspace/lib/tenant.ts`. Do not pass secret values as arguments. Live source availability is not verified by the fixture run. Missing keys remain off and are skipped; blocked sites are recorded and stopped.

After deploy, Claude checks `/market-lab`: start a refresh, verify the queued job completes and the page updates, ask, open each `/market-lab/sources/<UUID>?row=<index>#point-<index>`, then switch workspace and confirm access is denied. `POST /v1/market-lab/overview` must match the page's On count and the tenant's latest `agent_market_lab.feed_checks` rows. Check `agent_market_lab.feed_documents` with `fixture = false`: each linked statement must match that document's tenant, date, value and unit.
