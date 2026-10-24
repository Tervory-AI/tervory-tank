# GHOST-2: know every hole within an hour, shield it within a day

> Written 23 Oct 2026 by Claude, from the project doc `ghost/GHOST-PRODUCT-research.md` ("Building it with a goal"). **Builder: Grok.**
>
> **The goal:** *no known hole stays open on a Ghost site for more than a day.* GHOST-1 gave Ghost its box, watchers and investigations. GHOST-2 adds the inventory, the advisory watcher and Shields Up v1, dogfooded on our own sites. Defence only.

**Files you may change:**
- `agents/ghost/` (new modules `inventory.py`, `advisories.py`, `shields.py`, plus their routes in `app.py`);
- `agents/ghost/docker-compose.yml` (environment names only; no new ports, and Ghost's networks stay as they are);
- `tank/ghost_routes.py` (new routes only) and `tank/schema.sql` (additive);
- `workspace/app/admin/` (the Ghost panel only);
- `.env.example` (names only);
- tests.

## 1. Inventory: what every site runs
- **For each app Ghost watches:**
  - images and tags;
  - language runtimes (PHP, Node, Python versions);
  - packages from lockfiles (a bill of materials);
  - the domain, whether it's behind Cloudflare, and the open public ports.
- **Sources:**
  - the Coolify API (read-only, `COOLIFY_TOKEN_GHOST` by name);
  - the repo's Dockerfiles and lockfiles (`requirements*.txt`, `package-lock.json`, `pnpm-lock.yaml`);
  - each site's response headers (Server and X-Powered-By).
- **Ghost has no Docker socket and never gets one.** Host-level facts (such as Coolify's PHP version) come from a read-only report that Grok posts to Ghost's intake (`POST /ghost/inventory/report` with the Ghost room key), and are refreshed after each host change.
- **Refresh** on every deploy (the deploy-on-merge receipt) and nightly. Store it in `ghost_inventory` with one row per app, component and version, stamped with when it was seen.

## 2. The advisory watcher
- **Every 15 minutes, pull these legitimate sources only:**
  - CISA Known Exploited Vulnerabilities (JSON feed);
  - OSV (`api.osv.dev`, query by package and version);
  - GitHub Security Advisories (REST, public);
  - NVD 2.0 (optional `NVD_API_KEY` by name; without it, respect the public rate limit);
  - vendor notes: PHP releases, Node security releases, Coolify GitHub releases, and LiteLLM GitHub advisories.
- **No dark web, no bought or leaked data, no scanning anyone's site but ours.**
- **Match each new advisory against the inventory** using proper version ranges (OSV semantics). A match creates a Ghost issue with:
  - what is affected;
  - how bad it is (CVSS, and whether it's on the KEV list);
  - what to do: patch to a version, or the shield to raise.
- **Every match has a receipt with both timestamps:** when the advisory was published and when Ghost flagged it (that difference is time to know).

## 3. Shields Up v1 (Cloudflare-fronted sites only)
- **A short list of safe, reversible shields:**
  - turn on a WAF managed rule;
  - rate-limit a path;
  - block a method on paths that never take uploads (the PHP2Shell shape);
  - challenge known-bad bots.
- **Every shield follows the same four steps:**
  1. A proposed change goes to the founder panel with one button, **Shield**.
  2. Ghost applies it through the Cloudflare API with `CLOUDFLARE_API_TOKEN_GHOST` (by name, scoped to named zones and WAF and rule edit only).
  3. It runs a health check on the site straight after.
  4. If the site fails, it **undoes the change automatically**.

  There's also a **one-tap Undo**, and every change has a receipt.
- **Dry-run mode is the default.** With the token empty, Ghost shows exactly what it would change and calls nothing. The founder plugs the token in last.
- **For sites not on Cloudflare,** and for our own hosts (closing a port, say), Ghost writes the step as a brief for Grok. It never touches a host itself.

## 4. The panel and the numbers
- **The Ghost tile on the founder panel:**
  - open matches by severity;
  - **time to know** (target under 1 hour);
  - **time to shield** (target under 24 hours);
  - **sites broken by a shield** (target 0);
  - Ghost's cost this month (from Tank receipts).
- Plain words, no jargon, and receipts linked.

## 5. Acceptance: replay PHP2Shell (21 Oct)
Load a fixture advisory for CVE-2026-109618/9 and an inventory showing Coolify on PHP 8.4.23. Ghost must:
1. flag Coolify within one advisory-pull cycle;
2. propose "block multipart POST on non-upload paths at the edge" for `coolify.tervory.com` in dry-run;
3. mark it resolved once the inventory shows Coolify 4.4.7 on PHP 8.4.27.

## Done when
CI green. Tests:
- version-range matching, including the edge cases: pre-releases and epochs;
- the PHP2Shell replay end to end;
- in dry-run, a shield makes no network call;
- a shield whose health check fails is undone automatically;
- no secret value appears in any log, receipt or response.

Then dogfood for two weeks on tervory.com, app.tervory.com, coolify.tervory.com and rig.tervory.com (report-only where a zone isn't on Cloudflare).
