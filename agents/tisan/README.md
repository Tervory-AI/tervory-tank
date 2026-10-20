# Tisan

Tisan is the developer and the designer. It builds and checks the work a tenant has asked for.

## Room

Own Coolify resource. Base directory `/agents/tisan`. Compose location `/docker-compose.yml`. No public domain. Predefined network: isolated network only.

Standard room, same pattern as the template. The only corridor is `tervory-gw-tisan`. Tisan can reach Tank, Postgres, and Hermes. Nothing else joins that corridor.

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

The room's only network is `tervory-gw-tisan`. A live Figma call would need a route to the public internet, and this room does not get one. The reader uses the recorded fixture `agents/tisan/fixtures/tervory-landing.json`, captured from the Figma connection on 17 Oct 2026. It does not call Figma. The fixture has the resolved variable values and no collection names. `FIGMA_TOKEN` is a name in `.env.example` only. The room does not receive it.

The recorded page has no spacing variables, no font family, weight, or line height, and the Button component has no hover, active, disabled, or error state. Those are gaps. The reader does not fill them in.

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
The server action derives the tenant and user from Clerk, calls Tank through
`workspace/lib/tank.ts`, and Tank verifies the Workspace key and founder again
before forwarding to the fixed Tisan corridor. The room also requires its own
key and the same founder allowlist. Configure the existing founder-id setting
on the Tisan room; it is now passed through its compose file.

The additive, idempotent `agent_tisan.page_approvals` table is created at room
startup. It stores tenant, file/frame ids, saved frame hash, built page path and
hash, founder user id and approval time. Approval rejects a stale review (409).
`GET /gold/candidates?limit=N` is room-key only. It returns the requested six
fields for both skills only while both hashes and source identities still match.
`tenant_id` defaults to the platform tenant; supply the tenant explicitly for
private records. Every database read/write is tenant scoped. Private builds
remain `public: false`; no client page becomes exportable by approval alone.
The response is capped by GOLD_AUTO_MAX (default 200), with nightly scheduling
and deduplication owned by the collector. Nothing here trains or promotes a model.

No approved examples are seeded. Incomplete existing frames remain incomplete;
the visual-check PR adds full frame evidence and refuses missing measurements.
The review iframe blocks scripts and external assets, and the raw frame evidence
is also available. Never put credentials in generated pages or saved frames.
