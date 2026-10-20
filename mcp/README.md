# Tervory connector

Remote MCP server for `https://mcp.tervory.com/mcp`. Streamable HTTP. Users sign in with Clerk. Every tool call goes to Tank with that user’s tenant id.

Public setup, the tool list, and the privacy policy: `docs/mcp/index.html`. The reviewer steps are `docs/mcp/reviewer.md`.

Tests live in `tests/test_mcp_connector.py` and run with the rest of the suite. They do not use a network.

Environment names are in `.env.example`. Values are set in Coolify, not in this folder.
