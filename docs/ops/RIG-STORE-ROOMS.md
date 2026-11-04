# Rig store rooms

Layout B gives each store one Coolify Compose application: the existing Rig data
plane and its private Postgres. Brain, browser and 3D workers stay shared; GPU
paths remain off. Existing embeds keep their original API paths. Newly issued
room snippets use `https://rig.tervory.com/v1/rig/rooms/{store-uuid}` as api-base;
the unchanged widget appends its normal `/v1/rig/...` URLs. The shared Rig host
forwards this explicit corridor to that fixed UUID's room. It never substitutes
another store or falls back when a room is unavailable. The gateway forwards
the resolved client address, discarding shopper-supplied forwarding headers.
Set RIG_TRUSTED_PROXY_CIDRS on each store room to trust the shared gateway’s
actual corridor address range; shared Rig continues to trust its own proxy range. No retailer-control path
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
   `backups/room-retained.json`, then acknowledges retention. This manifest
   names immutable, hashed JSON parts of at most 16 MiB, so the snapshot is not
   limited to one bucket object. An incomplete part upload never publishes a
   new manifest or permits deletion. If archival fails,
   no Coolify DELETE is issued. The room remains frozen for recovery; do not
   repeat provisioning or manually delete its retained volumes.
6. DELETE has `delete_volumes=false`, `delete_connected_networks=false` and
   `docker_cleanup=false`; it cannot remove the shared Rig corridor. Both database
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
existing deployment workflows redeploy the main stacks (Tank/Workspace and
companions), the Ghost resource (Watch and lifecycle), and the shared Rig
resource, including their registered regional copies; no live resource was changed here.
The per-store template is US-only. A lifecycle receipt proves resource creation,
not deployment readiness, measured capacity or founder browser acceptance.

## Measure rooms locally

Run on the disposable Coolify test host, never the founder’s laptop or a live
store deployment. Docker and Python 3 are the only host tools. No Coolify token,
model key, SMTP credential, store credential or cloud k6 account is used.
From this checkout:

```sh
mkdir -p .tmp
export TMPDIR="$PWD/.tmp"
docker build --label tervory.test=1 -f agents/rig/Dockerfile -t "$(basename "$PWD"):load" agents
python3 tests/load/rig_rooms_load.py --rooms 2 --duration 60s
```

The harness launches N actual Rig data planes, each with a private Postgres and
network. A separate internal network carries only the local generator traffic.
It seeds the neutral Core fixture, then runs the production search/quote HTTP
paths. No shared brain/browser/3D worker is copied. Model and email paths are
unconfigured; quote storage and receipts still run. The application/database
CPU and memory limits match the room template. All `docker run` calls use
`--rm`, `tervory.test=1`, and a name beginning with this checkout’s folder name.
Only synthetic data uses temporary filesystems; no named volume is deleted.

k6 is pinned to [v0.54.0](https://github.com/grafana/k6/releases/tag/v0.54.0),
Linux amd64 image digest
`sha256:32000aaa40b848add83425ed7cc77535c343ca473498b0bd29464d00fdca6c79`.
It runs locally with usage reporting disabled and no cloud output. Search runs
about once per second per store; quotes are spaced 16 seconds apart to respect
the production abuse controls. The harness does not disable or spoof those
controls. A short smoke duration produces few quote samples; use longer runs
for useful percentile estimates.

Results are in `.tmp/rig-room-load-<id>/measurement.json`, alongside
`raw-k6.json`, `rooms.json` and `k6.log`. The report includes global/per-room p95
search and quote times in milliseconds, sampled Docker working-set bytes for
each app/database, maximum sampled aggregate memory, test duration, image and
Git revision, and failed checks/HTTP requests. These are working-set samples,
not RSS or a guaranteed peak. Failed checks, missing samples or failed requests
refuse a successful measurement. Ambiguous container startup is cleaned by its
pre-reserved fixture name. If Docker will not acknowledge cleanup, retry only
the recorded commands in `cleanup-pending.json`; never prune the Docker host.

Repeat with the founder’s chosen N after checking test-host headroom. Include
shared-worker and operating-system baseline consumption when deciding a
clients-per-box figure. This harness measures store data planes after startup;
it does not validate browser/GPU/model workloads or extrapolate capacity.
**About 60–80 clients on a KVM 8 remains unmeasured.** `capacity_claim` stays null.
The CI fixture replay verifies the real k6 scenario and report contracts without
Docker or an external service; its timing values are synthetic, not benchmarks.

The store-room lifecycle requests `is_raw_compose_deployment_enabled=true` at
creation, matching the template’s first-line raw Compose marker. This prevents
Coolify from adding its application network to the private database. The API
field is documented in [Coolify’s private GitHub application endpoint](https://coolify.io/docs/api/endpoints/applications/create-private-github-app-application).
