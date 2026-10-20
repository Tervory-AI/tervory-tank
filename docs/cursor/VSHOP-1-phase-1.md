# VSHOP-1: in-video shopping, phase 1 (working name "vshop" until the founder names the agent)

> Written 19 Oct 2026, 05:50 PT. Read `docs/cursor/AGENT-in-video-shopping.md` first. This phase proves the core loop on one short clip and one test catalogue.

**Files you may change:** new room `agents/vshop/` (start from `agents/_template/`, same chassis, own Dockerfile, compose and tests), new candidate skills `tank/skills/vshop.*` at 1.0.0 with evals and CHANGELOG, new page `workspace/app/vshop/` and routes `workspace/app/api/vshop/`, `workspace/app/squad-links.tsx` (add the link, founders only for now), `.env.example` (names only), new tests. Do not edit other rooms, Tank's router or ledger. The room calls Tank and Rig through Tank's existing API only.

## Build
1. **Upload.** A founder uploads a short video (up to 10 minutes, MP4/WebM) with a tick-box confirming the business owns or has the rights to it. Stored in the room's own storage, scoped by tenant.
2. **Scenes.** Split into scenes with ffmpeg (scene-change detection), one or two key frames per scene.
3. **Detect.** On each key frame, find products with open models that run on CPU inside the room: an open-vocabulary detector (YOLO-World or Grounding DINO, small size), SAM 2 (small) for the outline, SigLIP or CLIP (base) for an embedding and a short label. Models are downloaded at build time, pinned by version and checksum. No paid vision API.
4. **Match.** For each detected item, search the tenant's catalogue through Rig's search via Tank (`rig.search`), using the label plus the embedding when Rig supports it. Keep matches above a confidence threshold (`VSHOP_MATCH_MIN`, default 0.6) with: start and end time, product id, title, price, image, confidence, source frame.
5. **Player page** (`/vshop`): plays the video; small tags appear while a matched product is on screen; tapping a tag or pausing opens a side panel with the product and a **Buy** button.
6. **Buy goes to AmmoSync.** The button opens the product on the AmmoSync platform: `AMMOSYNC_PRODUCT_URL` with the product id. Never an outside checkout. Firearms are marked "Ships to your nearest FFL" (routing itself is an AmmoSync phase).
7. **Costs and receipts.** Every model call (if any goes through Tank) is on the ledger; the page shows processing time and cost per video.

## Rules
- Tenant-scoped everywhere; one tenant never sees another's videos or matches.
- No viewer tracking beyond tag taps and Buy clicks counted per video and scene.
- Schema changes additive, tested on an empty database, re-applied, and on the current main schema with agent roles.

## Done when
CI green; a fixture clip with a known product in two scenes produces matches at the right times against a fixture catalogue (tested); tags show at those times on the page (Playwright test, 375px and 1440px screenshots committed to `docs/screenshots/vshop/`); Buy links to `AMMOSYNC_PRODUCT_URL` with the right id (tested); another tenant cannot read the video or matches (tested).

## After merge (Claude)
Create the room in Coolify with room-setup, deploy it, and run a real test clip.
