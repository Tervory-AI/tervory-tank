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

## Coolify cutover (production, Boston)

Public product hosts are extra domains on the Coolify application that already serves `app.tervory.com`. They are not new applications. Agent rooms do not get these hosts.

Routing for the table above is already on `main` (`workspace/lib/product-hosts.ts`, `workspace/middleware.ts`). This note does not create DNS records or Coolify domains. The founder attaches domains in Coolify and merges. No secret values belong in git, in this note, or in the pull request.

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
| rig.tervory.com | **agent-rig** (existing). Leave it there. | rig public API | 8000 |
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

### Steps

1. **DNS (done).** Cloudflare A → `2.25.250.28`, proxied, for app, rig, protect, autumbra, zenas, base, tiger, market-lab, tisan, radix, skala, and tank (as of 2026-10-25). Do not change apex `tervory.com` from this cutover.
2. **Coolify, workspace.** Open the Boston application that already lists `https://app.tervory.com` on service `workspace` (port 3000). On that same service, set the domain list to `https://app.tervory.com` **plus** every workspace host in the table (`https://protect.tervory.com`, and the rest). Keep `app.tervory.com` in the list. Saving a list that omits it drops the client app. Do not create an application. Do not put these hosts on `site`, `mcp`, or `tank`.
3. **Coolify, rig.** On **agent-rig** → General, the domain stays `https://rig.tervory.com` only. Save only if it is missing, then deploy agent-rig. Do not redeploy agent-rig to publish workspace hosts.
4. **Coolify, rooms.** Confirm agent-ghost and the other rooms listed above have none of these public hosts. Leave them that way.
5. **Redeploy.** Redeploy the Boston workspace application if Coolify did not apply the new domains on save. Rooms do not need a redeploy for this cutover.
6. **Clerk.** On the **same** Clerk application as `app.tervory.com`, add each workspace host as an allowed / satellite domain. Keys stay in Coolify under the existing names `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY`. Do not copy the values into git.

### Smoke

Signed out, each of these is HTTP 200:

- `https://app.tervory.com/api/health`
- `https://protect.tervory.com/api/health` and the same path on autumbra, zenas, base, tiger, market-lab, tisan, radix, skala, tank
- `https://rig.tervory.com/health`

Then:

- `https://app.tervory.com/` is still the client dashboard (signed in).
- `https://protect.tervory.com/` is the public Autumbra page. Copy says Autumbra / Watch / Enforce, never Ghost or Wraith. `https://protect.tervory.com/admin/autumbra` is the founder console (signed-in founder).
- `https://zenas.tervory.com/moot` is the Moot index. `https://app.tervory.com/moot` returns **308** to the same path on `zenas.tervory.com`.
- `/sign-in`, `/sign-up`, and `/api/health` are not rewritten. Deep links stay as linked.

This note does not create DNS or Coolify domains by itself.
