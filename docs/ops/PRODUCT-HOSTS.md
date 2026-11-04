# Product hosts (*.tervory.com)

One product per host. `app.tervory.com` stays the client workspace. Marketing stays on apex `tervory.com`.

## Workspace hosts (same Coolify service as `app.tervory.com`)

| Host | Lands on | Product |
| --- | --- | --- |
| protect.tervory.com | `/autumbra` | Autumbra (Watch / Enforce) |
| autumbra.tervory.com | `/autumbra` | Autumbra |
| zenas.tervory.com | `/moot` | Zenas (Moot watch home; `/zenas` panel deep link) |
| base.tervory.com | `/base` | Base |
| tiger.tervory.com | `/tiger` | Tiger |
| market-lab.tervory.com | `/market-lab` | Market Lab |
| tisan.tervory.com | `/tisan` | Tisan |
| radix.tervory.com | `/radix` | Radix |
| rig.tervory.com | `/rig` | Rig (shared with the existing agent API/widget paths below) |
| skala.tervory.com | `/skala` | Skala (founder) |
| tank.tervory.com | `/tank` | Tank (founder) |

Routing is app-level: `workspace/lib/product-hosts.ts` + `workspace/middleware.ts` rewrite `/` on those hosts. Deep links, `/sign-in`, `/sign-up`, `/api/health`, `/autumbra` (public product), and `/moot` (public watch) are not rewritten away. Legacy `/admin/ghost` still redirects to `/admin/autumbra`.

**Moot is part of Zenas.** Canonical URLs are on `zenas.tervory.com` (`/moot`, `/moot/[match]`, `/zenas`). Hitting `app.tervory.com/moot*` returns **308** to the matching path on `zenas.tervory.com`. Do not treat Moot as a primary surface on the client workspace host.

User-facing copy on Autumbra hosts: **Autumbra** / Watch / Enforce only — never Ghost or Wraith.

## Separate services (do not attach to workspace, except shared Rig)

| Host | Service |
| --- | --- |
| rig.tervory.com | Shared: Workspace app pages plus agent-rig widget/API paths (inventory below) |
| mcp.tervory.com | mcp |
| coolify.tervory.com | Coolify UI |
| tervory.com / www | site / Worker marketing |

## Coolify cutover (production, Boston)

Public product hosts are extra domains on the Coolify application that already serves `app.tervory.com`. They are not new applications. Rig is the exception: its host stays on agent-rig as well as Workspace, with the path split below. Other agent rooms do not get these hosts.

Routing uses `workspace/lib/product-hosts.ts` and `workspace/middleware.ts`. The Rig split additionally requires the matching `agents/rig/docker-compose.yml` routers. This note does not create DNS records or Coolify domains. The founder attaches domains in Coolify and merges. No secret values belong in git, in this note, or in the pull request.

### Where each host goes

| Host | Coolify application | Service | Port |
| --- | --- | --- | --- |
| app.tervory.com | Boston stack (`docker-compose.yml`), the app that already has this host | `workspace` | 3000 |
| protect.tervory.com (Autumbra) | **same application, same `workspace` service** | `workspace` | 3000 |
| autumbra.tervory.com | same | `workspace` | 3000 |
| zenas.tervory.com | same | `workspace` | 3000 |
| base.tervory.com | same | `workspace` | 3000 |
| tiger.tervory.com | same | `workspace` | 3000 |
| market-lab.tervory.com | same | `workspace` | 3000 |
| tisan.tervory.com | same | `workspace` | 3000 |
| radix.tervory.com | same | `workspace` | 3000 |
| skala.tervory.com | same | `workspace` | 3000 |
| tank.tervory.com | same | `workspace` | 3000 |
| rig.tervory.com (app pages) | **same application as app.tervory.com** | `workspace` | 3000 |
| rig.tervory.com (reserved paths below) | **agent-rig**, keep the existing domain too | Rig public API/widget | 8000 |
| mcp.tervory.com | Boston stack, not workspace | `mcp` | 8000 |
| tervory.com / www | Boston stack, not workspace | `site` | 3000 |
| coolify.tervory.com | Coolify's own UI | — | — |

`protect.tervory.com` is the Autumbra host. The page copy is Autumbra / Watch / Enforce. The Coolify resource for the sealed room stays `agent-ghost` (folder `agents/ghost`) and its domain list stays empty. Do not rename that resource in order to hang the public host on it.

### Do not attach these hosts to agent rooms

Issue #314's first map put each product on its own room. That map is wrong. Do not add any workspace host to:

- agent-ghost (Autumbra room) — no public domains
- agent-zenas, agent-base, agent-tiger, agent-tisan, agent-market-lab, agent-radix
- agent-rig, except the existing `https://rig.tervory.com`

`agents/rig/docker-compose.yml` already names `rig.tervory.com` on the rig routers. Do not add protect, autumbra, zenas, or the other workspace hosts to those rules.

### Shared Rig path inventory (from the shipped code)

`agent-rig` has explicit HTTP and HTTPS routers matching `Host(rig.tervory.com)`
**and** the following path matchers, both at priority **1000**. All other paths
fall through to Workspace's host router (priority below 1000; normally its
automatic host-rule priority). No prefix stripping, path replacement, auth or
CORS change is applied to these agent requests. Query strings and request bodies
are preserved. See [Traefik rule priority](https://doc.traefik.io/traefik/reference/routing-configuration/http/routing/rules-and-priority/).

| Paths retained on agent-rig | Code / existing consumer |
| --- | --- |
| `/v1/rig` and `/v1/rig/*`, including OPTIONS | `rigbox/api.py`: search, products, setups, swap, graph, compare, Ask, privacy notice, quote/link-quote, search-events, Locate and admin fits/supply. The shipped widget bundle calls these paths. |
| `/v1/rig/admin/*` | Quote analytics, delivery/retry/resume/attention, embed-key issuance, supplier receipts, commerce and 3D APIs; these remain APIs, separate from the Workspace admin pages. |
| `/v1/rig/cart/*`, `/v1/rig/commerce/webhooks/{tenant_id}` | `rigbox/cart_api.py`: store cart operations and signed Shopify/WooCommerce/BigCommerce callbacks. |
| `/v1/rig/3d/*` and `/v1/rig/internal/3d/*` | `rigbox/three_d/api.py` and `internal.py`: entitlement/approved-model/assembly/quote/kiosk APIs; existing authentication remains required. |
| `/widget`, `/widget/*` | `rigbox/quotes/keys.py` emits `/widget/assets/{manifest.file}` and `api-base="https://rig.tervory.com"`. `hosting.py` serves `/widget/manifest.json`, immutable `/widget/assets/*`, `/widget/fonts/*` (CSS/WOFF2) and **`/widget/test`**. |
| `/3d`, `/3d/*` | `rigbox/three_d/asgi.py`: existing test page, `/3d/config`, runtime/model-viewer chunks and Basis JS/WASM assets. No new viewer entry or GPU path is enabled. |
| `/page`, `/page/*` | `rigbox/page_route.py`: existing catalogue/dealer JS/CSS/logo, v5 assets and immutable hash-addressed asset URLs. |
| `/product`, `/product/*`, `/cn-classic`, `/house`, `/v5`, `/v5/*` | `page_route.py`: existing product deep links, legacy catalogue aliases and v5/CN pages, retained for store links. |
| `/storage`, `/storage/*` | Existing chassis storage APIs, including model/photo object paths and usage; their authentication is unchanged. |
| `/health` (exact) | Existing agent health check. `/api/health` belongs to Workspace. |

Path prefixes include a slash boundary: `/widget-extra`, `/3d-extra`,
`/page-extra` and `/v1/rig-extra` do **not** match the agent router. `/` rewrites
inside Workspace to `/rig`; `/admin` and `/admin/*` rewrite to `/rig/admin` and
`/rig/admin/*`. Existing `/rig/*`, `/rig-cart/*`, `/_next/*`, sign-in/up and
Workspace API paths stay in Workspace. Trigger sign-in still protects private Rig pages.
The room's old `/` and `/admin` HTML routes remain available internally but no
longer own those public host paths. Internal room-host calls are unchanged.

The raw Compose agent routers must be the only agent-rig routes on this host:
an extra broad `Host(rig.tervory.com)` agent router would capture app pages.
Keep the domain on agent-rig, but remove any obsolete/generated catch-all agent
router from its saved labels if present. Do not remove the reserved-path routers.

### Steps

1. **DNS (done).** Cloudflare A → `2.25.250.28`, proxied, for app, rig, protect, autumbra, zenas, base, tiger, market-lab, tisan, radix, skala, and tank (as of 2026-10-25). Do not change apex `tervory.com` from this cutover.
2. **Coolify, workspace.** Open the Boston application that already lists `https://app.tervory.com` on service `workspace` (port 3000). On that same service, set the domain list to `https://app.tervory.com` **plus** every workspace host in the table (`https://protect.tervory.com`, **`https://rig.tervory.com`**, and the rest). Keep `app.tervory.com` in the list. Saving a list that omits it drops the client app. Do not create an application. Do not put these hosts on `site`, `mcp`, or `tank`.
3. **Coolify, rig.** Keep `https://rig.tervory.com` on **agent-rig** too. Deploy its reviewed raw Compose labels with the reserved-path rules above, priority 1000 on both HTTP/HTTPS routers. Keep TLS, gzip, service port 8000 and the proxy network unchanged. Inspect saved/effective labels: there must be no broad agent-rig host-only router. Workspace must have a matching host router with priority below 1000. Do not attach other product hosts to agent-rig.
4. **Coolify, rooms.** Confirm agent-ghost and the other rooms listed above have none of these public hosts. Leave them that way.
5. **Redeploy.** Deploy Workspace with the Rig host map and aliases, then attach its domain; verify the existing embeds while agent-rig still has its old host router. Deploy the reviewed agent-rig path split after Workspace is ready. Other rooms do not need a redeploy. Do not remove either Rig domain association during the cutover. Check both backends immediately; if the widget/API checks fail, restore the previous agent-rig labels before continuing.
6. **Trigger sign-in.** All product hosts share the Workspace's encrypted secure session on `.tervory.com`; the maintained OIDC client returns through `app.tervory.com`. Setup supplies the app IDs. Set only `TRIGGER_SIGNIN_WORKSPACE_SECRET` in Coolify, never a publishable key or satellite-domain setting. See `docs/ops/TRIGGER-SIGNIN.md`.

### Smoke

Signed out, each of these is HTTP 200:

- `https://app.tervory.com/api/health`
- `https://protect.tervory.com/api/health` and the same path on autumbra, zenas, base, tiger, market-lab, tisan, radix, rig, skala, tank
- `https://rig.tervory.com/health`

Then:

- `https://app.tervory.com/` is still the client dashboard (signed in).
- `https://protect.tervory.com/` is the public Autumbra page. Copy says Autumbra / Watch / Enforce, never Ghost or Wraith. `https://protect.tervory.com/admin/autumbra` is the founder console (signed-in founder).
- `https://zenas.tervory.com/moot` is the Moot index. `https://app.tervory.com/moot` returns **308** to the same path on `zenas.tervory.com`.
- `https://rig.tervory.com/` opens the Rig Workspace app after sign-in; `/admin` and `/admin/three-d` reach its Rig admin pages. `/rig/admin?cart=connection`, `?cart=orders` and `?cart=delivery` keep their query strings and reach the existing pages. No agent HTML handles those requests.
- On an existing store page, load the **unchanged issued embed snippet**: its script, fonts, CORS preflight, search, quote and cart calls still reach agent-rig. Verify `/widget/manifest.json`, `/widget/test`, `/3d/config`, `/page/search.js` and a signed test store webhook on the existing paths. Health and widget asset responses must not contain a Workspace sign-in redirect or HTML page.
- `/sign-in`, `/sign-up`, and `/api/health` are not rewritten. Deep links stay as linked.

Offline regression: `tests/test_rig_product_host.py` checks both rules and the
actual Workspace middleware. With `RIG_TRAEFIK_TEST_BINARY` pointing to an
existing local Traefik binary, it also sends real HTTP/HTTPS requests through
those labels' rules to isolated loopback backends. It inventories production
routes, extracts the issued snippet and shipped bundle paths, and verifies
redirects, query strings, POST/OPTIONS, body/key/origin/signature forwarding, namespace
boundaries and Workspace fallback. No production proxy or store is contacted.

Local validation for this change: **56 focused Python tests passed**, including
real Traefik HTTP/HTTPS routing and existing widget hosting/store/cart tests;
**19 Node tests passed** across product-host and shell-navigation tests.
Workspace TypeScript checking (`tsc --noEmit --incremental false`), Compose
validation and CI's exact Ruff command passed. These are offline proofs; the
founder still performs the Coolify cutover and existing-store smoke checks above.

This note does not create DNS or Coolify domains by itself.
