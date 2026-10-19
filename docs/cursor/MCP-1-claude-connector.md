# MCP-1 — Tervory as a Claude connector (Connectors Directory)

> Written 18 Oct 2026, 18:30 PT. Goal: a remote MCP server at `https://mcp.tervory.com` so Claude users can call the squad, then submit it to the Claude Connectors Directory (claude.ai/directory/manage). Requirements: https://claude.com/docs/connectors/building/submission

**Files you may change:** `mcp/` (new service: Dockerfile, server, tests), `docker-compose.yml` (additive: one `mcp` service on the tank corridor only), `.env.example` (names only), `docs/mcp/` (public docs page source), new tests. Do not edit Tank's router, queue or ledger; call Tank's existing API.

## Build
- Remote MCP server over HTTPS (Streamable HTTP), public at `mcp.tervory.com` (Claude sets the domain).
- **Auth: OAuth 2.0** with Clerk as the identity provider, dynamic client registration supported; the user's Clerk organization is the tenant (same tenant mapping as the Workspace, including `TERVORY_TENANT_ALIASES`). No API keys handed to users.
- **Every call goes through Tank** with the tenant id, so the ladder, cache, ledger and costs apply.
- **First tools** (each with a `title` and `readOnlyHint` or `destructiveHint`, clear descriptions):
  - `rig_search` (read-only): search a retailer's catalogue the user has access to.
  - `base_lookup` (read-only): look up the user's own enriched business records.
  - `base_enrich` (write): submit a small list (max 100 rows) for enrichment; returns a batch id.
  - `zenas_research` (read-only): legal research question, US or SA business law, answer with citations; scope gate first, no criminal law.
  - `market_lab_brief` (read-only): sourced market brief on a topic.
  - `tiger_watch` (write): add a product URL to the user's price watchlist.
- Every answer returns its sources, the model that ran it and the cost, as in the app.

## Listing materials (in `docs/mcp/`)
Public documentation page (setup, each tool, examples), privacy policy section for the connector, support contact, icon (the existing Tervory mark, exact file), and a reviewer test-account guide (the founder creates the test account).

## Done when
CI green; MCP Inspector lists all tools with titles and annotations; a test proves a call without a valid token is refused and a call is always scoped to the caller's tenant; the founder can add it in Claude as a custom connector and run each tool. Submission to the directory is the founder's step after that.
