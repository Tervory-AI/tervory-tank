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

## The order (each lane starts only when the one before is live)

| Lane | What | Builder | Starts when |
|---|---|---|---|
| **RIG-2** | Infrastructure: Rig's own box | Cursor or Grok (catalogue is firearms; Codex refuses) | now |
| **RIG-3** | Catalogue and feeds, retailer admin, price rules | Cursor or Grok | RIG-2 live and sealed |
| **RIG-4** | The widget live on Custom Nation | Cursor (UI to Figma) | RIG-3 has a real catalogue |
| **RIG-5a** | 3D frames in Figma, for founder approval | Cursor | can run alongside RIG-3 |
| **RIG-5** | The 3D upgrade (paid tier; Custom Nation first) | Cursor or Grok | RIG-5a approved and RIG-4 live |

**Hard rules for every Rig lane:** `docs/cursor/CONTEXT.md`, `AGENTS.md` and `tervory-rig/AGENTS.md`. In particular:
- One indicative total. Cost, duty and margin never reach the browser.
- Only parts with an approved fit are shown.
- No checkout; every path ends in a quote.
- The widget code is industry-neutral.
- No secrets in the widget.
- **Custom Nation is a ZA client:** its live shopper data (quote contacts) is stored on the ZA box. Until the ZA box is back, build and test on Boston with sample or stand-in data only.

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

## RIG-3: catalogue, feeds, retailer admin and price rules
**Reuse ACCESS-1's feed system in Tank** (`tank/access.py`: feed import, connect and refresh, with receipts). Don't build a second one.

**Files you may change:**
- `agents/rig/`;
- `tank/access.py` (Rig's feed mapping only);
- `tank/schema.sql` (additive);
- new `workspace/app/rig/admin/`;
- `workspace/lib/tank.ts` (Rig admin calls only);
- tests.

1. **Feeds into Rig's tables** (`products`, `fits`, `families`, `setup_templates`):
   - formats: Shopify `products.json`, WooCommerce REST, Google Merchant XML, and the US distributor feeds ACCESS-1 already reads (Zanders, Sports South, RSR, Jerry's);
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
6. Replace the 18-row stand-in only when the founder names the suppliers. **Founder decision:** which US suppliers and accounts Custom Nation uses (the Figma notes' open question).

**Done when:**
- CI is green.
- A sample Shopify feed and a sample distributor feed import with receipts.
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
   - **Founder decision:** Custom Nation's Odoo URL and the user to create quotations, entered by the founder in Coolify; never in chat.
3. **Keys and origins:** a live publishable key for Custom Nation, limited to customnation.co.za and its test page.
4. **Hosting the bundle:** the UMD bundle on a public, cache-busted path (an R2 public bucket or Rig's own domain), under 150 KB gzipped.
5. **Analytics** (no tracking of people): counts of searches, setups opened, swaps, quotes, and searches with no result, per tenant.

**Done when:**
- The widget on a Custom Nation test page searches the real catalogue, builds setups, swaps a part and sends a test quote, which reaches Odoo as a draft quotation (in a test Odoo, or by founder sign-off).
- Screenshots at 390px and 1440px.
- **Live on the ZA box** once it's back (Custom Nation shopper data stays in ZA).

---

## RIG-5a: the 3D frames (Figma first)
Tisan's rule: design before code. Add these frames to `uRpPy3Hns0WxWZYTPwZ2ni`:
- **06 · 3D view** (desktop 1440 and mobile 390): the chosen product in 3D. Parts from the chosen setup snap on as the shopper picks them. Swap a part to see it change. Rotate, zoom and "exploded view". One indicative total. Request a quote.
- **07 · Dealership terminal** (1920×1080 touch, kiosk): attract loop, big touch targets, the same flow, then "send this build to my phone or email" for the quote.
- **Loading and no-3D states:** a product with no approved 3D model falls back to photos, quietly.

**Done when:** the founder approves the frames. No code before that.

---

## RIG-5: the 3D upgrade (a paid tier; Custom Nation first)
**3D is not for everyone:** it is a per-tenant entitlement (`rig_3d`). Tenants without it never download a byte of 3D code.

1. **Getting the 3D models, in order of preference:**
   1. **The maker's CAD files** (STEP/IGES), converted to optimised GLB with the CAD converter (`cadconvert`), with a polygon budget and real dimensions in millimetres.
   2. **Photos to 3D** with an open model on our Hugging Face GPUs. TRELLIS 2 is MIT-licensed and gives GLB with PBR materials. Check any other model's licence first.
   3. Every model is a **draft until a person approves it** (scale, look, attachment points). Unapproved models never reach a shopper.
   4. Files are stored in `tervory-rig` R2, served through a CDN, compressed (meshopt or Draco, KTX2 textures), with a size budget per model.
2. **Attachment points:** fitment rows gain **mount points** (for example the optic cut, rail, muzzle thread and holster envelope) as named anchors with position and orientation in the product's GLB. A part snaps only to an anchor that an approved fit allows. The 3D view **never assembles anything the API didn't return** (widget rule 4).
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
- On the Custom Nation test page, a Staccato P (a stand-in model is fine until the maker's CAD arrives) shows in 3D, with an approved red dot snapping to the optic cut and a holster shown in the exploded view.
- A tenant without `rig_3d` loads no 3D code (bundle test).
- Kiosk mode runs at 1920×1080.
- **Founder decision:** ask Custom Nation's suppliers and makers for CAD or 3D files of the top 20 products; AI-from-photos drafts are only the fallback.

## Founder decisions (collected)
1. The US suppliers and accounts Custom Nation uses (RIG-3).
2. Custom Nation's Odoo, for quotes (RIG-4).
3. CAD or 3D files from the makers for the top 20 products (RIG-5).
4. The price of the 3D add-on (RIG-5).
5. Going live on the ZA box when it's back (RIG-4).
