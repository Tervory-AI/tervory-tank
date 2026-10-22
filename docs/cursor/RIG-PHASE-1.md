# RIG phase 1: the whole of Rig, built and live for Custom Nation, with the 3D upgrade

> Written 22 Oct 2026. Founder: "I want the entire Rig built so phase 1 is done. We still have to add 3D upgrade to it. 3D is not going to be for everyone. But it must be built for Custom Nation." Also: "You cannot give it live feeds until the infrastructure is built."
>
> **Where Rig stands (22 Oct):**
> - Live at `https://rig.tervory.com` (Boston), healthy.
> - The public API (`tervory-rig/docs/api.md`), skills (search, setups, explain, ask, fit_suggest) and catalogue reads through Tank (#199, #202) are done.
> - The Custom Nation catalogue is a **18-row stand-in sheet** with demo ZAR prices.
> - The widget (`Tervory-AI/tervory-rig`) runs on mock data.
> - Rig has no brain, browser or sandbox of its own yet.
>
> **Design:** Figma `uRpPy3Hns0WxWZYTPwZ2ni`, frames 01–05 (search, results, complete your setup, can't find it, the explore graph). There are no 3D frames yet.

## How it runs: all five lanes in parallel, now (founder, 22 Oct 11:13)
> "Forget anything to do with my suppliers or API keys. Those come last. The infrastructure needs to be built and complete."

**Phase 1 is the complete machine, running on stand-in data.** Every lane uses fixtures, sample feeds and stand-in 3D models. Real suppliers, supplier keys, Custom Nation's Odoo login and the makers' CAD files are plugged in **last**, as configuration only, with no new code. Every lane builds the adapter, the screen and the test now, and leaves the real credentials as a named, empty Coolify setting.

**Rig is built neutral (founder, 22 Oct).** Rig is a product for any retailer. Build every lane industry-neutral, with neutral stand-in data and neutral stand-in 3D models; no retailer- or industry-specific content in code, fixtures or models. Custom Nation comes with its own skin, which already exists (`theme="custom-nation"` in `tervory-rig`), and its catalogue is loaded last, as data. Don't add to or change the existing `customnation` catalogue files.

The lanes run **in parallel**. To keep merges clean, each lane owns its own files:

| Lane | What | Builder | Owns |
|---|---|---|---|
| **RIG-2** | Rig's own box: brain, sandbox, sealed browser, storage, memory | Codex | `agents/rig/` compose, Dockerfiles, `brain/`, `ops/seal-check.sh`, `tests/test_room_seal.py`, `tests/test_rig_box*.py` |
| **RIG-3** | Feed machinery, price rules, fit approval, retailer admin, on sample feeds | Codex | `agents/rig/rigbox/` (feeds, pricing, fits), `tank/access.py` (Rig mapping only), `workspace/app/rig/admin/`, `tests/test_rig_feeds*.py` |
| **RIG-4** | The widget complete to Figma 01–05, the quote handoff (Odoo adapter stubbed), bundle hosting, analytics | Codex | `Tervory-AI/tervory-rig`, plus `agents/rig/rigbox/quotes/` and `tests/test_rig_quotes*.py` |
| **RIG-5a** | 3D frames 06–07 in Figma | Codex | Figma `uRpPy3Hns0WxWZYTPwZ2ni` only |
| **RIG-5F** | The 3D forge: every 3D tool brought in, pinned and sealed, plus the GPU jobs | Codex | `agents/rig/forge/` (new service), `agents/rig/docker-compose.yml` (the forge service only), `ops/seal-check.sh` (forge entries), `tests/test_rig_forge*.py` |
| **RIG-5** | The 3D engine: asset pipeline, mount points, `rig_3d` entitlement, viewer chunk, kiosk mode, on stand-in models | Codex | `agents/rig/rigbox/three_d/`, `tervory-rig/widget/src/three/`, `tests/test_rig_3d*.py` |

**How the lanes meet:**
- **Shared tables:** each lane adds its own additive schema in `agents/rig/schema.sql`, in its own clearly marked block. Merge main before marking ready, and keep every other lane's block.
- **RIG-5 builds the engine now** (pipeline, anchors, entitlement, loader, viewer core, kiosk shell) and wires its screens to frames 06–07 once the founder approves them. Until then the viewer runs in a plain test page.
- **Deploy order:** whichever lane merges first deploys. Tick Raw Compose on agent-rig before RIG-2 merges.

**Hard rules for every Rig lane:** `docs/cursor/CONTEXT.md`, `AGENTS.md` and `tervory-rig/AGENTS.md`. In particular:
- One indicative total. Cost, duty and margin never reach the browser.
- Only parts with an approved fit are shown.
- No checkout; every path ends in a quote.
- The widget code is industry-neutral.
- No secrets in the widget.
- **Custom Nation is a ZA client:** its live shopper data (quote contacts) will be stored on the new ZA host. Phase 1 builds and tests on Boston with stand-in data only.

---

## RIG-2: Rig's own box (infrastructure only, no feeds)
Clone the AGENT-1 shape that Base proved (`agents/base/`: brain, sandbox, browser, gateway).

**Files you may change:**
- `agents/rig/` (new brain, sandbox, browser and gateway services, compose, Dockerfiles);
- `agents/_brain/` (only if Rig needs a shared hook, with Base's tests still green);
- `ops/seal-check.sh` (add Rig's corridor services, and `agent-rig` to `EXPECTED_SEALED`);
- `tests/`;
- `docs/cursor/ROOMS.md`;
- `.env.example` (names only).

1. **Brain:** Rig's own Hermes Agent (`rig-brain`). Its model calls go through Tank with `TANK_KEY_RIG`, task type `agent.rig.think` (add the policy row: luna, rung 1, `ON CONFLICT DO NOTHING`, above the MODELS-2 marker in `tank/schema.sql`). It uses Skala-approved Rig skills only.
2. **Sandbox and browser:** sealed exactly like Base and Tiger.
   - The sandbox is on an internal network only.
   - The browser sits behind its own gateway and holds no Tank key.
   - The compose file starts with `# coolify: raw compose`, has every variable explicit and no `ports:`, and existing volumes are pinned `external` to their live names (ask Grok for `docker volume ls | grep 59f8cnpelzwsyte1atyjc4fv`).
3. **The public API stays public.** `agent-rig` keeps `rig.tervory.com` through the proxy, and nothing else in the box is reachable from outside. Update `tests/test_room_seal.py` for Rig's public service.
4. **Storage:** the `tervory-rig` bucket with Rig's own `R2_ACCESS_KEY_ID_RIG` pair, for catalogue snapshots, product images and, later, 3D files.
5. **Memory and receipts:** Rig's own memory per tenant. Every step goes on a receipt through Tank, and the paid-work pause applies.

**Done when:**
- CI is green, and `seal-check.sh` shows `agent-rig: sealed`.
- The brain answers one test question about the stand-in catalogue, with a receipt.
- `rig.tervory.com/health` is still 200.
- **Founder step:** tick Raw Compose Deployment on agent-rig before merging.

---

## RIG-3: catalogue, feeds, retailer admin and price rules (on sample feeds)
**Reuse ACCESS-1's feed system in Tank** (`tank/access.py`: feed import, connect and refresh, with receipts). Don't build a second one.

**Files you may change:**
- `agents/rig/`;
- `tank/access.py` (Rig's feed mapping only);
- `tank/schema.sql` (additive);
- new `workspace/app/rig/admin/`;
- `workspace/lib/tank.ts` (Rig admin calls only);
- tests.

1. **Feeds into Rig's tables** (`products`, `fits`, `families`, `setup_templates`):
   - formats (founder, 22 Oct):
     - **the store's own CSV.** The store uploads or connects it itself in the admin and maps its columns. Its prices are used exactly as given; that's the store's choice. A store can optionally turn on the price rule below.
     - **US distributor feeds** that ACCESS-1 already reads (Zanders, Sports South, RSR, Jerry's). These prices are supplier cost, and the landed-cost price rule applies.
     - No Shopify, WooCommerce or Google Merchant importers.
   - pulled nightly, plus a manual **Refresh now**;
   - all-or-nothing per file, with `{added, updated, rejected}` on a receipt.
2. **Price rules** (server-side only): the retailer's landed-cost rule (supplier cost, freight, duty, margin and FX to ZAR at a rate the founder sets) gives **one indicative price**. The rule and its inputs never leave the server, and the API sends the result only.
3. **Fitment:**
   - feed fitment data where it exists;
   - otherwise `rig.fit_suggest` proposes rows (`source='suggested'`);
   - a **Fit approval queue** in the retailer admin: approve or reject, with the evidence shown;
   - nothing reaches a shopper until it is approved.
4. **Retailer admin** at `/rig/admin` (Workspace, the tenant's own data only):
   - connect a feed, set the price rule, choose setup templates per category (pistol: red dot, plate, holster, light; rifle: scope, rings, bipod), and see the fit queue;
   - **what shoppers searched for and didn't find.**
5. **Tiger** updates price and availability for products with no feed (never fitment).
6. **Run on sample feeds now:** a sample store CSV and a sample distributor file, both in `agents/rig/catalogues/samples/`. Real suppliers are connected last, through the admin, with no code change.

**Done when:**
- CI is green.
- A sample store CSV and a sample distributor feed import with receipts.
- A suggested fit is invisible until approved.
- The browser never receives cost, duty or margin (test).
- Screenshots of `/rig/admin` at 375px and 1440px.

---

## RIG-4: the widget live on Custom Nation
**Repo:** `Tervory-AI/tervory-rig`, plus `agents/rig/` for the API side.

1. **Build frames 01–05 exactly as in Figma** (`uRpPy3Hns0WxWZYTPwZ2ni`), including **05 · Explore**, the graph view, and the **Ask** box. Use the `custom-nation` theme. The `SAMPLE DATA` badge shows only when `sample` is true.
2. **Quote handoff:**
   - every quote and "can't find it" link request is stored in Rig and sent to the retailer's flow, configured per tenant;
   - for Custom Nation that flow is its client portal and an **Odoo quotation** (Figma notes);
   - build the Odoo adapter behind the existing sender interface, with a stub in tests.
   - Build the adapter against Odoo's documented API with a stub in tests. `RIG_ODOO_URL` and `RIG_ODOO_USER` stay empty in Coolify until they are plugged in last.
3. **Keys and origins:** a live publishable key for Custom Nation, limited to customnation.co.za and its test page.
4. **Hosting the bundle:** the UMD bundle on a public, cache-busted path (an R2 public bucket or Rig's own domain), under 150 KB gzipped.
5. **Analytics** (no tracking of people): counts of searches, setups opened, swaps, quotes, and searches with no result, per tenant.

**Done when:**
- The widget on a Custom Nation test page searches the real catalogue, builds setups, swaps a part and sends a test quote, which reaches Odoo as a draft quotation (in a test Odoo, or by founder sign-off).
- Screenshots at 390px and 1440px.
- **Custom Nation's live shopper data moves to the new ZA host (Hetzner) with the rest of ZA, last.** Until then the test page runs on Boston with stand-in data.

---

## RIG-5a: the 3D frames (Figma first)
Tisan's rule: design before code. Add these frames to `uRpPy3Hns0WxWZYTPwZ2ni`:
- **06 · 3D view** (desktop 1440 and mobile 390): the chosen product in 3D. Parts from the chosen setup snap on as the shopper picks them. Swap a part to see it change. Rotate, zoom and "exploded view". One indicative total. Request a quote.
- **07 · Dealership terminal** (1920×1080 touch, kiosk): attract loop, big touch targets, the same flow, then "send this build to my phone or email" for the quote.
- **Loading and no-3D states:** a product with no approved 3D model falls back to photos, quietly.

**Done when:** the founder approves the frames. No code before that.

---

## RIG-5F: the 3D forge (bring the software in)
Rig gets one sealed worker service, **`rig-forge`**, holding every 3D tool. It's pinned, checksum-verified, headless, and runs nothing on anyone's laptop. The GPU-heavy steps run as **Hugging Face GPU jobs**, started and tracked by the forge.

**Tools in the `rig-forge` image** (CPU, on Boston). Each is pinned to an exact version and checked against its published SHA256. Licences are recorded in `agents/rig/forge/LICENSES.md`:

| Tool | Job | Licence |
|---|---|---|
| Blender 4.x LTS, headless (`blender -b -P`) | import OBJ/PLY, clean up, decimate, bake normal and AO maps, export GLB | GPL (run as a separate program, never linked) |
| `@gltf-transform/cli` | simplify to a size target, meshopt, dedupe, resize textures, validate | MIT |
| `gltfpack` (meshoptimizer) | final compression for the web | MIT |
| KTX-Software (`toktx`) | KTX2/Basis textures | Apache-2.0 |
| OpenCascade via `cadquery-ocp` (or the FreeCAD CLI) | maker CAD (STEP/IGES) to a mesh, in millimetres | LGPL |
| `trimesh` + `manifold3d` | the automatic model check: outward faces, watertight, real size, budget | MIT / Apache-2.0 |
| Khronos `gltf-validator` | spec check of every GLB | Apache-2.0 |

**GPU jobs** (Hugging Face Jobs, on Tervory's account):
- **Photogrammetry:** Meshroom/AliceVision headless (`meshroom_batch`), a CUDA image pinned by digest. Input: 50–150 photos from the `tervory-rig` bucket. Output: OBJ plus textures back to the bucket.
- **Photos to 3D with AI:** TRELLIS 2 (MIT), from one or a few photos to a GLB with PBR materials, as a draft only.
- **Settings:** the token is `HF_JOBS_TOKEN`, a job-scoped token held by `rig-forge` only. It stays empty until plugged in; tests use a stub. Each job has a cost cap and a timeout, and goes on a receipt through Tank's vendor ledger.

**How a job flows:**
1. Rig's brain (or the retailer admin) creates a 3D job.
2. The forge picks it up: CAD, a scan or AI, then Blender, then gltf-transform and gltfpack, then KTX2, then the model check, then the validator.
3. The result goes to the bucket as a **draft**, with a report (triangles, size, dimensions, pass or fail per check).
4. A person approves it before any shopper sees it (RIG-5).

Every step has a receipt, and a failed step stops the job with its reason.

**Sealed like the browser:**
- `rig-forge` has no public route and no Tank key.
- It is reachable only from `rig-brain` over an internal network.
- Its outbound traffic goes only to the R2 host and the Hugging Face API, through an allow-listed egress proxy (the Radix pattern).
- Add it to `ops/seal-check.sh` and to the seal test.

**Wiring the forge needs (approved 22 Oct):**
- `agents/rig/docker-compose.yml`: the forge's private network to `rig-brain`, plus a forge egress proxy allow-listing only the R2 host and the Hugging Face API.
- In `rig-brain`, only the connection to the forge and a receipt relay. The forge has no Tank key; its receipts go through the brain.
- Tank: new, additive receipt routes for GPU job costs, with the cost cap enforced in Tank. The existing vendor endpoint's behaviour does not change.
- CI image-build wiring for the forge image.
- Seal tests and `ops/seal-check.sh` entries.
- Variable names in `.env.example`, with empty values.

Nothing else in other lanes' files changes behaviour.

**Done when:**
- CI builds the forge image and verifies every tool's checksum.
- `tests/test_rig_forge*.py` takes a neutral sample STEP file and a sample scan (OBJ) end to end into a GLB that passes the model check and the validator.
- An inside-out mesh and a mesh with holes are both rejected, with a reason.
- A GPU job runs against the stub with a receipt.
- The forge image's software list is in the PR.

## RIG-5: the 3D upgrade (a paid tier; Custom Nation first)
**3D is not for everyone:** it is a per-tenant entitlement (`rig_3d`). Tenants without it never download a byte of 3D code.

1. **Getting the 3D models, in order of preference:**
   1. **The maker's CAD files** (STEP/IGES), converted to optimised GLB with the CAD converter (`cadconvert`), with a polygon budget and real dimensions in millimetres.
   2. **Photos to 3D with AI** (one or a few photos), using an open model on our Hugging Face GPUs. TRELLIS 2 is MIT-licensed and gives GLB with PBR materials. Check any other model's licence first.
   3. **Photos to 3D by scanning (photogrammetry):** the retailer uploads 50 to 70 overlapping phone photos of one product. It all runs in the cloud, in the RIG-5F forge, never on anyone's laptop:
      - Meshroom runs headless (`meshroom_batch`) on a Hugging Face GPU job;
      - Blender runs headless (`blender -b -P optimize.py -- in.obj out.glb`, using `bpy.ops.wm.obj_import` because Blender 4.x removed `import_scene.obj`);
      - then `gltf-transform` (simplify to a size target, meshopt and KTX2).
      - Every step goes on a receipt.
   4. **Automatic model check before anyone reviews it:**
      - every face points outward (no inside-out parts; the 22 Oct test mug's handle failed exactly this);
      - no open holes;
      - real size in millimetres;
      - under the size budget.

      A model that fails goes back with the reason and never reaches the approval queue.
   5. Every model is a **draft until a person approves it** (scale, look, attachment points). Unapproved models never reach a shopper.
   6. Files are stored in `tervory-rig` R2, served through a CDN, compressed (meshopt or Draco, KTX2 textures), with a size budget per model.
2. **Attachment points:** fitment rows gain **mount points** (for example a mount plate, a rail, a thread or a case cut-out) as named anchors with position and orientation in the product's GLB. A part snaps only to an anchor that an approved fit allows. The 3D view **never assembles anything the API didn't return** (widget rule 4).
3. **Viewer:**
   - three.js in the widget as a separate, lazy-loaded chunk, fetched only when the tenant has `rig_3d` and the shopper opens 3D;
   - the base bundle stays under 150 KB;
   - it shows rotate, zoom, the exploded view and part swap, with keyboard access and "reduced motion" respected;
   - AR (phone camera) is later, not phase 1.
4. **Kiosk mode** for dealership terminals:
   - full screen, attract loop, touch;
   - catalogue and models cached for poor connections;
   - a remote "reset" from the retailer admin;
   - the quote goes to the shopper's phone or email.
5. **Billing:** `rig_3d` is a plan add-on (price set by the founder), shown in billing. Model conversion and generation costs go on receipts.

**Done when:**
- CI is green.
- On the Custom Nation test page, the neutral stand-in centre product shows in 3D, with an approved part snapping to its mount point and a second part shown in the exploded view.
- A tenant without `rig_3d` loads no 3D code (bundle test).
- Kiosk mode runs at 1920×1080.
- Build and test on stand-in models now: neutral stand-in models (a centre product and two parts that fit it), each with mount points. The makers' CAD files are plugged in last.

## Plugged in last (configuration only, no code)
1. Custom Nation's real suppliers and their keys: RIG-3's feed connections take them.
2. Custom Nation's Odoo URL and user: RIG-4's adapter takes them.
3. The makers' CAD files: RIG-5's pipeline takes them.
4. The 3D add-on price.
5. Going live on the new ZA host (Hetzner) for Custom Nation shopper data.
