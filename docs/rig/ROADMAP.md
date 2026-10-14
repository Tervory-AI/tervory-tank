# Rig roadmap: from "find it" to a 3D build in the dealership

Founder direction (14 Oct 2026): Rig grows from product search into **add-ons that fit**, then the **whole build assembled in realistic 3D**, shown on a **terminal inside dealerships**, as a product Tervory sells to retailers. Benchmark: Optivus (3D configurators for firearms with collision checks and compatibility rules). Our edge: photo-real rendering instead of CAD-looking models, fitment that learns from catalogue data, any industry, and every build ending in a quote for the dealer.

| Phase | What ships | Depends on |
| --- | --- | --- |
| **R3 Brain + data** | Live API, spreadsheet/feed import, approved fitment, setups, quote handoff. Test brands loaded. | Now (brief `docs/cursor/R3-rig-brain.md`) |
| **R4 Add-ons graph** | Every product shows what fits it, by role, with "why it fits"; dealer admin page to approve suggested fits; bundles priced as one total. | R3 |
| **R5 3D assets** | Per part: a `.glb` model with named **mount points** (where it attaches, orientation, clearance box). Sources in order: the brand's CAD (STEP) converted to glTF with real materials; then scans/photogrammetry; AI image-to-3D only for previews, never for fit. Asset checks: scale, polycount, materials, mount points present. | Brands supply CAD/3D files |
| **R6 3D configurator** | Assemble the build in the browser and the widget: parts snap to mount points, collision check before a part is allowed, photo-real rendering (PBR materials, studio lighting, shadows), turntable and close-up views, screenshot/share, the quote carries the exact build. | R4, R5 |
| **R7 Dealership terminal** | Kiosk mode on a large touchscreen (and optional holographic/3D display): locked-down full-screen app, works through dealer Wi-Fi drops (cached catalogue and models), staff login for quotes, analytics on what customers build. | R6 |

**What the founder supplies, per brand:** product sheet + fitment sheet (templates in `docs/rig/templates/`), product images, and from R5 the CAD/3D files with permission to use them for rendering.
