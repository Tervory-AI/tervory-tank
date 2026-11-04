# Rig 3D frames 06–07: waiting for approval

Wave 4 check, 3 November 2026: no approval record for the Custom Nation 3D
frames exists in `docs/figma`. The approved US cart register concerns cart
screens S06/A07; those are not approval of the following 3D frames.

| Frame | Needed approval |
| --- | --- |
| 06 · 3D view | Shopper viewer entry, model interaction, approved-model selection, loading/unavailable fallback and responsive layout |
| 07 · Dealership terminal | Terminal layout, quote/contact flow, reset and disconnected states |

These are pending requirements, not invented Figma node IDs or approved copy.
The existing widget's 3D entry remains hidden. Do not wire `openThreeD` into it
until both approved frames and their exact node references are recorded here.

The backend is already built: `rig_3d` is tenant-scoped; only the internal room
key can change the entitlement; models must pass automatic checks and a human
review of scale, appearance and attachment points before public serving. Fit
anchors must also be approved. Revocation blocks existing model URLs and
assemblies. The offline Wave 4 lifecycle test proves grant → review → approved
assembly → revoke → restore without a billing or GPU call.

GPU routes remain off. `RIG_FORGE_TRELLIS_ENABLED` is not enabled by this work;
no conversion service, subscription or payment path is activated. Custom Nation
continues quote → retailer invoice → EFT outside Rig.
