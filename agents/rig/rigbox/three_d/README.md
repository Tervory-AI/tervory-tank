# RIG-5: approved 3D engine

Industry-neutral stand-ins only. CAD, AI and scan conversion belong to RIG-5F;
this engine never installs Blender or runs a GPU job. The forge is not merged;
draft PR #254 has not published a job/relay interface at the revision inspected
(b1e68c7). `StubForge` and `BrainForge` implement the same
`submit(Job)`, `poll(Job)`, `artifact(Job)` interface, contract `rig-forge/1`.
The brain relay uses POST `/forge/jobs`, GET `/forge/jobs/{id}` and
GET `/forge/jobs/{id}/artifact`, with tenant scoping and header authorization.
RIG-5F must expose this relay or adapt this boundary when its final contract is
available. This is an explicitly proposed contract, not a verified live forge.

Each request names tenant-owned bucket inputs, real millimetre dimensions,
polygon/byte limits, cost cap and timeout. CAD is preferred, then AI (one to four
photos), then scan (50–70 photos). Failed automatic checks never enter review.
Approval separately confirms scale, appearance and anchors. The public API
returns only current approved fits and approved model revisions.

The test entry point uses `StubForge` and tenant-private disk storage. Production
uses the existing Rig R2 adapter and a brain relay. The forge owns conversion
receipts and Tank owns paid-job cost-cap enforcement; the engine retains receipt
identifiers. Stand-in receipts are explicitly synthetic, zero-cost identifiers.

Deploy using the existing Rig image with the command
`uvicorn rigbox.three_d.asgi:app --host 0.0.0.0 --port 8000`.
This opt-in entry point retains the original app/lifespan and registers only
RIG-5 routes, without modifying another lane's `app.py` or Compose file.
The existing image already copies `rigbox/` and `schema.sql`.

An internal room-authenticated entitlement route controls `rig_3d`; retailer
administrators cannot grant their own paid add-on. Price stays unset until the
founder sets it. The capability response exposes the add-on billing summary.
The existing Workspace billing screen is outside this lane's allowed files;
its Stripe subscription-to-entitlement integration is a separate wiring step.

Drafts remain private in the `tervory-rig` bucket. Approved models are served
through the key-gated route. A CDN may front this route only if it forwards
`X-Rig-Key` and respects `private, no-store`; there are no secret-bearing URLs
or public draft paths. The kiosk keeps short-lived approved models locally.

## Cloud sample and checks

Use an isolated Postgres database, Python 3.12 with Tank's requirements, and
Chromium. From the repository root set `PYTHONPATH=tank` and
`READ1_CHROMIUM_EXECUTABLE` to the installed Chromium executable. Run
`python -m pytest -q tests/test_rig_3d_engine.py tests/test_rig_postgres.py`
with `RIG_TEST_DATABASE_URL` pointing to the local test database. These tests
create their own empty databases, apply the room schema twice and remove only
the databases they create.

Build the companion at `tervory-rig/widget/src/three/`, then run its
`package-widget.mjs` with the absolute destination of this folder's `widget/`
subdirectory. For the stand-in app, set `PYTHONPATH=agents/rig:agents/_chassis`,
`RIG_3D_TEST_DATABASE_URL`, `RIG_3D_TEST_DATA_DIR`, and optionally
`RIG_3D_WIDGET_DIR`. Start `python -m uvicorn rigbox.three_d.demo:app --host
127.0.0.1 --port 8035`. `/health` must return `ok: true, sample: true`; `/3d/`
is the plain page. `?photos` selects the sample tenant without the add-on.
These environment variables are local test settings only, not Coolify secrets.
The sample seeds reviewed neutral fixtures in its own database, including one
taller alternative to demonstrate a server-approved swap. No real supplier,
retailer catalogue, contact or paid job is used.

## Remaining integration boundaries

- The production entry point never seeds samples, grants an add-on or creates
  sample receipts. R2 uses the existing Rig credential names. No new key is
  introduced. A missing connection fails closed.
- For the deployed plain page, put public-only configuration in
  `$DATA_DIR/rig-3d-page.json`: `publishable_key`, `product_id`, `kiosk_id`, and
  optional `photo_key` for a separate non-entitled test tenant. Use an existing
  **publishable** key only. Private/admin keys are rejected. Each physical
  terminal needs a distinct configured UUID, never a shopper identifier.
- The brain relay/job contract must be reconciled with RIG-5F before real
  conversion. Actual receipts/caps and R2/CDN transfer are unverified until
  that lane and secure settings are available. The stub is not a live forge.
- Existing Workspace billing/Stripe hooks and `/rig/admin` controls belong to
  other lanes and are not edited here. Their required calls are the internal
  entitlement route, administrator job/review/mount routes and terminal reset.
  The billing summary on the test page does not claim a Stripe integration.
- Until frames 06–07 are approved, the existing widget does not expose a 3D
  button; its caller integration is `openThreeD(host, client, request, kioskId)`.
- Kiosk snapshots expire after five minutes. Quotes require a connection and
  are never queued locally. A remote reset takes effect on the next successful
  five-second poll; it cannot reach a disconnected terminal. No contact is cached.

## Prove it after deploy

1. Retain the existing `/health` response and catalogue routes after selecting
   `rigbox.three_d.asgi:app`. Configure the public test page and use stand-in
   data only on Boston; do not bring in live ZA shopper data.
2. With a tenant's publishable header, read `/v1/rig/3d/capabilities` and POST
   `/v1/rig/3d/assembly` with the test product. A disabled tenant must have
   `rig_3d: false`, get 403 for models and fetch no viewer chunk.
3. Inspect that tenant's `agent_rig.rig_3d_jobs`: failed checks never have
   `status='draft'`; reviewed rows have `status='approved'`, the check report,
   receipt references, reviewer and timestamp. Inspect its fit row's
   `mount_points` and verify the part is still approved.
4. Open `/3d/`: rotate, zoom, explode and swap the neutral parts; verify the
   indicative total. At 1920×1080, open terminal mode, request a sample quote,
   and find its tenant-scoped `agent_rig.quotes` row. An acknowledgement means
   stored, not a confirmed email/Odoo delivery unless RIG-4 returns `sent`.
5. POST the administrator terminal reset route. Its tenant-scoped
   `agent_rig.rig_3d_kiosks.revision` must increment and the connected terminal
   must clear contact/build state. No production deployment was performed here.
