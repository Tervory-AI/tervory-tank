# Rig × Custom Nation × Archon — wiring plan

Written 18 Oct 2026 (PT). Research and planning only. No code was changed, no pull request was opened, nothing was merged or deployed, and nothing was signed up for.

Diagrams (dark theme, in this folder):
- `1-system.png`: the whole system, box by box
- `2-media-pipeline.png`: how Zenas's photos and video become 3D, step by step
- `3-search-flow.png`: one shopper's journey, from typing a search through to "Reserve at Custom Nation"

The editable sources are the `.mmd` files next to them.

Colour key on the diagrams: **blue = already live**, **pink = new to build**, **orange = needs a graphics card**, **green = quick win**, **grey dashed = switched off**.

---

## 1. The short version

1. **Most of the plumbing already exists.** Rig's live server already does search, "what fits this pistol", suggested builds, swapping parts, Ask Rig, and sending a reservation to the dealer by email or webhook. The new work is mostly the **look**: the glowing search screen, the hero view and the build view. On top of that come the **3D files** and one small new "asset list" that tells the screen which 3D files belong to which product.
2. **Quick win first:** a glowing search screen plus a **360° spin** of each pistol, made from Zenas's own video. This needs no special hardware.
3. **Then real 3D:** "splats" (photo-real 3D clouds made from video) of each pistol, shown with a free viewer called Spark.
4. **Then the exploded builder:** each part filmed on its own, so parts can fly apart and upgrades can snap onto their fit points. The running total comes from Rig's existing pricing.
5. **Everything recommended is free and open-source.** The only possible costs are a graphics card (if Zenas's computer has no suitable one), a can of scanning spray for shiny parts, and CDN storage once the files get big. These are all flagged below. Nothing has been bought.

---

## 2. What each box in the diagram does

| Box | What it does in plain words | Status |
|---|---|---|
| **Shopper's browser** | The phone or computer the shopper uses. | n/a |
| **Custom Nation skin** | The paint job. CN logo and a dark, glowing style, with no Tervory branding. It's the same Rig underneath, just dressed as Custom Nation. | New (look only) |
| **Glowing search view** | The screen in Zenas's reference picture: a glowing centre node for the search, curved lines out to category nodes (Pistols, Magazines, Triggers, Optics…) and item cards at the ends. | New |
| **Pistol hero view** | One pistol, big. A 360° spin first, then full 3D once it's ready. Price, short facts and an Ask box. | New |
| **Build view** | Exploded view of the pistol. Upgrades that fit glow at their spot. Pick one and it moves into place, and the total updates. | New |
| **3D viewer** | The engine that draws the 3D in the browser. | New (free tools) |
| **Rig search API** | Rig's live server at rig.tervory.com. It already answers search, product detail, "what fits" (`/graph`), suggested builds (`/setups`), swapping a part (`/swap`), Ask Rig (`/ask`) and reservations (`/quote`). Each shop key works only from that shop's own website. | **Live today** |
| **Asset list per product** | A new, small addition. You give it a product code and it gives back that product's 360 frames, 3D file and fit points. | New |
| **Catalogue** | The products, prices and families, stored in Postgres (the database). | Live. Archon items still need adding. |
| **Approved fits** | The list of "this part fits that pistol". Shoppers only ever see approved fits. | Live. Archon fits need adding. |
| **Saved answers** | Rig remembers answers it has already worked out, so the next shopper gets them instantly and for free. | Live |
| **Reservations / quotes** | Saves the shopper's exact build and contact details, then tells Custom Nation by email or webhook. | Live |
| **3D asset records + fit points** | New table. It records which 3D file belongs to which product and where each upgrade attaches. | New |
| **Media pipeline** | Off-line work that turns Zenas's photos and video into web-ready 3D. It runs on a computer with a graphics card, not on the shop website. | New |
| **Asset checks** | Before anything goes live, an automatic check: is it the right size (within 2 mm, the bar already in the Rig spec)? Is the file small enough? Are the fit points there? | New |
| **File storage / CDN** | Where the 3D files live. Start on Rig's own server, which is free. Move to a CDN (a fast worldwide file host) later if needed. | New |
| **CN quote inbox** | Where "Reserve at Custom Nation" lands: an email, or a webhook into CN's own system. | Live (needs CN's address) |
| **Tank + rig.vault** | Only used if a plugin is ever needed, for example a key for an outside service. All such calls go through Tank, on the server. **The vault stays OFF.** While it's off, the tab says "This vault is off. Turn it on in Tank." The demo needs no plugins. | Exists. Stays off. |

---

## 3. What we already have vs what must be built

**Already have (live on main, commit 81bda21):**
- Search with honest states. When there's no exact match, Rig says "No exact match for that model" and shows the closest match. Rig never makes things up.
- `/graph/{product}`. It already returns exactly the shape the glowing view needs: one centre product, plus branches by category with the parts that fit. **This is a big head start**, because the glowing screen is mostly a new way of drawing data Rig already sends.
- Suggested builds, part swaps and plain-sum totals (no bundle discount, as decided).
- Ask Rig, which answers only from the catalogue and refuses with "I don't know" otherwise, with Sources attached.
- Reservation hand-off by email or webhook.
- Shop keys locked to each shop's own website, and full separation between shops.
- Postgres with fast text search and typo-tolerant search already switched on (`pg_trgm` and full-text indexes).

**Must be built:**
1. **Archon catalogue sheet** for Custom Nation: products, prices and fits, in the existing templates (`docs/rig/templates/`). Today the CN demo catalogue is Staccato. The Archon items seen so far are Type A, Type B, Type B Ported, 12- and 15-round magazines, Performance Trigger and the RMSc mounting screw pack, plus any optics and holsters CN stocks.
2. **CN skin** (colours, logo, fonts) for the shopper screens.
3. **Glowing search view, hero view and build view.** Draw them in Figma first (already under way), then build them.
4. **Asset list** (one small read-only address on the Rig server) and the **asset table** in the database.
5. **Media pipeline scripts.** These are a short chain of free tools, listed below.
6. **Asset checks** wired into Rig's tests.

---

## 4. Recommended open-source pick per layer

All of these were checked as current in Oct 2026. "Licence" says whether we can use it commercially for free.

### a) The glowing search screen
- **Pick: React Flow** (`@xyflow/react` 12, MIT). It's a ready-made "boxes joined by lines" toolkit. It gives us the tidy left-to-right layout from the reference, with curved lines we can make glow and zoom/pan for free. We add a small 3D glowing orb at the centre with **react-three-fiber + postprocessing "Bloom"** (MIT / zlib), which is the glow effect.
- **Runner-up: d3** (`d3-hierarchy` + `d3-shape`, ISC). It's lighter and draws the same curves, but needs more hand-building.
- **Not chosen:** react-force-graph (MIT). It's good, but nodes float and wobble like a physics toy, which doesn't match the calm reference. sigma.js and cytoscape.js (MIT) are made for thousands of nodes, which is overkill here.

### b) Turning Zenas's photos and video into 3D
| Job | Pick (licence) | Why | Runner-up |
|---|---|---|---|
| Pull frames out of video | **ffmpeg** (LGPL/GPL tool, free) | The standard video tool. It's already on the box. | — |
| Throw away blurry frames | **OpenCV** sharpness check (Apache 2.0) | A few lines of code. | Manual pick |
| Cut out the background (photos) | **BiRefNet via rembg** (both MIT) | The best free cut-out quality, and it runs offline. | — |
| Cut out the background (video) | **SAM 2** (Apache 2.0) | Click the pistol once and it follows it through every frame. | BiRefNet frame by frame |
| Work out where the camera was | **COLMAP 4.0** (BSD) | The industry standard. Since March 2026 it includes the fast "global mapper" (formerly GLOMAP). | GLOMAP is now part of COLMAP |
| Build the photo-real 3D ("splat") | **Brush** (Apache 2.0) | Runs on Windows, Mac and Linux, and works with almost any modern graphics card, including Apple Silicon. Simple app. | **gsplat / nerfstudio** (Apache 2.0). Top quality, but needs an NVIDIA card. |
| Tidy and split the splat | **SuperSplat** (MIT, in the browser) | Delete stray bits and cut a splat into parts (slide, frame…) by hand. | — |
| Shrink the splat for the web | **splat-transform → .sog** (MIT) | Makes splat files many times smaller. | `.spz` format (MIT) |
| Solid model (mesh), for fit | **COLMAP 4.0** dense + mesh + texture (BSD) | It now does the whole job in one tool. | **Meshroom / AliceVision** (MPL-2.0), which is easier to click through |

### c) Showing 3D on the web
- **Pick: three.js + react-three-fiber + drei** (all MIT). The standard 3D engine for the web. It gives us studio lighting, soft shadows, orbit-by-drag and labels.
- **Splats: Spark** (`@sparkjsdev/spark` 2.3.1, MIT, released 1 Oct 2026, built by World Labs). It's actively maintained, fast even on phones, and reads `.sog/.spz/.ply`. It can also move each splat part separately, which is what makes an exploded view from splats possible.
  - **Runner-up:** PlayCanvas engine (MIT).
  - **Avoid:** mkkellogg GaussianSplats3D. Its author says it's no longer maintained and points to Spark.
- **Simple one-tag fallback: Google model-viewer** (Apache 2.0). It's good for plain models and can show "view in your room" on phones.
- **Solid model files:** **glTF/.glb** (the "JPEG of 3D") shrunk with **gltf-transform + meshopt** (both MIT). Meshopt opens faster than the runner-up, **Draco** (Apache 2.0).

### d) Exploded view and fit points
- **Fit points:** inside each solid model, we add invisible named markers such as `mount_optic`, `mount_trigger`, `mount_magwell` and `mount_rail`. Each marker carries a direction and a small "clearance box" (the roadmap already asks for this). For splats, the same markers are kept in a small side file in the asset list.
- **Blender** (free, GPL; the files we make are ours) with a **Python script**. The script checks each model for scale and size and adds or validates the named markers. It runs in batch, with no clicking.
- **Exploded view:** each part is its own file (or its own splat piece cut out in SuperSplat). The viewer slides them apart along set paths. An upgrade is offered only if Rig's **approved fits** say it fits. The 3D just shows it moving into place.
- **Later (R6):** collision checks, so a part that physically clashes is refused. three.js plus simple box checks to start.

### e) Quick win: 360° spin from video
- **Pick: our own small spin viewer** (about 100 lines, no licence issue). It works like this:
  - Pull 72 evenly spaced frames from a slow spin with ffmpeg.
  - Cut out the background with BiRefNet.
  - Save as small WebP images.
  - Drag to turn. It loads in about a second.
- **Runner-up: js-cloudimage-360-view** (MIT). Catch: its licence lets the vendor use our name and logo in their marketing, so we'd only use it with Zenas's OK.

### f) Search side
- **No change needed now.** Rig already uses Postgres full-text search and typo-tolerant search (`pg_trgm`). Its search rule already passes the honest-state tests.
- **pgvector** ("search by meaning") could help Ask Rig with fuzzy questions later. It's **not a clear win** for a catalogue this size, so it's left out.
- The one real improvement for the demo is on the **screen**: group search results by category so the glowing nodes have something to show. That can be done in the browser with data Rig already returns.

### Optional, previews only
- **AI photo-to-3D** (for example Microsoft **TRELLIS.2**, MIT). The roadmap already says this is "for previews, never for fit". Catches: it needs a 24 GB NVIDIA card, and its default add-ons (nvdiffrast/nvdiffrec) are **non-commercial** licences. Not recommended for the demo.

---

## 5. Hardware and costs

| Item | Free? | Notes |
|---|---|---|
| All software above | **Free** | All open-source. No sign-ups. |
| The box (our shared Linux machine) | Free | 8 cores, 15 GB memory, **no graphics card**. Good for frames, cut-outs, 360 spins, file shrinking and checks. **Not** good for building splats or meshes. |
| Graphics card for splats and meshes | **Maybe paid** | It runs on **Zenas's own computer** if it has an NVIDIA RTX card (8 GB+ memory is fine, 12 GB+ is better) or an Apple Silicon Mac, using Brush. Expect roughly 10–40 minutes per pistol. If not, a rented cloud GPU (paid by the hour). **Flagged. Not signed up.** |
| Scanning spray for shiny parts | **Paid (small)** | A temporary matte spray that makes shiny metal easier to capture, and later wipes or evaporates off. Only needed if the shiny parts come out badly. **Flagged. Ask before buying, and check it's safe on the finish.** |
| File storage / CDN | Free to start | Serve from Rig's own server first. A CDN such as Cloudflare R2 has a free tier and is paid above it. **Flagged** for later. |
| Rough file sizes | — | 360 spin: 3–6 MB. Splat (.sog): 5–15 MB per pistol. Solid model (.glb): 2–8 MB. |

---

## 6. What Zenas needs to supply

1. **The files you mentioned:** your photos and the firearms walkthrough video. Put them in one Google Drive folder, or wherever suits you. We'll check whether the walkthrough already orbits the guns well enough for 3D. A talking walkthrough usually gives great hero clips and maybe a 360 spin, but full 3D normally needs the dedicated filming below.
2. **Permission:** a yes from Archon (and Custom Nation) to use their names, products and 3D renders. If Archon will share **CAD files** (their engineering drawings), we should use them. The roadmap already says CAD comes first for exact fit.
3. **Real CN prices and stock** for the Archon items. Otherwise they stay labelled "demo price".
4. **The CN reservation address:** which email or webhook "Reserve at Custom Nation" should go to.

### How to film for the best 3D (per pistol, and per loose part)
- **Safety first:** unloaded, magazine out, and checked by a qualified person. If we want the exploded view, have the pistol **field-stripped** (slide, frame, barrel, spring, magazine, trigger, optic plate) by someone qualified. Film each part on its own the same way, plus each upgrade part (trigger, magazines, optic).
- **Keep the gun still, move the camera.** Set it on a small stand on a **patterned mat**; a newspaper works. The pattern helps the software track the camera. Turntables with a plain backdrop confuse it.
- **Light:** soft and even, like an overcast day or two big soft lights. No direct sun, no flash and no hard reflections.
- **Shiny black finishes are the hardest case.** If they come out patchy, the fixes are a polarising filter or a light dusting of scanning spray. Splats cope with shine better than solid models, which is one reason splats are the main showcase.
- **Camera settings:** lock focus, exposure and white balance. Shoot 4K video at 30 or 60 frames a second, with a fast shutter (1/250 or faster) to avoid blur.
- **Path:** three slow full circles at low, middle and high height, about 40 seconds per circle, then a pass over the top. Keep the gun filling most of the frame, and keep 70%+ overlap between views.
- **Photos instead of video:** 100–150 sharp photos per pistol (about 40 per circle × 3 circles, plus top and close-ups), and 40–80 per small part.
- **Scale:** put a ruler in a few shots, or write down the overall length. That's how we pass the "within 2 mm" check in the Rig spec.
- **For the quick 360 spin:** one extra clip with the camera locked on a tripod while the gun turns slowly on a turntable (one full turn in about 20–30 seconds), against a plain backdrop.

---

## 7. Build order (each stage: drawn in Figma first, draft PR only, nothing merged or deployed without Zenas's OK)

**Stage 0: no media needed (can start now)**
- Archon catalogue and fits sheets for the CN shop, using the existing templates.
- CN skin, and the glowing search view drawn from Rig's existing `/search` and `/graph`.
- Hero and build views with the current line drawings as stand-ins.
- Honest states: no exact match, nothing fits, "I don't know", and the vault off.

**Stage 1: quick win (needs Zenas's files, no graphics card)**
- A 360° spin for each pistol, made from his video.
- Hero video loops cut from his walkthrough.
- The new asset list and asset table.

**Stage 2: real 3D look (needs a graphics card)**
- One splat per pistol: Brush, tidied in SuperSplat, shrunk to .sog, and shown in the hero view with Spark.
- The 360 spin stays as the instant first view while the 3D loads, and as the fallback for old phones.

**Stage 3: exploded builder**
- Parts filmed separately and cut or split into pieces.
- Fit points marked.
- Approved upgrades glow and move into place, with the running total from `/swap`.
- "Reserve at Custom Nation" sends the exact build through `/quote`.

**Stage 4: R5 / R6 proper**
- Solid .glb models with named fit points, from Archon CAD if possible, otherwise from photogrammetry (3D from many photos).
- The 2 mm size check, collision checks, and screenshot/share.

---

## 8. Risks

| Risk | Plain-English meaning | What we do |
|---|---|---|
| **SAM 3 licence bans gun use** | Meta's newest cut-out tool (SAM 3) forbids use "related to… the development or use of guns". | **Don't use SAM 3.** Use SAM 2 (Apache 2.0) and BiRefNet (MIT) instead. |
| **Original splatting code is non-commercial** | The original INRIA research code (and its spin-offs such as SuGaR) can't be used for business. | Use Brush or gsplat (Apache 2.0) only. |
| **"Share your code" licences** | OpenSplat and OpenMVS are AGPL: if we build them into our service, we must publish our changes. | Don't build them into Rig. Our picks avoid them. |
| **Paid tools that look free** | Postshot (Jawset) is paid and closed. | Not used. |
| **Shiny black metal** | It can come out patchy or with holes. | Better light, a polarising filter, or (with OK) scanning spray. Splats first. |
| **No graphics card on the box** | We can't build splats on our server. | Zenas's computer, or a rented GPU only with a yes. |
| **The walkthrough may not be 3D-ready** | A talking walkthrough rarely circles the gun evenly. | Use it for hero clips and maybe a 360. Ask for the short dedicated filming above. |
| **Firearm 3D files** | Exact, downloadable 3D files of gun parts could be misused or break laws. | Only show compressed, view-only versions. No downloads. CAD stays private. |
| **Brand permission** | Archon's name, logo and products are their trademarks. | Get Archon's and CN's written OK before anything public. |
| **SA firearm sale rules** | Guns can't simply be "bought" online. | Keep it as **"Reserve at Custom Nation"**, with collection only after the licence check in store. Wording to be confirmed by CN. |
| **Slow phones** | 3D can be heavy. | Load the 360 spin first, then the 3D. Keep files small, with a fallback to the spin. |
| **Accuracy for fit** | Pretty 3D isn't proof that a part fits. | **Fit always comes from Rig's approved fits list, never from the 3D.** The 3D only shows it. |

---

## 9. Open questions only Zenas can answer
1. Which computer will build the 3D? Does your computer have an NVIDIA graphics card, or is it a Mac? If neither, are you OK with renting one by the hour later?
2. Do we have Archon's OK to use their products in a public demo? Will they share CAD files?
3. May the pistols be field-stripped and filmed part by part, and is scanning spray OK on the finish if needed?
4. Real CN prices and stock for the Archon range, or keep "demo price" for now?
5. Where should the demo live: on rig.tervory.com, or embedded inside customnation.co.za?
6. Where should "Reserve at Custom Nation" go: an email address, or straight into CN's own system?
