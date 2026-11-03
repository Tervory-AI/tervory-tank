# 1.1.0

Read tenant-paired live pages through the fixed Figma-only proxy. Keep the offline Tervory fixture when no token is set. Bound requests and bodies, refuse unpaired files, and preserve unknown variables on a 403. Tenant identity comes from the skill context. Earlier versions are untouched; founder approval in Skala is required.

Adds three offline REST cases: paired read, tenant refusal before any request, and variables 403. `recorded-rest.json` adapts only values already in the recorded MCP fixture to REST wire shapes; it is not a fresh REST capture or approved visual evidence. `tests/test_tisan_figma_live.py` executes those cases through the real locked proxy and a local fake HTTPS API. No fixture payload enters the production reader. Live Skala evaluation requires the founder-configured token and matching tenant/file pairs.

Figma plan rule: https://developers.figma.com/docs/rest-api/variables/ and https://developers.figma.com/docs/rest-api/variables-endpoints/. The Variables API requires Enterprise access. A local-variables 403 leaves collections unknown.
