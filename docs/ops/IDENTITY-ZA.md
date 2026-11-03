# ZA identity: founder deployment and acceptance

This is the first Clerk-replacement step, for ZA CLI sign-in only. The identity
resource is separate from `tervory-tank-za`; it has its own PostgreSQL 16 database
and volumes. Boston's Clerk settings and Workspace approval remain unchanged.
Zitadel and its Login app are unmodified upstream images with default branding.
Do not add Tervory branding until the founder approves Figma page `8 · Sign-in`.
No live deployment or founder browser acceptance is claimed by this document.

## 1. DNS, once the ZA box is available

Use **Proxied (orange cloud)** for the A record `auth-za.tervory.com`, pointing
to the ZA server's actual origin IPv4 from Coolify. Keep the existing
`za.tervory.com` record unchanged. The identity hostname is one level below
`tervory.com`, so Cloudflare's free Universal SSL `*.tervory.com` coverage applies.
Confirm the zone's existing Universal SSL edge certificate is active. Set/confirm:

- Cloudflare **Network → gRPC: On** for the zone.
- **Speed → Settings → Protocol Optimization → HTTP/2 to Origin: On**.
- **SSL/TLS → Overview → encryption mode: Full (strict)**.
- Existing Coolify proxy: TLS on **443**, a valid unexpired origin certificate
  covering `auth-za.tervory.com`, and HTTP/2 advertised as **h2** via ALPN. Keep
  the checked-in API upstream **h2c** and Login routes. Zitadel authenticates
  requests; Cloudflare Access does not protect proxied gRPC.

### Origin certificate: establish the existing ZA issuance path first

The origin certificate must be issued/renewed **exactly as Coolify does today
for the existing proxied `za.tervory.com`**, using the existing ZA proxy
configuration. No resolver/challenge change and no new Cloudflare token.

**What the repo establishes:** `docker-compose.za.yml:2` and `:174` say Coolify
attaches `za.tervory.com` to Tank, which exposes port 8000. That service has no
checked-in Traefik TLS/certificate labels; the running resource's generated
labels and the ZA proxy's current certificate challenge configuration are not
in the repo. The identity compose references the existing `https` entrypoint and
`letsencrypt` resolver, but that does not prove what the live ZA host uses.

**Founder checks, read-only, in Coolify before deployment:**

1. Open the existing **tervory-tank-za** resource on the ZA server. Under
   **Configuration → General**, read the existing Domains/service routing entry
   for `https://za.tervory.com` and Tank port 8000. Inspect the resource's current
   generated labels/configuration for its HTTPS router: record only its
   `entrypoints`, `tls` and `tls.certresolver` names, if present.
2. Open **Servers → ZA server → Proxy → Configuration**, without editing,
   saving or restarting. Identify the same resolver's existing ACME challenge
   type from its command flags; if the router uses a custom certificate instead,
   identify that existing certificate mechanism from the proxy's dynamic TLS
   configuration. Record only the mechanism/resolver names. Do not display/copy
   environment values, private-key files or ACME storage contents.
3. Confirm the current `za.tervory.com` certificate is valid and how Coolify
   issues and renews it while that record stays proxied. Use that **same existing
   issuance/renewal path** for `auth-za.tervory.com`. Establish how that existing
   path will issue the identity hostname certificate on deployment, then verify
   its hostname coverage during step 4. Keep the ZA proxy configuration unchanged. The
   checked-in identity labels require `https`/`letsencrypt`; if the existing names
   or mechanism differ, record that mismatch for an identity-resource label
   review rather than changing the shared proxy.

**Stop at this step until the existing issuance/renewal mechanism and compatible
identity router settings are established.** Missing evidence is the live ZA
resource's TLS router/resolver and the existing proxy's certificate issuance and
renewal method; this cannot be established from the repository. Do not deploy
identity-za, enter the issuer on Tank or continue sign-in acceptance until that
read-only check succeeds. Do not switch the record to DNS-only, alter the ZA
proxy or introduce a token as a workaround. Preserve the host's existing firewall
and certificate-validation rules.

Sources: [Cloudflare gRPC requirements](https://developers.cloudflare.com/network/grpc-connections/),
[HTTP/2 to origin](https://developers.cloudflare.com/speed/optimization/protocol/http2-to-origin/),
[Full (strict)](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/),
[Universal SSL limitations](https://developers.cloudflare.com/ssl/edge-certificates/universal-ssl/limitations/),
[Coolify certificate troubleshooting](https://coolify.io/docs/troubleshoot/dns-and-domains/lets-encrypt-not-working),
[Zitadel proxy guidance](https://zitadel.com/docs/self-hosting/manage/reverseproxy/traefik).

## 2. Create the separate Coolify resource

On the **ZA server**, create a resource named **identity-za** from this repository
and the founder-reviewed commit. Base directory: `ops/identity`. Compose file:
`docker-compose.yml`. Enable Raw Compose Deployment so the checked-in networks
and proxy labels are used. Build contexts intentionally point back to the full
repository. Do not attach any service to the main ZA database network or volume.

Use Coolify's existing HTTPS proxy, entrypoint `https`, certificate resolver
`letsencrypt`, with a valid public certificate for `auth-za.tervory.com`. Put the
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
`identity-backup` worker depends only on healthy identity Postgres, so backups
continue independently of setup success or machine-key expiry.

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
fails rather than replacing it. After key expiry, a completed `/bootstrap/tervory.json`
record makes the job exit 0 and log `Identity setup already completed; bootstrap
key expired; no changes attempted` without reading/signing the key or calling an
API. It prints the saved public client ID. This trusts the last completed setup,
not a fresh drift audit. An expired partial/missing completion record still fails:
the founder must renew the machine credential through the instance administrator
before finishing setup, without printing/copying it. Backups remain independent.

Confirm the API and Login health checks pass and the proxy serves HTTPS with
HTTP/2. In the browser, open `/ui/console` and confirm console requests succeed;
HTTP/1.1 upstream fallback is not an acceptable gRPC check. If h2c routing or
certificate issuance fails, stop with that result. Do not disable TLS checks.

## 5. First sign-in and password change

Open `https://auth-za.tervory.com/ui/console`, sign in with the first admin email
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

The **Tervory** organisation is the one **Zitadel creates at first start** from
`ZITADEL_FIRSTINSTANCE_ORG_NAME`, not a second organisation created by our job.
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
| `IDENTITY_ISSUER` | `https://auth-za.tervory.com`, exactly, without a trailing slash. |
| `IDENTITY_CLIENT_ID` | The public client ID printed by `tervory-setup`. |
| `IDENTITY_ORG_TENANTS` | A JSON object mapping each actual Zitadel organisation ID to its approved existing Tervory tenant UUID, in the form `{"<org id>":"<tenant UUID>"}`. |

The first-start Zitadel **Tervory** organisation must map to the **existing
Tervory Workspace tenant UUID**, not the platform UUID, the Zitadel project/org
ID, a user's personal tenant or a new UUID. Find the exact UUID without SQL:

1. In the existing Boston Workspace, sign in as founder and select the existing
   **Tervory** Clerk organisation using its current organisation selector.
2. In the same authenticated browser, open
   `https://app.tervory.com/api/case-studies` with **no tenant_id query**.
   This existing GET returns the active organisation's exact `tenant_id` UUID
   (`workspace/app/api/case-studies/[[...path]]/route.ts`; Tank's existing
   `GET /v1/case-studies`). It already resolves any `TERVORY_TENANT_ALIASES`.
3. Map the first-start Zitadel Tervory organisation ID from step 8 to **that exact
   returned `tenant_id`**, preserving other approved mappings. Never select an
   unlabelled UUID from `/clients` or infer identity from an organisation's name.

The live Tervory UUID is not verified in this offline PR and is not fabricated
here. If the founder cannot positively select the existing Tervory organisation,
or the authenticated read does not return its UUID, **stop at this step**:
missing input is the verified existing Tervory tenant UUID. Do not populate
`IDENTITY_ORG_TENANTS` or continue sign-in acceptance until that read succeeds.

These settings reach ZA Tank only. Do not configure them in Boston. An empty
issuer preserves the existing behavior. **Zitadel is opt-in even with the issuer
set**: only `tervory login --region za --sign-in zitadel` sends
`{"device_name":"…","approval":"zitadel"}`. Plain `tervory login --region za`,
older CLI requests without `approval`, and explicit `approval: "workspace"`
keep the Boston approval path exactly as before. Keep both existing approval
key settings/routes unchanged; Boston's limited key still cannot approve founders.

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
tervory login --region za --sign-in zitadel
tervory chat
tervory logout
```

The browser must open only `https://auth-za.tervory.com`; approve the displayed
code on Zitadel's default page. Tank validates issuer, audience, expiry and
RS256 signature using discovery/JWKS, refreshes unknown signing keys, maps the
reserved organisation ID, and issues the same existing Tank credential format,
one-hour access and rotating 30-day refresh. `user_id` is `zitadel:<sub>`.
Project roles come only from Zitadel's reserved claim for the requesting
application's own Tervory project; other-project claims and metadata are ignored.
Roles are captured at sign-in. **Removing a role in Zitadel does not remove
it from an already issued Tank sign-in: it lasts until that Tank sign-in is
revoked (or expires), including through refresh.** Run `tervory logout` on each
affected signed-in CLI to revoke its existing Tank sign-in and refresh token,
then sign in again for current roles. Repeat for every affected sign-in; logging
out of Zitadel alone is not Tank revocation. The Clerk Workspace's own-sign-ins
page uses the Clerk user ID and does not list `zitadel:<sub>` sign-ins.
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

Why the second resource needs the existing ZA R2 settings: `r2-backup-za` in
`docker-compose.za.yml` has only the `tervory-za` network. `identity-postgres`
has only this resource's private, non-external `database` network and no published
port. The existing worker cannot resolve/reach it. Sharing the identity database
network or publishing Postgres would break this resource's intended isolation.
Therefore the small separate worker reuses the existing backup code and **same
ZA-only Zenas R2 setting names**, bucket and public age recipient in Coolify;
it has only its own database credential, not the main Tank database credential.
Coolify resources do not inherit each other's environment values. The founder
supplies the existing storage values through Coolify; this PR reads none of them
and creates no new storage account, bucket or credential. Successful archive
manifests and the ZA restore drill remain required evidence.

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
