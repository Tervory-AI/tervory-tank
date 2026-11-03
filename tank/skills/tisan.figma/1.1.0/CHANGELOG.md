# 1.1.0

Add explicitly enabled tenant-paired live reads through the fixed Figma-only proxy. execute() defaults to live=False, preserving approved 1.0.x wrappers and unversioned room jobs. The authenticated room eval dispatcher parses the version and enables live mode from 1.1.0; this versioned wrapper also opts in. Job input cannot select live mode. Tank must supply a trusted approved-version field before ordinary jobs may enable it.

The Tervory recording remains available when its tenant/file is unpaired, including when FIGMA_TOKEN is set. Real Skala room evals contain the six 1.0.1 cases verbatim and one unpaired-file refusal, all scored from returned room results. Paired REST and variables-403 cases run in pytest only. tests/test_tisan_figma_live.py drives Tank's actual run_room_eval definition through app.py /evals/run using TestClient, a platform UUID and fixed placeholder environment; older versions are checked for zero live calls.

recorded-rest.json adapts existing recorded MCP values to REST wire shapes solely for offline HTTP/proxy tests. It is not a fresh REST capture or approved visual evidence. The per-instance proxy limit is 5,000,000 bytes; Radix source/defaults are unchanged. The existing compose mode and data volume are retained. The gateway is an ordinary bridge, so proxy enforcement describes the reader code path, not a whole-room egress seal.

Figma plan rule: https://developers.figma.com/docs/rest-api/variables/ and https://developers.figma.com/docs/rest-api/variables-endpoints/. A local-variables 403 leaves collections unknown. Earlier approved skill files are untouched; founder approval in Skala is required for 1.1.0.
