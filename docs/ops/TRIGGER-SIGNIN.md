# Trigger sign-in

Trigger sign-in is the only sign-in for the Workspace, every product host,
the CLI in both regions, the window and mobile. There is no alternate provider,
Workspace device-approval page or automatic fallback. The server and hosted
login run the unchanged, digest-pinned upstream images inherited from #589.
Configuration uses supported APIs only; no upstream source is copied or patched.

## Founder deployment

1. Have Claude review and merge the cutover. Before deployment, preserve the
   existing ZA database and named volumes, and its existing proxy/TLS settings.
   Rename the existing Coolify resource to **trigger-signin-za**, retaining
   `TRIGGER_SIGNIN_VOLUME_PREFIX=identity-za`. Do not recreate its database.
2. On the existing Boston server, add **trigger-signin-us** (not a new box).
   Both resources use `ops/trigger-signin/docker-compose.yml`, raw compose,
   their own PostgreSQL and named volumes. Boston uses volume prefix
   `trigger-signin-us`. The checked-in image digests are authoritative.
3. Keep ZA at **auth-za.tervory.com**; route Boston at **auth.tervory.com**.
   Reuse each box's existing Coolify proxy network, HTTPS entrypoint, certificate
   resolver and valid certificate. API traffic remains h2c behind TLS. Verify
   certificate coverage and existing Cloudflare gRPC/HTTP2-to-origin settings;
   do not change a shared proxy, firewall or paid service to work around a failure.
4. Fill the **names only** in sections A and B of
   [FOUNDER-SETTINGS.md](FOUNDER-SETTINGS.md) directly in Coolify. Use independent
   regional database/master/session secrets. Match each region's
   `TRIGGER_SIGNIN_SETUP_TOKEN` on its Tank and setup job; Boston's
   `TRIGGER_SIGNIN_SETUP_TOKEN_ZA` matches the ZA capability. Never print values
   or rendered compose exports. Retain the existing ZA immutable master key.
5. Deploy Tank's additive registry migration first, then the regional sign-in
   resources and their setup jobs. The existing `tervory-setup` pattern creates
   the Tervory project, public PKCE Workspace app, native device app and project
   roles. Generated `TRIGGER_SIGNIN_ISSUER` and `TRIGGER_SIGNIN_CLIENT_ID` are
   published to Tank and read automatically by Tank and the Workspace. Nobody
   copies an app ID, project ID, organisation ID or subject into Coolify.
6. Setup reads existing tenants through Tank's capability-protected
   `/v1/case-studies/clients` read, creates one native organisation per existing
   tenant, and writes the organisation-to-tenant registry through Tank's
   setup-only API. It never accesses Tank SQL directly or invents a tenant UUID.
   Re-run setup on redeploy and after adding a tenant: existing bindings remain
   immutable and new tenants gain organisations. Renew an expired machine
   credential in Coolify; an expired bootstrap cannot report a successful run.
7. The first native human is created from `TRIGGER_SIGNIN_ADMIN_EMAIL` and
   `TRIGGER_SIGNIN_ADMIN_TEMP_PASSWORD`. Setup records that account's subject
   in Tank's issuer-scoped founder allowlist and grants the Tervory project's
   `org_admin` for the tenant organisations. Change the temporary password at
   first Trigger sign-in; enrol a passkey if desired. Link later admins by
   selecting their native subject in the correct tenant organisation and
   granting that project's `org_admin` in the console. Never match by email.
8. Deploy the Workspace and shared CLI release together. Setup configures
   native light-only branding, the original logo and Inter, approved English
   translations and Trigger sign-in email names. Existing native email bodies,
   code substitutions, action URLs and templates remain upstream-rendered;
   pending post-approval email body rewrites are not applied. Configure SMTP and
   check the native branding/email settings against the approved
   [sign-in frames](../figma/SIGN-IN-FRAMES.md). The 4 Nov sign-up order supersedes
   the older registration-off design prerequisite; it does not authorise a
   custom registration form. Remove the obsolete Coolify names listed in
   Claude's PR. No previous-provider credential is accepted after cutover.

## Acceptance

Offline rows live in `tests/acceptance/test_trigger_signin.py`: S01 sign in,
S02 sign out, S03 organisation switching, S04 CLI US, S05 CLI ZA and S06
client refused founder-only pages. Cryptographic verifier/device/guard tests
use synthetic RSA keys and fake upstream HTTP; database proofs use disposable
PostgreSQL. Offline results are not a claim of live founder acceptance.

After deployment, the founder checks app.tervory.com, each product host and the
window, then `tervory login --region us-east` and `tervory login --region za`.
Each CLI opens only its region's native device approval host. Check sign-out
and revoke, switch A/B/A without leaking either tenant's data, and confirm a
client receives 404 on founder-only pages. Record the deployed head, region,
surface and result, never a password, token or device code.

## Identity and operation

`user_id` is the verified native `sub`, unchanged. Names, email and metadata
are display data, never identity, tenant links or authority. `tenant_admin`
comes only from the requesting Tervory project's signed `org_admin` grant.
Roles from another project or an unlinked organisation are refused. Workspace
service keys alone cannot attest a human. Old opaque credentials and old
device/OAuth codes lack native provenance and are refused immediately.

The shared encrypted backup/restore worker covers each resource's own database;
retain the existing ZA backup settings and enable Boston's separate copy before
live acceptance. Do not delete or rename existing data volumes. The upstream
API identifiers and pinned image paths keep their required original spelling.
The resource, product, setting prefix, emails and reports are Trigger sign-in,
separate from Trigger CRM and its tools/hostname.
