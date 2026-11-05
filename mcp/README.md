# Tervory connector

The old `https://mcp.tervory.com` resource redirects supported MCP/OAuth protocol paths to the canonical Workspace host. It issues no tokens and holds no identity settings. Trigger sign-in authenticates the Workspace; Tank handles the existing scoped MCP credentials.

Public setup, the tool list, and the privacy policy: `docs/mcp/index.html`. The reviewer steps are `docs/mcp/reviewer.md`.

Tests live in `tests/test_mcp_redirect.py` and run with the rest of the suite. They do not use a network.

Environment names are in `.env.example`. Values are set in Coolify, not in this folder.
