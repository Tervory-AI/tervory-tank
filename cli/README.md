# Tervory CLI

Node 22. macOS Keychain, Windows Credential Manager, or Linux Secret Service is required for login. The CLI uses the pinned `@napi-rs/keyring` binding, never a plaintext credential file. Linux requires a running unlocked Secret Service; an unavailable keychain fails without a storage fallback. Cross-platform native keychain integration has not been exercised in founder acceptance.

## Install (self-hosted, no npm)

The CLI is never published to npm or any other third-party registry: `cli/package.json` is `"private": true` (CI asserts it) and its `publishConfig.registry` points at an invalid host. Tervory serves it from the Workspace at `https://app.tervory.com/cli/`:

```
curl -fsSL https://app.tervory.com/cli/install.sh | sh                          # latest
curl -fsSL https://app.tervory.com/cli/install.sh | TERVORY_CLI_VERSION=0.1.0 sh  # pinned
tervory update                      # latest, or TERVORY_CLI_VERSION when set
tervory update --version 0.1.0      # a specific version (also downgrades)
tervory version
```

- `install.sh` reads `latest.json` (or the pinned version), then `releases/<version>/manifest.json`, downloads `tervory-cli-<version>-<platform>.tar.gz` and refuses it unless its SHA-256 matches the manifest (nothing is installed on a mismatch). `releases/<version>/SHA256SUMS` is the same list in `sha256sum` format. It installs to `~/.tervory/cli/<version>`, switches `~/.tervory/cli/current` and writes a `~/.local/bin/tervory` launcher. Node.js 22 must be on PATH.
- Platforms: linux-x64/arm64 (glibc and musl) and darwin-x64/arm64; each tarball carries its own `@napi-rs/keyring` binding.
- `tervory update` uses `https://app.tervory.com/cli` only (no URL override), verifies the SHA-256 the same way and switches `current` atomically. Installed copies check `latest.json` at most once a day (1.5 s budget, never fails a command) and print a one-line notice; `TERVORY_NO_UPDATE_CHECK=1` or a `TERVORY_CLI_VERSION` pin turns that off.
- Releasing: bump `version` in `cli/package.json` and `CHANGELOG.md` and merge. Release files are build outputs, never committed: the Workspace image build (`workspace/Dockerfile`, `cli-release` stage, fed `cli/` through `additional_contexts` in `docker-compose.yml`) runs `node cli/scripts/build-release.mjs` and copies the result into `public/cli`, so `https://app.tervory.com/cli/` serves the version in `cli/package.json`. Pushing a tag `cli-vX.Y.Z` runs the `cli-release` workflow, which checks the tag against the version and changelog, builds twice (byte-identical) and keeps the files as a 90-day workflow artifact; it publishes and deploys nothing. On one host the build is byte-reproducible; the `cli` workflow proves the image's tarballs hold the same entries and file bytes as a direct build (archive bytes can differ between GNU tar versions) and that the image's manifest and `SHA256SUMS` match the files it serves. The image serves only its current version, so `TERVORY_CLI_VERSION` pins to an older version stop resolving after a bump (follow-up: durable release storage together with manifest signing). For local testing, `node cli/scripts/build-release.mjs --out workspace/public/cli` (ignored by git). `latest.json` and `install.sh` are `no-cache`, versioned releases are immutable.

Development: `npm ci --prefix cli`, then `node cli/bin/tervory.mjs help`. Do not install anything on the founder's laptop as part of automated work.

`tervory login [--region us-east|za]` signs in with a device approval; nothing is pasted. The CLI asks the region's public origin for a device code, opens one Workspace page, `https://app.tervory.com/cli/device?code=XXXX-XXXX&region=…` (it builds that URL itself and opens only that origin), and polls every 5 seconds (plus 5 s on `slow_down`) for up to 10 minutes. The page uses the existing Clerk sign-in. It shows the code, when the code was created, organization, region and "Device (the name the device reported)" (the requesting machine's own hostname claim, unverified), warns to deny any code the user did not just create, with **Approve** and **Deny** buttons. On approval, Tank issues an organization-scoped credential for the approving user into `tank.personal_tokens`. Only sha256 hashes are stored. The access token lasts 1 hour, and the refresh token lasts 30 days and rotates on every use. A reused, expired or revoked refresh token is refused. `last_used_at` is updated at most once a minute. The CLI saves one JSON entry in the OS keychain: `{version, region, access_token, refresh_token, expires_at, refresh_expires_at}`. It refreshes automatically when the access token is within 60 s of expiry. `tervory logout` revokes the credential on Tank and then removes the keychain entry. Each user can also see and revoke their CLI sign-ins in the Workspace at **CLI sign-ins** (`https://app.tervory.com/cli/sign-ins`, linked in the sidebar): one row per active sign-in with the device name the device reported, region, when it signed in and when it was last used, and a **Revoke** button that ends its access and refresh tokens at once. ZA rows are read and revoked on the ZA Tank with `TANK_DEVICE_APPROVAL_KEY_ZA`, which there may only list and revoke that user's own sign-ins (never create one, never for a founder). Older keychain entries holding a raw `tv1` personal token keep working until logout. The command accepts no token arguments or environment variables. Do not use a service key in this CLI.

Regions: **us-east** device calls go to `https://app.tervory.com/v1/command/device/{code,token,refresh,revoke}`, which the Workspace forwards to its local Tank. **ZA** has no Workspace: `za.tervory.com` is Tank only, so the CLI calls `https://za.tervory.com/v1/command/device/…` and every later chat turn goes straight to the ZA Tank. Approval still happens on the single Clerk-backed Workspace (`app.tervory.com/cli/device?region=za`), which records the decision on the ZA Tank at `TANK_URL_ZA` with the dedicated `TANK_DEVICE_APPROVAL_KEY_ZA` (the ZA Tank accepts it as `TANK_DEVICE_APPROVAL_KEY` for the two approval routes and for listing and revoking the user's own sign-ins only, and never for a founder; the ZA homes key in `TANK_API_KEY_ZA` cannot approve). No Clerk dashboard change is needed: the page is an ordinary signed-in Workspace route protected by the existing middleware.

```
tervory chat [thread]
tervory ask "question" [--thread id] [--file path]
tervory threads
tervory run base batch --file path.csv [--thread id]
tervory run agent task --args '{"argument":"value"}' [--thread id]
tervory build "change" [--thread id]
tervory receipts thread-or-task-id
```

Interactive chat ends on `/exit` or EOF. Tool cards require an explicit `y` or `yes`; every other answer cancels. Non-interactive input cannot confirm. `run` uses the existing Tank tool name and argument schema; Base CSV intake maps headers and records to the existing batch contract. Other tool files must use that tool's JSON schema through `--args`. Tank enforces the schema and current role. `build` displays the submitted change as its brief, proposes the existing build card, and waits for confirmation; it does not spend a model call to rewrite the user's text.

The token envelope selects `https://app.tervory.com` or `https://za.tervory.com`. There is no URL override or cross-box fallback. Tank verifies the complete credential hash and region; the envelope alone grants no identity. The public command route forwards only the bearer credential to its fixed local Tank. It never sends a service key or client-supplied user, tenant or role assertions.

Receipt amounts are displayed exactly as Tank returns them. Answers use Auto. Model names, provider models and prices are founder-only: Tank refuses the model roster (404) and any pinned model (403, naming no model) for everyone else, and sends model names in receipts, steps and messages only to the founder. Customers see the dollar figures and "What Auto would have cost". The CLI never computes money. An interrupted stream is reported and never automatically retried, because a turn may have incurred cost.

The known-action `run` and owned task receipt endpoints are supplied by companion draft PR #465. This branch must be tested with that backend before founder acceptance. Confirmed jobs are watched with read-only snapshot polls every 500 ms, for at most 240 polls; Ctrl-C cancels watching, never the already confirmed job. The CLI prints changed steps, produced links and ledger receipts and stops at completion, failure, unknown outcome or the polling bound. Reopen `chat <thread>` to show saved messages and resume watching. No failed or interrupted turn/action is automatically resubmitted.

Interactive terminals show provisional answer text on a single stderr preview line; stdout receives the final answer once. Tank's `replace` event replaces the provisional answer, and duplicate sequence numbers are ignored. Non-interactive stdout receives only the validated final answer, avoiding stale previews in scripts.

`npm test --prefix cli` runs fake-Tank tests with synthetic credentials and data only. No provider requests or live account changes occur. Evidence in `tests/cli_1_20261031/` is labeled offline fake-Tank proof and is not a founder-browser test.
