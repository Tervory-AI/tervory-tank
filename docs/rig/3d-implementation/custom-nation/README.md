# Custom Nation case-study intake

This is a bounded, offline intake of three existing website collection entries, not a live catalogue import, generation job, model approval or training dataset. It copies no photos into Rig and changes no website content. The recipe pins the documented live-source repository, rather than the separate vinext experiment. Each checkpoint stores the source commit, catalogue hash/JSON pointer, photo path/hash and every product association. Public photo URLs are references: fetching the first URL in this cloud session returned HTTP 403, so availability to the terminal still requires coordinator verification.

The selected entries are `hardy-hybrid` (The Hybrid), `grayboe-phoenix-2` (Phoenix 2) and `falcon-t50i` (T50i+). Their photos are already tracked under `public/images/brand-photography/` in the pinned Custom Nation source. The source's `docs/handoffs/task-2-evidence/audit-media.json` and `docs/handoffs/TASK-2-PROVENANCE.md` retain prior media inspection and owner-review caveats. An appearance reference does not establish reconstruction suitability, complete multi-view coverage, scale, dimensions, attachment geometry, compatibility or reuse rights.

All 46 source collection rows lack SKU values. Consequently the three checkpoint rows have `sku: null`, missing geometry and no executable requests. Historical `agents/rig/catalogues/customnation` demo rows, moved out of runtime in Tank #563, are not an authoritative mapping. Do not substitute source slugs, historical Archon demo SKUs or invented prices for the retailer's actual catalogue identifiers.

## Reproduce or resume intake

Use the pinned source checkout and the room's ordinary Python dependencies. No model, bucket, database or production credential is needed:

```sh
PYTHONPATH=agents/rig:agents/_chassis:tank python -m rigbox.three_d.batch \
  --source-root /path/to/custom-nation-preview \
  --recipe docs/rig/3d-implementation/custom-nation/recipe.json \
  --output /private/local/case-study-checkpoints
```

The source commit and every selected file's Git object are verified. Dirty bytes, symlinks, escaping paths, ambiguous slugs and selections larger than five are rejected. Photos deduplicate by SHA-256 while preserving separate product records. Identical inputs resume the same immutable content-addressed checkpoint; changed mapping, measurement or review evidence creates a new checkpoint and preserves the earlier one. No automatic submission or retry of uncertain remote work exists here.

## Required coordinator inputs

For **each selected entry**, supply the authoritative catalogue SKU/product ID and variant, the tenant-scoped mapping evidence, and the intended tenant/home region. Confirm the exact photo depicts that SKU/variant and is authorised for the proposed appearance/reconstruction use. Public availability alone grants neither generation nor training permission; current robots signals explicitly deny AI training.

For the no-spend CPU route, supply one actual embedded GLB/OBJ/PLY scan, source units (`unit_mm`), measured width/height/depth in the scan's coordinate frame, named attachment positions and unit quaternions, and a measurement record identifying the physical item and method. Supply separately approved fit mappings for assembly; this tool never creates them. Photos and catalogue image pixel sizes are not physical measurements.

Optional `--preparations` accepts a private JSON object keyed by one of the selected source slugs. Each entry must provide `sku`, `tenant_id`, `home_region`, `mapping_evidence`, `measurement_evidence`, `scan_path` (tracked relative path in the source checkout), `unit_mm`, `dimensions_mm` and `anchors`. The anchor shape is the existing Rig contract (`position_mm`, `quaternion`). No sample tenant, measurements or anchors are supplied for Custom Nation. Forge's existing contract currently accepts only `us-east`; this is not authority to place Custom Nation data there. The coordinator must resolve intended regional placement before any submission.

When these inputs exist, the tool validates a Forge `method: scan`, zero-cost-cap request and deterministic tenant/SKU/input-bound job UUID, then exports it as pending CPU validation. It performs no upload or service call. The coordinator uses existing authenticated brain/Forge contracts, retains the same job ID for polling/resume, and checks the actual draft/report/zero-cost receipts before human review. Geometry checks and the existing checksum-bound approval process remain mandatory. Approval is never inferred from an intake request.

An optional `review_outcome` preserves `outcome` (`accepted` or `rejected`), exact `artifact_sha256`, evidence reference and the existing three human checks (`scale`, `appearance`, `attachment_points`). Accepted records require all checks; rejected records preserve failed checks. This is historical provenance only: `approval` remains `not_reviewed` in the intake, and no serving record is modified. Every record remains `training.status: not_authorized`. A future learning loop needs a separate explicit rights decision, scope, lineage and revocation policy; uploading, converting or approving a product model is not training consent.

The existing Figma-approved frames and widget/admin flows remain the UI source of record. Real terminal configuration, model approval, quotes and delivery evidence belong to the coordinator/founder acceptance run. This batch establishes no Monday readiness.
