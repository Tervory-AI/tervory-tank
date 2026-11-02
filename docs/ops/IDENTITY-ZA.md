# ZA identity: founder deployment and acceptance

This is the first Clerk-replacement step, for ZA CLI sign-in only. The identity
resource is separate from `tervory-tank-za`; it has its own PostgreSQL 16 database
and volumes. Boston's Clerk settings and Workspace approval remain unchanged.
Zitadel and its Login app are unmodified upstream images with default branding.
Do not add Tervory branding until the founder approves Figma page `8 · Sign-in`.
No live deployment or founder browser acceptance is claimed by this document.

## 1. DNS, once the ZA box is available

In Cloudflare, create the **A** record `auth.za.tervory.com` with the ZA server's
actual public origin IPv4 address, as shown on that server in Coolify. Use
**DNS only** for this record. Do not copy Boston's address from PRODUCT-HOSTS.md,
do not change the existing proxied `za.tervory.com` record, and do not change
any Boston/Clerk host. If the ZA origin address is unavailable, stop there.

DNS-only is the selected deployment here: browser TLS/HTTP2 goes straight to
Coolify, whose existing proxy forwards API traffic as h2c. Cloudflare proxying
is also supported by Cloudflare and Zitadel; it would require **Network → gRPC
On**, Full (strict) TLS, origin port 443, HTTP/2 and ALPN h2. It is not necessary
to change that zone-wide setting for this DNS-only identity hostname. Cloudflare
Access is not a substitute for Zitadel's authentication: Access does not protect
proxied gRPC. No second Traefik or public Cloudflare Tunnel is part of this stack.

Sources: [Cloudflare gRPC requirements](https://developers.cloudflare.com/network/grpc-connections/),
[HTTP/2 to origin](https://developers.cloudflare.com/speed/optimization/protocol/http2-to-origin/),
[Zitadel compose](https://zitadel.com/docs/self-hosting/deploy/compose),
[Zitadel proxy guidance](https://zitadel.com/docs/self-hosting/manage/reverseproxy/traefik).

## 2. Create the separate Coolify resource

On the **ZA server**, create a resource named **identity-za** from this repository
and the founder-reviewed commit. Base directory: `ops/identity`. Compose file:
`docker-compose.yml`. Enable Raw Compose Deployment so the checked-in networks
and proxy labels are used. Build contexts intentionally point back to the full
repository. Do not attach any service to the main ZA database network or volume.

Use Coolify's existing HTTPS proxy, entrypoint `https`, certificate resolver
`letsencrypt`, with a valid public certificate for `auth.za.tervory.com`. Put the
existing proxy network's name in `COOLIFY_PROXY_NETWORK`; select the name from
the ZA server's existing proxy configuration, not from another server. If this
server uses different proxy entrypoint/resolver names, stop and record those
names for a reviewed configuration change; do not silently change the labels.
Do not let an auto-generated HTTP/1.1 API route override the checked-in h2c labels.

Pinned release: **Zitadel v4.20.0**, latest stable release verified 1 Nov 2026
([release](https://github.com/zitadel/zitadel/releases/tag/v4.20.0), published 22 Oct).
API and Login multi-architecture index digests are in the compose file.
Postgres is `16.15` with its exact digest. Configuration/backup jobs use a pinned
Python base; they configure upstream APIs and reuse the existing encrypted backup
worker, without copying or patching Zitadel code (AGPL-3.0).

## 3. Enter settings in identity-za

Enter these values only in Coolify's environment settings. Do not paste values
into chat, git, terminal commands, screenshots, or a rendered compose export.
Do not enable shell tracing or print environment files.

| Setting name | Founder supplies |
| --- | --- |
| `ZITADEL_MASTERKEY` | Exactly **32 ASCII characters**. Keep securely and **never change it** after initialization. The database cannot be recovered without the original key. |
| `LOGIN_SESSION_COOKIE_SECRET` | A strong cookie-signing value of at least 32 characters, shared by Login replicas. |
| `POSTGRES_ADMIN_PASSWORD` | A new password for this resource's own Postgres administrator. |
| `POSTGRES_ZITADEL_PASSWORD` | A separate password for its own `zitadel` database role. |
| `IDENTITY_ADMIN_EMAIL` | The first founder administrator's real email; also used as the initial login name. |
| `IDENTITY_ADMIN_TEMP_PASSWORD` | A temporary password meeting Zitadel's complexity policy. First sign-in requires changing it. |
| `IDENTITY_BOOTSTRAP_KEY_EXPIRATION` | A future RFC3339 UTC expiry for the short-lived first-instance setup machine key; allow enough time to finish/retry setup. |
| `LOGIN_CLIENT_PAT_EXPIRATION` | A future RFC3339 UTC expiry for the Login app's service credential. Record its renewal date. |
| `COOLIFY_PROXY_NETWORK` | The existing ZA Coolify proxy network name from step 2. |
| `R2_ACCOUNT_ID` | The existing regional storage account setting. |
| `R2_ACCESS_KEY_ID_ZENAS`, `R2_SECRET_ACCESS_KEY_ZENAS` | The existing ZA backup storage credential pair, entered through the approved operator path. Never borrow Boston's pair. |
| `R2_BUCKET_ZENAS_ZA` | The existing ZA Zenas backup bucket name. |
| `R2_BACKUP_RECIPIENT` | The existing **public** age recipient used for ZA backups; never a private restore identity. |

There are deliberately **no SMTP environment settings** in this resource.
The first admin email is marked verified for this founder-controlled bootstrap;
no self-registration or external identity provider is enabled. Only the founder
creates organisations/users in this step.

## 4. Deploy identity-za

The checked-in dependency order is: own Postgres healthy → `zitadel-init` once →
`zitadel-setup` once → API healthy → Login and `tervory-setup`. The separate
`identity-backup` worker starts after successful Tervory setup.

Zitadel setup writes the first-instance machine key only to
`identity-za-bootstrap`, never stdout. Login's token is in the separate
`identity-za-login-token` volume: Login cannot read the bootstrap machine key.
The Tervory setup job authenticates with that machine key and creates the
`Tervory` project, a public native `Tervory CLI` OIDC app (device grant and
PKCE authorization code), and the project role `org_admin`. It verifies that the
project belongs to the first Tervory organisation. Self-registration is off,
passkeys/TOTP/security keys are allowed, and password/OTP lockout limits are on.

`tervory-setup` prints **only the public client ID on successful stdout**. Save
that public identifier for `IDENTITY_CLIENT_ID` below. Resource identifiers are
also stored in `/bootstrap/tervory.json`; no credential is included in that file.
A repeated setup run finds existing resources and makes no changes. A partial
run resumes by searching the same resources. If an existing app differs, setup
fails rather than replacing it. Rerun within the configured bootstrap key's
validity; after expiry, use the founder-controlled instance administrator to
renew the machine credential without printing or copying its value.

Confirm the API and Login health checks pass and the proxy serves HTTPS with
HTTP/2. In the browser, open `/ui/console` and confirm console requests succeed;
HTTP/1.1 upstream fallback is not an acceptable gRPC check. If h2c routing or
certificate issuance fails, stop with that result. Do not disable TLS checks.

## 5. First sign-in and password change

Open `https://auth.za.tervory.com/ui/console`, sign in with the first admin email
and temporary password, and complete the required password change. The root
hostname routes to the default Login app. Keep Zitadel's default words and
branding. No new sign-in page or copied Figma frame is introduced by this step.

## 6. Add a passkey

In the default account profile/security settings, add a passkey/security key
using this HTTPS origin. Complete the browser/device prompt, then sign out and
verify sign-in using that passkey. Keep a founder-controlled recovery method.
Capture acceptance screenshots with all passwords, cookies and token values hidden.

## 7. SMTP in the console

Use Zitadel Console → Instance settings → Email/SMTP to enter the founder's
existing mail transport settings and send a test message. Enter them in the
console only; do not add SMTP values or configuration to this repository.

## 8. Tervory organisation and role assignments

The first-instance setup has already created the **Tervory** organisation.
Select it in the console; do not create a duplicate. Copy its organisation ID
from the organisation details/URL. For additional client organisations, the
founder creates them in this console, creates their users, and records each ID.
Map only approved organisations to existing Tervory tenant UUIDs in step 9.

The public CLI application must remain in the project owned by this Tervory
organisation. Assign `org_admin` only through that project (and founder-approved
project grants where needed). An organisation's own IAM/ORG administrator role,
email, display name or editable user metadata does not grant Tervory admin rights.
Do not enable custom actions that replace reserved role/organisation claims.

## 9. Configure only tervory-tank-za

In the existing **tervory-tank-za** resource, set:

| Setting | Value to enter |
| --- | --- |
| `IDENTITY_ISSUER` | `https://auth.za.tervory.com`, exactly, without a trailing slash. |
| `IDENTITY_CLIENT_ID` | The public client ID printed by `tervory-setup`. |
| `IDENTITY_ORG_TENANTS` | A JSON object mapping each actual Zitadel organisation ID to its approved existing Tervory tenant UUID, in the form `{"<org id>":"<tenant UUID>"}`. |

These are passed only to ZA Tank by `docker-compose.za.yml`. Do not configure
these names in Boston. With the issuer empty, behavior stays as before.
Keep `TANK_DEVICE_APPROVAL_KEY_ZA`/`TANK_DEVICE_APPROVAL_KEY` and their existing
Boston approval routes unchanged. While Zitadel is enabled, an existing caller
may explicitly request `{"device_name":"…","approval":"workspace"}` at the
same code endpoint for the limited Boston approval flow; no new browser controls
or CLI option are added. Default ZA code requests use Zitadel. Existing local
pending codes can still be approved/polled. Boston's key still cannot approve
founder identities. Old CLI versions need the 0.1.2 update for the new default.

## 10. Find the founder sub and append the founder identity

In the Tervory organisation, open the founder's own user in Zitadel Console.
The user's immutable ID shown in the details/URL is the OIDC **sub**. Append
`zitadel:<that sub>` to **ZA** `TERVORY_ADMIN_USER_IDS`, retaining existing entries.
Do not use an email, display name, metadata field, IAM role, or an unprefixed ID.
Nothing changes in Boston's founder list.

## 11. Redeploy ZA Tank and test the CLI

Redeploy **tervory-tank-za** after the settings are saved. Founder merges; no
operator in this task merges or pushes main. The shared code also runs in Boston,
but the feature is gated to ZA and an explicit issuer setting. No Boston/Clerk
setting has been changed. Review deploy-on-merge impacts before merging: Tank,
ZA compose and CLI changes may select the existing main/ZA build pipelines.

Install/update the self-hosted CLI to **0.1.2** using its existing release path.
Run:

```sh
tervory version
tervory login --region za
tervory chat
tervory logout
```

The browser must open only `https://auth.za.tervory.com`; approve the displayed
code on Zitadel's default page. Tank validates issuer, audience, expiry and
RS256 signature using discovery/JWKS, refreshes unknown signing keys, maps the
reserved organisation ID, and issues the same existing Tank credential format,
one-hour access and rotating 30-day refresh. `user_id` is `zitadel:<sub>`.
Project roles come only from Zitadel's reserved claim for the requesting
application's own Tervory project; other-project claims and metadata are ignored.
Roles are captured at sign-in; the existing Tank revoke ends that credential.
Founder membership is re-read from the explicit ZA admin list.

Show a ZA chat as founder, then revoke that sign-in using `tervory logout` (the
existing revoke endpoint). A subsequent chat must be refused until a new login.
Do not paste a bearer/refresh/ID token into a terminal or screenshot. Record
screenshots of the default sign-in, passkey confirmation, device approval,
founder chat and refused post-revoke attempt with credentials hidden.

## 12. Backups and the identity restore drill

The identity worker reuses `jobs/train/backup.py --owner zenas --target database
--identity --nightly`, encrypted through `age` before archive storage, at the
existing 02:00 UTC cadence. It dumps only `identity-postgres:5432/zitadel` with
that resource's `zitadel` role. Completed archives use the existing ZA backup
prefix with label `identity/database.dump.age`. Neither SQL plaintext nor the
private restore identity goes to R2. The main ZA/Postgres/Qdrant backups continue
through their existing workers; no Boston backup path is changed.

On the **ZA host only**, follow [RESTORE-DRILL.md](RESTORE-DRILL.md)'s existing
secure operator prerequisites and add `--identity` to the ZA command:

```sh
.git/restore-venv/bin/python ops/restore_drill.py --region za --identity-file "$RESTORE_IDENTITY_FILE" --rls --identity
```

This requires completed encrypted Tank, Qdrant **and identity** archives. It
restores identity to a separate `identity_restore` database in the disposable
Postgres container, never the main ZA database, and returns
`identity_database_restored: true` plus a nonzero `identity_table_count`.
Plaintext/temp containers are removed through the existing drill lifecycle.
Keep the original immutable master key securely outside the database backup;
also retain the resource's Login/bootstrap volumes and operator-managed settings.
The database drill does not claim to restore those separate secret volumes.

Acceptance remains pending until the founder completes the browser/CLI steps,
revocation refusal and this real **ZA** restore drill. The synthetic offline
round trip in the PR is preparation evidence, not a live deployment result.
