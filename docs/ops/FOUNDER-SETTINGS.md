# Everything the founder fills in, all at once (3 Nov 2026, 16:10 PT)

This is the one list. Every name below is taken from `.env.example` on main or on an open PR branch; none is a guess. You type the values in Coolify, and Claude never sees them. Skip any name you have already filled. Flags marked "leave off" stay off until testing shows there is room.

## A. Coolify settings, Boston (the main app unless noted)

**Shared email** (the morning report and default alerts): SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM

**Market Lab** (free keys): FRED_API_KEY, EIA_API_KEY, CENSUS_API_KEY, LEGISCAN_API_KEY, NOAA_TOKEN, USPTO_API_KEY
**Market Lab email:** MARKET_LAB_SMTP_HOST, MARKET_LAB_SMTP_PORT, MARKET_LAB_SMTP_USER, MARKET_LAB_SMTP_PASSWORD, MARKET_LAB_SMTP_FROM, MARKET_LAB_SMTP_ALERT_ADDRESSES

**Zenas US:** CONGRESS_GOV_API_KEY, LEGISCAN_API_KEY (the same key as Market Lab)
**Zenas review (each room):** ZENAS_REVIEW (default off; scope, identifier and citation checks remain on)
**Zenas email:** ZENAS_SMTP_HOST, ZENAS_SMTP_PORT, ZENAS_SMTP_USER, ZENAS_SMTP_PASSWORD, ZENAS_SMTP_FROM, ZENAS_SMTP_ALERT_ADDRESSES

**Trigger CRM:** TRIGGER_CRM_URL, TRIGGER_CRM_PAT_CONNECTOR, TRIGGER_CRM_TENANT_BINDINGS
**Trigger Google (Business Profile):** TRIGGER_GOOGLE_OAUTH_CLIENT_ID, TRIGGER_GOOGLE_OAUTH_CLIENT_SECRET
**Trigger Facebook** (#624): TRIGGER_META_APP_ID, TRIGGER_META_APP_SECRET
**Trigger WhatsApp** (#624): TRIGGER_WHATSAPP_APP_SECRET, TRIGGER_WHATSAPP_VERIFY_TOKEN, TRIGGER_WHATSAPP_TOKEN_CONNECTOR, TRIGGER_WHATSAPP_BINDINGS (includes each number's timezone)
**Trigger chat bot:** TRIGGER_BOT_HANDOVER_ADDRESSES, TRIGGER_BOT_TRUSTED_PROXY_CIDRS

**Tisan:** TISAN_COOLIFY_URL, TISAN_COOLIFY_TOKEN, TISAN_SITES_REPO, TISAN_GITHUB_TOKEN, FIGMA_TOKEN, TISAN_FIGMA_FILES

**Autumbra (Ghost app):**
- Edge: CLOUDFLARE_API_TOKEN_ENFORCE, AUTUMBRA_EDGE_CREDENTIAL, AUTUMBRA_EDGE_WEBHOOK_SECRET, AUTUMBRA_CLOUDFLARE_WEBHOOK_SECRET
- Google Workspace alerts: AUTUMBRA_GOOGLE_PUSH_AUDIENCE, AUTUMBRA_GOOGLE_PUSH_SERVICE_ACCOUNT
- Health and Undo: AUTUMBRA_HEALTH_SECRET, AUTUMBRA_HEALTH_URL (#649), AUTUMBRA_UNDO_TOKEN_SECRET, AUTUMBRA_MAILBOX_WEBHOOK_SECRET
- Email: AUTUMBRA_SMTP_HOST, AUTUMBRA_SMTP_PORT, AUTUMBRA_SMTP_USER, AUTUMBRA_SMTP_PASSWORD, AUTUMBRA_SMTP_FROM
- One Enforce per client (#622; on the enforce-lifecycle service only, never on Watch): AUTUMBRA_COOLIFY_URL, AUTUMBRA_COOLIFY_TOKEN (read and write, no deploy), AUTUMBRA_COOLIFY_PROJECT_UUID, AUTUMBRA_COOLIFY_SERVER_UUID, AUTUMBRA_COOLIFY_ENVIRONMENT, AUTUMBRA_COOLIFY_GITHUB_APP_UUID, AUTUMBRA_LIFECYCLE_KEY (on Tank and enforce-lifecycle only)
- Code-fix PRs: GHOST_GITHUB_TOKEN, GHOST_PATCH_PR_ENABLED

**Radix** (#651, breach watch): HIBP_API_KEY, only if Have I Been Pwned's domain search is free for your domains.

**Brains** (leave off): TIGER_BRAIN_ENABLED, ZENAS_BRAIN_ENABLED; SANDBOX_KEY_TIGER, SANDBOX_KEY_ZENAS (fill these now; they are only used when a brain is on).

**Rig** (only at Custom Nation go-live): RIG_WIDGET_PUBLISHABLE_KEY. Rig 3D (off): HF_JOBS_TOKEN, HF_JOBS_NAMESPACE.

## B. Coolify settings, ZA box

- LAWS_AFRICA_API_TOKEN (if not already set; question-time retrieval only, never training)
- ZENAS_REVIEW (ZA room; default off)
- ZA regulation email uses the same ZENAS_SMTP_HOST, ZENAS_SMTP_PORT, ZENAS_SMTP_USER, ZENAS_SMTP_PASSWORD, ZENAS_SMTP_FROM and ZENAS_SMTP_ALERT_ADDRESSES names above, on the ZA room.
- Existing Zenas training handoff: TANK_KEY_ZENAS on ZA Tank; its matching TANK_KEY on the ZA Zenas room. Never use the Workspace TANK_API_KEY for this room handoff.
- Zenas training: HF_TOKEN, HF_ORG; HF_TRAIN_MAX_USD is optional (default 50); ZENAS_OWN_MODEL_KEY (dedicated ZA llama.cpp server key)
- ZENAS_BRAIN_ENABLED (leave off), SANDBOX_KEY_ZENAS

## C. Domains and accounts (once, in Coolify or the provider)

1. Coolify: attach **trigger.tervory.com** and **rig.tervory.com** to the app.tervory.com application, after those two PRs merge. agent-rig keeps rig.tervory.com as well.
2. Database: the restricted database role that turns RLS on (#573).
3. Backups: a second offsite bucket (B2) for the 3-2-1 copy.
4. Meta: the Meta app and the WhatsApp business number (they produce the Trigger Facebook and WhatsApp values above).
5. Google Cloud: the project with Business Profile API access (it produces TRIGGER_GOOGLE_OAUTH_*).
6. GitHub repository secrets (not Coolify): CLI_RELEASE_SIGNING_KEY, CLI_RELEASE_SIGNING_PUBLIC_KEY. Only needed to sign CLI releases.

## D. Wording only you can write (legal text)

1. Radix: the client consent text a tenant admin agrees to before an active scan of their domain (#651).
2. Chat bot (**D2**): the client’s privacy notice and conversation-retention wording (decision 35). The shipped retention job removes expired conversations after 12 calendar months; agree the wording against that behavior before enabling capture. Save the actual notice and its version as tenant data fields `privacy_notice` and `notice_version` using the existing confirmed `trigger.bot.settings` tool. They are not environment settings. Without both, visitor lead/quote capture stays disabled; changed versions require a fresh notice before submission.

Nothing else needs you before testing. Any name a later PR adds is added to this file, not sent separately.

**Street Law (ZA):** ZENAS_REVIEW is the existing room-wide review setting; Street Law still requires human review while pre-launch even when that setting is off. No Street Law key or bypass switch is added.

## Rig store rooms (layout B)

On the existing isolated enforce-lifecycle service only: RIG_COOLIFY_URL, RIG_COOLIFY_TOKEN, RIG_COOLIFY_PROJECT_UUID, RIG_COOLIFY_SERVER_UUID, RIG_COOLIFY_ENVIRONMENT, RIG_COOLIFY_GITHUB_APP_UUID. Use a dedicated Rig-only team/project/environment and the same server UUID as shared Rig. Token permissions: read, write and deploy (Coolify requires deploy for application DELETE); no root or read:sensitive. Do not reuse Autumbra’s token.

On Tank and enforce-lifecycle only: RIG_LIFECYCLE_KEY. It must differ from AUTUMBRA_LIFECYCLE_KEY and all room keys.

Per store application only: RIG_ROOM_DB_PASSWORD (unique URL-safe value), plus the existing names in the create receipt’s founder_fills. The lifecycle supplies RIG_ROOM_TENANT, RIG_ROOM_NAME, RIG_ROOM_DATA_VOLUME, RIG_ROOM_DB_VOLUME and RIG_ROOM_NETWORK; never edit these bindings. Existing R2 settings are needed for the retained bucket snapshot before destroy. See [Rig room operations](RIG-STORE-ROOMS.md).

Existing per-room names used by the room template and retention step: TANK_KEY_RIG, RIG_RETAILER_KEY, RIG_TRUSTED_PROXY_CIDRS, RIG_WIDGET_PUBLISHABLE_KEY, R2_ACCOUNT_ID, R2_ACCESS_KEY_ID_RIG, R2_SECRET_ACCESS_KEY_RIG. Store mail uses the existing SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD and SMTP_FROM names. These are names only; values belong in the owning application.
