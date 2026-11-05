# Trigger sign-in

One Trigger sign-in serves every user in every country at **auth.tervory.com**
on the existing Boston server. The sole Coolify resource is **trigger-signin**,
in `ops/trigger-signin/`, with its own PostgreSQL and named volumes. ZA runs no
sign-in server or setup job. Region selects where work runs, not identity.
Zenas ZA, ZA Tank, the Workspace, all product hosts, CLI, window and mobile
trust this same issuer. There is no fallback or Workspace device approval page.

## Founder deployment

1. Fill the setting names in sections A and B of
   [FOUNDER-SETTINGS.md](FOUNDER-SETTINGS.md) directly in Coolify. No secret values
   or rendered compose exports belong in Git. Only Boston Tank and setup receive
   the setup token. The read-only configuration token is shared by Boston
   Tank/Workspace/setup and ZA Tank; it cannot write links, grant roles, mint
   sessions or approve devices. Match the own-session key between the Workspace
   and ZA Tank for authenticated list/revoke only.
2. Have Claude review and merge the coordinated cutover. Deploy Tank's additive
   registry schema and consumers, then the single Boston resource from
   `ops/trigger-signin/docker-compose.yml`. Use its pinned image digests and the
   existing Coolify proxy network, HTTPS certificate and h2c API transport.
   Do not create another server, attach a Tank database or delete old volumes.
   The Boston database/bootstrap/login volumes retain their previous physical
   names so renaming the resource cannot silently create an empty database.
   Those storage names are not additional sign-in resources or issuers.
3. Run Boston's `tervory-setup`. The reused #589 pattern creates one Tervory
   project, public PKCE Workspace app, native CLI device app and project roles.
   It reads existing tenants through both Tanks' capability-protected
   `/v1/case-studies/clients` APIs, deduplicates UUIDs and creates one native
   organisation per existing tenant regardless of home region. It writes
   immutable links only to Boston's registry API, never directly to SQL.
   Re-run after adding tenants and on redeploy. Expired machine credentials
   fail closed and must be renewed in Coolify.
4. Project/client IDs and issuer are published automatically to Tank and the
   Workspace. Generated setting names are `TRIGGER_SIGNIN_ISSUER` and
   `TRIGGER_SIGNIN_CLIENT_ID`; nobody copies IDs, subjects or JSON mappings.
   ZA Tank reads the canonical registry through the authenticated, no-store
   Boston Workspace configuration endpoint; it never accepts a local issuer
   or an alternative if Boston is unavailable.
5. The first founder account is created from `TRIGGER_SIGNIN_ADMIN_EMAIL`.
   Its initial password is Coolify-generated and nobody uses it. Setup turns on
   email from the `TRIGGER_SIGNIN_SMTP_*` settings (the password is referenced
   from the existing Coolify mail secret by name, never viewed or typed) and
   sends the founder one setup email to set their own password and, if wanted,
   a passkey. Setup records the founder's native subject in the founder
   allowlist and grants the Tervory project's `org_admin` in the tenant
   organisations. Later admins are linked by native subject and tenant, never
   email. Self-registration grants no tenant access.
6. Deploy the Workspace and shared CLI release together. Setup configures native
   branding, the original logo/Inter and Trigger sign-in page/email names against
   the approved [frames](../figma/SIGN-IN-FRAMES.md), using supported APIs only.
   Preserve upstream email bodies, action
   URLs and substitutions. Remove obsolete Coolify names listed in the PR.
   Keep retired regional data volumes untouched: no automatic account matching,
   live-data migration or deletion is implied.
7. Enable the encrypted backup worker for Boston's single database and preserve
   its private bootstrap volume. Founder acceptance covers app.tervory.com,
   product hosts, window, and `tervory login --region us-east` plus
   `tervory login --region za`. Both approve at auth.tervory.com; only work
   endpoints differ. Check sign-out, own-session revoke, organisation A/B/A
   isolation and client refusal on founder pages. Record head, work region,
   surface and result, never secrets or device codes.

## Identity and operation

`user_id` is the verified native `sub`, unchanged across work regions. Email,
names and metadata are display data only. `tenant_admin` comes only from the
requesting Tervory project's signed `org_admin` grant. Other project roles,
unlinked organisations, unsigned human assertions and retired credentials are
refused. Private conversations and CLI sessions retain the verified issuer.

Setup reserves native organisation IDs durably before creation in its private
bootstrap volume. Retries recover by reserved ID, never name or email. Published
Tank bindings remain authoritative. Losing a pending reservation requires
operator reconciliation, not automatic identity matching.

The unchanged, digest-pinned upstream images inherited from #589 are configured,
never patched, forked or renamed inside their AGPL-3.0 source. Required upstream
image/API spellings remain unchanged. Trigger sign-in is separate from Trigger
CRM and its tool namespace and hostname.

Offline rows S01–S06 in `tests/acceptance/test_trigger_signin.py` cover sign in,
sign out, organisation switching, both CLI work regions and founder refusal.
Synthetic RSA keys/fake upstream HTTP and disposable PostgreSQL prove integration
boundaries, not live founder acceptance or historical screenshot validity.
