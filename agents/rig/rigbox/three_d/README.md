# RIG-5: approved 3D engine

Industry-neutral stand-ins only. CAD, AI and scan conversion belong to RIG-5F;
this engine never installs Blender or runs a GPU job. The forge was absent from
main during implementation. `StubForge` and `BrainForge` implement the same
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
