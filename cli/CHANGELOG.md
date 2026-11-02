# Changelog

## 0.1.2 — 2026-11-01

- ZA can use the optional self-hosted Zitadel device sign-in, including founders. Both verification URLs must use https://auth.za.tervory.com.
- Existing us-east Workspace approval and ZA Boston-approval fallback are unchanged. Tank access/refresh credentials and logout/revoke are unchanged.

## 0.1.1 — 2026-10-31

- Every CLI network call has a hard deadline that covers the body (device calls 10 s, JSON 300 s, request headers 30 s, live events 120 s per read, update 15 s JSON / 180 s tarball); a stream that stops early (stall, cancel, bad event, or the caller leaving) closes its connection to Tank; redirects are refused, never followed.
- Browser device-approval login (us-east via Workspace, ZA direct to Tank; the login itself shipped in 0.1.0): a 401/403 while polling stops login. Each sign-in can be seen and revoked in the Workspace under CLI sign-ins.
- Answers use Auto. `tervory models` and `--model` pinning are founder-only; customers never see model names, and customer receipts show dollar figures and "What Auto would have cost" only.
- Self-hosted install from app.tervory.com/cli (install.sh, SHA-256 manifest, `tervory update`, `TERVORY_CLI_VERSION` pinning). Never published to npm.
- install.sh: https only, including every redirect, over curl and wget (wget follows no redirect); connect and total deadlines (wget: per read, plus a total under `timeout` where it exists); the script runs only once fully downloaded; atomic replace; no downgrade from latest.json without `TERVORY_CLI_VERSION`.
- `tervory update` refuses a latest.json older than the installed copy unless `--version` is given.

## 0.1.0 — 2026-10-31

- Node 22 `tervory` command, persistent OS keychain login and logout.
- Tank-backed chat, ask, threads, run, build, receipts and models.
- Token-selected region, live steps and receipts, explicit Confirm prompts.
- Offline fake-Tank tests and public PAT forwarding boundary tests.
- Settings token UI is pending an approved Figma frame; this release remains a draft.
