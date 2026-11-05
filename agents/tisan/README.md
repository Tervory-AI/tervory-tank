# Tisan

Tisan is the developer and the designer. It builds and checks the work a tenant has asked for.

## Room

Own Coolify resource. Base directory `/agents/tisan`. Compose location `/docker-compose.yml`. No public domain. Predefined network: isolated network only.

Standard room, same pattern as the template. Its corridor is `tervory-gw-tisan`, reaching Tank, Postgres, and Hermes. Its only additional network is the internal `figma_internal` link to `figma-egress-proxy`. Only that proxy is declared on `egress`. The external `tervory-gw-tisan` network is an ordinary bridge, so this is not a network-level egress seal. The dedicated proxy constrains the Figma reader's code path.

Login `agent_tisan`. Schema `agent_tisan`. Key `TANK_KEY_TISAN` on Tank and on Hermes.

The image installs Node and fills an npm cache while it builds. A scaffold run uses that cache with `npm ci --offline`, so the check does not need the internet.

The room has 1g of memory and 0.25 CPU. A scaffold job is allowed 10 minutes. Other jobs, and other agents, stay on the chassis default of 2 minutes.

## Project scaffold

Skill `tisan.scaffold` (job kind `scaffold`). Input:

```json
{
  "name": "Northwind",
  "slug": "northwind",
  "pages": ["home", "about", "contact", "privacy"],
  "locale": "en",
  "brand": {
    "colours": {"ink": "#001840", "paper": "#F4F6FB", "accent": "#E80008", "line": "#B8BFD0"},
    "fonts": {"heading": "Jost", "body": "Inter"},
    "logo_url": "https://cdn.example/logo.svg"
  }
}
```

The tenant is the job's `tenant_id`. Brand colours and fonts become CSS variables and Tailwind tokens. Pages use those tokens. The contact form posts to `/api/contact`, which accepts the message and does not store it. There is no analytics and no third-party script.

Before it returns, the room runs `npm ci`, `npm run lint`, `npm run build`, and `npm test`. The project is stored at `/data/builds/<tenant>/<slug>/<n>.tar.gz` with a manifest: `files`, `token_set`, and `checks`.

The generated project also carries a GitHub Actions gate. That gate runs ESLint, `tsc`, the unit tests, the production build, Playwright at 390px, 768px, and 1440px (including axe-core), and Lighthouse CI. Performance, accessibility, best practices, and SEO must each score 90 or above. Those browser checks run in GitHub Actions. The room does not launch a browser.

`npm run deploy` reads the HTML that build wrote. It refuses to continue until every saved page has a privacy notice, and a cookie notice when that page loads a script or frame from another site. It does not fetch a page. A web address is not a saved page. The command does not publish the site.

## Figma reader

Skill `tisan.figma` (job kind `figma`). It reads one page and returns named colour, type, and spacing tokens as CSS custom properties, a Tailwind config that points at those properties, and a component manifest. A value that disagrees with itself is listed under `conflicts` and left out of the tokens. A state a component does not have is listed under `gaps` and is not invented.

```json
{
  "file_key": "ksi7ctRwEnN8wbip1yfuhL",
  "node_id": "0:1"
}
```

`file_key` defaults to the Tervory file. `node_id` defaults to page `0:1`, "Landing — Desktop & Mobile". `2:11` is the desktop frame and `6:45` is the mobile frame. The tenant is the job's `tenant_id`. The reading is stored at `/data/readings/<tenant>/<file_key>/<node>.json`.

Live reads require explicit trusted dispatch plus the founder's `FIGMA_TOKEN` and `TISAN_FIGMA_FILES`, both filled in by name in Coolify. The latter is a comma-separated list of `<tenant id>=<file key>` pairs; only a pair matching the dispatched tenant permits a live request. The recorded Tervory fixture remains available when that file is unpaired, even if a token is configured. Payloads cannot choose a token, proxy, host, tenant identity, or enable live mode.

The reader makes at most two GETs: the requested node and local variables at `api.figma.com`, using `X-Figma-Token` through the fixed `figma-egress-proxy:8080` proxy. Environment proxies are ignored; redirects and retries are disabled. Each request has a 20-second wall-clock deadline and a 5 MB decoded-response ceiling. This proxy instance also has a 5,000,000-byte tunnel limit; the Radix class defaults and its other callers are unchanged. Existing proxy rate/concurrency limits still apply. Its only allowed host is `api.figma.com`, with SNI checked and storage access disabled. No raw response, header, or token is logged or stored; only the compiled tenant reading is saved.

Figma restricts the [Variables REST API](https://developers.figma.com/docs/rest-api/variables/) to Enterprise access (see the [local variables endpoint](https://developers.figma.com/docs/rest-api/variables-endpoints/)). A variables 403 still reads the node with `variables_payload=None`: `collections_known` stays false and missing values remain gaps. Other HTTP errors, timeouts, malformed data, and oversized bodies return the fixed `Figma request failed` error. Without a token, only the recorded Tervory fixture `agents/tisan/fixtures/tervory-landing.json` remains available for offline builds and tests.

The managed room data volume remains unchanged. The optional brain/browser/sandbox now require Raw Compose Deployment; preserve the current project identity when enabling that mode. This requirement comes from the private tools, not the Figma reader. The `brain` profile remains disabled and `TISAN_BRAIN_ENABLED` defaults to false. The founder checks the gateway network with `docker network inspect -f '{{.Internal}}' tervory-gw-tisan`. The reader's fixed proxy, host and SNI checks constrain its code path; they do not establish network-level isolation for the whole room. The seal checker requires exact declared Tisan/proxy attachments and reports any extra network as a leak. Deployment routing is unchanged: `.github/scripts/deploy_changed.py:wanted` maps this compose to `agent-tisan`; `.github/scripts/room_setup.py` selects `/agents/tisan/docker-compose.yml`. The room image keeps its repository-root context, and the proxy uses `context: ..` with `dockerfile: radix/Dockerfile`, resolving all COPY sources under `agents/`.

`execute()` defaults to `live=False`. Approved `1.0.0` and `1.0.1` wrappers therefore remain offline even with a paired token. The room's authenticated `/evals/run` parses its version and allows live mode only for `1.1.0` or later. The versioned `1.1.0` wrapper explicitly opts in. The ordinary `figma` job handler remains `live=False` until Tank supplies the approved version in a server-controlled field; caller input is never that authority. The seven real room eval cases use the platform UUID tenant: six copied verbatim from `1.0.1`, plus an unpaired-file refusal. Paired REST and variables-403 checks stay in offline pytest, outside Skala's cases file.

Skill `tisan.figma/1.1.0` awaits founder approval in Skala; earlier versions are untouched.

### Historical J2 gate 1 verification (3 Nov 2026)

The review corrections above supersede the historical Raw Compose/volume instructions and nine-case eval result below. The current review evidence is in `tests/tisan_j4/PR.md`; the reader job intentionally remains offline pending trusted Tank version dispatch.

Ran from `/workspace/codex-tisan-w3`, branch `codex/tisan-w3`, Python 3.12.16. No live job, model call, deploy, production SQL, or live-data mutation was performed. The local HTTPS tests use test-only TLS material and placeholder credentials. The REST eval payload adapts the saved MCP recording and does not claim a fresh Figma REST capture.

Commands and results:

```bash
.venv/bin/python -m pytest tests/test_tisan_figma_live.py -q --disable-socket --allow-hosts=127.0.0.1,localhost --maxfail=1
# 23 passed; includes Skala's evaluator: 9/9 cases, eligible=true, score=1.0, cost_usd=0, no model calls.

TISAN_TEST_PLAYWRIGHT=/workspace/codex-tisan-w3/.venv/tisan-browser/node_modules/playwright PLAYWRIGHT_BROWSERS_PATH=/home/ammosync/.cache/ms-playwright .venv/bin/python -m pytest tests/test_tisan_*.py tests/tisan_promotion/ tests/test_c10_rooms.py tests/test_secrets.py -q -rs --disable-socket --allow-hosts=127.0.0.1,localhost
# 284 passed, 16 skipped, 15 existing warnings, 86.39s.
# Skips: 14 optional local/CI PostgreSQL cases and 2 opt-in npm build cases.
# Existing Chromium promotion tests are enabled and pass.

.venv/bin/python -m pytest tests/test_room_seal.py::test_raw_compose_files_need_nothing_from_coolify -q --disable-socket --allow-hosts=127.0.0.1,localhost
# 7 passed.

node --test tests/tisan_gold_actions.test.cjs
# 1 passed.

docker compose --env-file /dev/null -f agents/tisan/docker-compose.yml config --no-interpolate --quiet
# Exit 0. Compose validation only; a new Docker image was not built here.

git diff --check origin/main...HEAD
# Exit 0.
git diff --exit-code origin/main HEAD -- agents/radix/Dockerfile agents/radix/egress.py tank/skills/tisan.figma/1.0.1
# Exit 0: Radix and the approved skill version are unchanged.
```

The initial wider run (`.venv/bin/python -m pytest tests/test_tisan_*.py tests/tisan_promotion/ tests/test_c10_rooms.py tests/test_room_seal.py tests/test_secrets.py -q --disable-socket --allow-hosts=127.0.0.1,localhost --maxfail=3`) produced 384 passed, 19 skipped, and 2 failures: TypeScript was absent for an existing Node test, and Raw Compose required a pinned volume name. Both were corrected; the commands above recheck each failure. Earlier collection attempts needed the existing dependencies installed, including pinned `selectolax==0.3.27` and `jiter==0.18.0`. The new integration tests initially exposed a missing compiled `collections_known` field; it was fixed and the final checks above pass. Test dependencies live only in ignored `.venv/` and `workspace/node_modules/`; repository manifests were not changed.

Read-only live mount/config proof:

```bash
docker ps -q --filter label=com.docker.compose.service=agent-tisan | xargs -r docker inspect --format '{{range .Mounts}}{{if eq .Destination "/data"}}{{.Type}} {{.Name}}{{end}}{{end}}'
# volume lblbn0wjaz30hhdur9l3pylg_agent-tisan-data

docker ps -q --filter label=com.docker.compose.service=agent-tisan | xargs -r docker inspect --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}} {{index .Config.Labels "com.docker.compose.project.config_files"}}'
# /artifacts/fdy2ohg2htosrx6zha51gi0e/agents/tisan /artifacts/fdy2ohg2htosrx6zha51gi0e/agents/tisan/docker-compose.yml
```

`test_deploy_routing_and_all_proxy_copy_sources_resolve` extracts and executes the existing `deploy_changed.py:wanted` function without importing its credential-bearing module setup: this compose maps to `(False, {'agent-tisan'}, False)`. It also verifies the room setup paths and every local Radix Dockerfile COPY source under `agents/`. The complete gate includes `tank/skills/`, so deploy-on-merge also selects the main/ZA stacks and Tisan regional copies according to its existing rules. No deployment logic was changed. Both requested topology tests now assert the exact room/proxy/network membership.

Pending after review: Claude opens the PR; final-head Tank/Workspace CI results must be recorded there. The founder approves `tisan.figma/1.1.0`, supplies `FIGMA_TOKEN` and `TISAN_FIGMA_FILES` in Coolify, and deployment retains the original compose mode and data volume. Founder-browser acceptance and screenshots are still pending: run `tisan.figma` through the existing `/chats` Confirm card for a paired page and an unpaired file in the founder's workspace. The local intercepted browser tests are regression evidence, not that acceptance proof. No PR was opened or merged by this builder.


The recorded page has no spacing variables, no font family, weight, or line height, and the Button component has no hover, active, disabled, or error state. Those are gaps. The reader does not fill them in.

## Visual review

Saved Figma readings now retain `frame_data` and any recorded `visual` mappings
(boxes, text, token colours and selectors). The reader does not invent missing
measurements. The existing 390px/mobile recording remains incomplete for the
375px gate. Capture the real 375px frame before using it for this check.

A scaffold input with `figma: {file_key, node_id}` copies that tenant's saved
visual evidence into `visual/frames.json`. The generated project's existing
Playwright CI runs these comparisons; incomplete evidence fails with
`frame data incomplete`. A generic scaffold with no Figma reference has no
comparison target. `npm run test:visual` explicitly requires recorded data and
fails if it is absent. See the template's `visual/README.md` for the mapping
schema and scoring rules. No model call, external screenshot service or new
runtime dependency is added. No logo is drawn or replaced.

## What Tisan never does

- Deploy anything to production without a Radix scan result of "no critical findings".
- Deploy the starter site when a saved page has no privacy notice, or loads a script or frame from another site without a cookie notice.
- Hold model keys. Every model call goes through Tank.
- Push to a client's repo without that tenant's approval recorded.

## Gold approvals and candidates

A successful scaffold job can include `figma: {file_key, node_id, page}` (`page`
is home/about/contact/privacy). Save the Figma reading first. The checked static
HTML, CSS and page structure are retained under the tenant's builds directory;
a stable per-page review reference is saved under `/data/reviews/<tenant>/`.
Rebuilding the page replaces that reference and invalidates its previous approval.
No approval is seeded.

The Tisan page loads platform pages and the active organization’s pages beside
sandboxed built-page previews. Approval scope is limited to those two tenants.
Only signed-in founders in `TERVORY_ADMIN_USER_IDS` can use **Approve as gold**.
The server action derives the tenant and user from Trigger sign-in, calls Tank through
`workspace/lib/tank.ts`, and Tank verifies the Workspace key and founder again
before forwarding to the fixed Tisan corridor. The room also requires its own
key and the same founder allowlist. Configure the existing founder-id setting
on the Tisan room; it is now passed through its compose file.

The additive, idempotent `agent_tisan.page_approvals` table is created at room
startup. It stores tenant, file/frame ids, saved frame hash, built page path and
hash, founder user id and approval time. Approval rejects a stale review (409).
`GET /gold/candidates?limit=N` is room-key only. It returns both skills only
while both hashes and source identities still match. Each row's `label_family`
is `founder-approved-page:YYYY-MM`, taken from the approval time. A new month
is a new family. A page marked synthetic uses a family whose name contains
`synthetic`. An approval with no usable time is not emitted.
`tenant_id` defaults to the platform tenant; supply the tenant explicitly for
private records. Every database read/write is tenant scoped. Private builds
remain `public: false`; no client page becomes exportable by approval alone.
The response is capped by GOLD_AUTO_MAX (default 200), with nightly scheduling
and deduplication owned by the collector. Nothing here trains or promotes a model.

No approved examples are seeded. Incomplete existing frames remain incomplete;
the visual-check PR adds full frame evidence and refuses missing measurements.
The review iframe blocks scripts and external assets, and the raw frame evidence
is also available. Never put credentials in generated pages or saved frames.
