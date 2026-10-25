# Product hosts (*.tervory.com)

One product per host. `app.tervory.com` stays the client workspace. Marketing stays on apex `tervory.com`.

## Workspace hosts (same Coolify service as `app.tervory.com`)

| Host | Lands on | Product |
| --- | --- | --- |
| protect.tervory.com | `/autumbra` (public product) | Autumbra (Watch / Enforce) |
| autumbra.tervory.com | `/autumbra` (public product) | Autumbra |
| zenas.tervory.com | `/zenas` | Zenas |
| base.tervory.com | `/base` | Base |
| tiger.tervory.com | `/tiger` | Tiger |
| market-lab.tervory.com | `/market-lab` | Market Lab |
| tisan.tervory.com | `/tisan` | Tisan |
| radix.tervory.com | `/radix` | Radix |
| skala.tervory.com | `/skala` | Skala (founder) |
| tank.tervory.com | `/tank` | Tank (founder) |

Routing is app-level: `workspace/lib/product-hosts.ts` + `workspace/middleware.ts` rewrite `/` on those hosts. Deep links, `/sign-in`, `/sign-up`, and `/api/health` are not rewritten. Legacy `/admin/ghost` still redirects to `/admin/autumbra`.

### Autumbra public paths (no auth fight)

| Path | Who | What |
| --- | --- | --- |
| `/autumbra` | Anyone | Product page — Watch + Enforce value, zero-ingestion, what you get after sign-in |
| `/autumbra/demo` | Anyone | Interactive fixture console — triage, inventory, advisories, Enforce |
| `/admin/autumbra` | Founder (signed in) | Live console + same fixture board when Tank/HF offline |

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
4. Merge the product PR, then deploy-on-merge / Coolify redeploy workspace.
5. Smoke (signed-out, no auth fight):
   - `https://protect.tervory.com/` → Autumbra product
   - `https://protect.tervory.com/autumbra/demo` → clickable fixture console
   - `/api/health` 200 on each host
   - Founder signed-in: `/admin/autumbra` console

This note does not create DNS or Coolify domains by itself.
