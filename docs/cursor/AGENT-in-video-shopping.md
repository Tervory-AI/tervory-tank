# New agent: in-video shopping (name to come from the founder)

> Added 19 Oct 2026, 05:45 PT. Founder decision: a new squad agent for in-video shopping. Viewers watching a show or clip can see and buy the products on screen. Design reference for the viewer home page: https://dribbble.com/shots/26481725-Interactive-Home-Page-Design-For-Streaming-Website (uiux_sumeet): "Discover Unlimited Content" headline, category pills (Popular, Latest, Top Rated, Recommended), and a fanned carousel of posters with the selected title raised in front. Reference only: we build our own design in the Tervory style, never a copy.

## What it does
1. **Find products in a video.** For each scene, detect the products on screen (clothing, gear, devices, furniture) with open models that run on our own servers: an object finder (for example Grounding DINO or YOLO-World), SAM 2 for clean outlines, and an image embedder (SigLIP or CLIP) to describe each item.
2. **Match them to a real catalogue.** Each detected item is matched against a retailer's own catalogue through Rig's search (the same engine that finds parts that fit). Matches above a confidence threshold are kept, with the frame time, the product, the price and the shop link.
3. **Shoppable player.** A web player shows small product tags at the right moments. Tapping one opens a side panel with the product, the price and "Buy" (the retailer's own checkout or an affiliate link). Pausing shows everything in the current scene.
4. **Viewer home page,** in the spirit of the reference: a headline, category pills, a fanned carousel of titles, and a "Shop this show" strip under each title.
5. **Owner dashboard:** which products were shown, tapped and bought, per video and per scene, with every figure from real data.

## Rules
- Only videos the client owns or has the rights to; the upload asks for that confirmation.
- No tracking of individual viewers beyond what a sale needs. Counts are per video and scene, not per person.
- Vision models run on our servers or through Tank, with costs on the ledger like every other agent.
- First test content: TNGO.tv (when it is ready) and the group's own product videos.

## Phase 1 (first brief)
Upload a short video, detect and match products against one test catalogue, and play it back with product tags and a product panel. The dashboard and the home page come in phase 2.

## Founder
Name the agent and give it a logo, like the rest of the squad.
