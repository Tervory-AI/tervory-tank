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
| skala.tervory.com | `/skala` | Skala (founder) |
| tank.tervory.com | `/tank` | Tank (founder) |

Routing is app-level: `workspace/lib/product-hosts.ts` + `workspace/middleware.ts` rewrite `/` on those hosts. Deep links, `/sign-in`, `/sign-up`, `/api/health`, `/autumbra` (public product), and `/moot` (public watch) are not rewritten away. Legacy `/admin/ghost` still redirects to `/admin/autumbra`.

**Moot is part of Zenas.** Canonical URLs are on `zenas.tervory.com` (`/moot`, `/moot/[match]`, `/zenas`). Hitting `app.tervory.com/moot*` returns **308** to the matching path on `zenas.tervory.com`. Do not treat Moot as a primary surface on the client workspace host.

User-facing copy on Autumbra hosts: **Autumbra** / Watch / Enforce only — never Ghost or Wraith.

## Separate services (do not attach to workspace)

| Host | Service |
| --- | --- |
| rig.tervory.com | agent-rig (existing) |
| mcp.tervory.com | mcp |
| coolify.tervory.com | Coolify UI |
| tervory.com / www | site / Worker marketing |

## Cutover (AMMOSYNC / Zenas)

1. Cloudflare DNS A → `2.25.250.28` proxied (done for product hosts as of 2026-10-25).
2. Coolify: attach each workspace host to the **same** workspace application as `app.tervory.com` (do not invent new apps).
3. Clerk: add each workspace host as allowed / satellite domain on the **same** Clerk app as `app.tervory.com`.
4. Merge this routing PR, then deploy-on-merge / Coolify redeploy workspace.
5. Smoke: signed-out `/api/health` 200 on each host; `https://zenas.tervory.com/moot` shows Moot index (published fixtures); `app.tervory.com/moot` 308 → zenas; app root still client dashboard.

This note does not create DNS or Coolify domains by itself.
