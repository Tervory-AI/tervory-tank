# Rig store rooms

Layout B gives each store one Coolify Compose application: the existing Rig data
plane and its private Postgres. Brain, browser and 3D workers stay shared; GPU
paths remain off. Existing embeds keep their original API paths. Newly issued
room snippets use `https://rig.tervory.com/v1/rig/rooms/{store-uuid}` as api-base;
the unchanged widget appends its normal `/v1/rig/...` URLs. The shared Rig host
forwards this explicit corridor to that fixed UUID's room. It never substitutes
another store or falls back when a room is unavailable. No retailer-control path
is exposed through that corridor. Room webhooks must use that same api-base plus
`/v1/rig/commerce/webhooks/{store-uuid}`; their raw bodies/signatures survive.

## Founder setup

Use the existing **enforce-lifecycle** service and its single worker, not a second
controller. Rig subclasses `CoolifyEnforceBackend` from Autumbra; signing, lock,
Coolify client, provenance checks and retained-volume deletion are reused.
Set the names in [FOUNDER-SETTINGS](FOUNDER-SETTINGS.md#rig-store-rooms-layout-b).
Only this isolated service receives the dedicated Rig Coolify token. The Rig
team contains only Rig store resources. Grant read/write/deploy (DELETE needs
deploy), without root or read:sensitive. Use the same server as shared Rig.
Tank and lifecycle alone receive `RIG_LIFECYCLE_KEY`, distinct from every other
key. Watch, shared Rig, store rooms, browser and brain receive no Coolify token
or lifecycle key. No ingress, Docker socket or privileged container is added.

1. In the test store's `/chats`, enter `rig.store.onboard`, review the existing
   Confirm card and confirm. The actor's authenticated tenant is the store;
   supplying a different tenant argument is rejected. A non-admin cannot onboard.
2. The receipt reports a created Coolify application and its `founder_fills`
   setting **names**. As with Autumbra, creation is deliberately undeployed:
   fill these names in this store application and deploy through Coolify.
   `RIG_ROOM_DB_PASSWORD` must be unique and URL-safe. No builder obtains a secret
   value, and no application auto-deploys before credentials exist.
3. Do not edit the five supplied identity/volume/network bindings. A retained
   database cannot be rebound to another UUID. Tenant-bearing tables receive a
   fixed-store CHECK constraint; private controls, authenticated keys and storage
   also reject foreign tenants. The database has no shared-room network access.
4. `rig.rooms.list` lists only this store's named application. Configure store
   settings, catalogue and cart through existing Rig admin paths; Tank routes
   these operations to the provisioned store room. Create a fresh embed key there.
   Existing stores are not silently moved or copied; their old snippets continue
   to work until an explicitly planned data migration.
5. `rig.store.destroy` requires another Confirm card. The room first freezes
   writes, snapshots all its tenant tables into its private bucket prefix under
   `backups/room-retained.json`, then acknowledges retention. If archival fails,
   no Coolify DELETE is issued. The room remains frozen for recovery; do not
   repeat provisioning or manually delete its retained volumes.
6. DELETE has `delete_volumes=false` and `docker_cleanup=false`. Both database
   and data volumes, the bucket snapshot and existing bucket objects remain.
   The registry remains as a tombstone, so destroyed stores cannot fall back to
   the shared catalogue. Another store's application and data are untouched.

A lost or ambiguous Coolify mutation is recorded as unknown and is never
retried automatically. Inspect Coolify and the receipt before reconciling the
registry; there is no guess-and-create fallback. These operations do not delete
bucket objects, credentials in the store's existing sealed vault, or volumes.
The bucket snapshot contains private store data: keep its bucket private.

Rig never takes payment, holds a card or refunds. Supplier identities stay
private. Custom Nation remains quote → the store's own invoice → EFT; US stores
use the store cart and checkout.

Runtime changes ship in this single PR as explicitly requested. On merge,
existing deployment workflows rebuild Tank, Ghost's lifecycle image and Rig,
including their registered regional copies; no live resource was changed here.
The per-store template is US-only. A lifecycle receipt proves resource creation,
not deployment readiness, measured capacity or founder browser acceptance.
