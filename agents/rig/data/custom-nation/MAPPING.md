# How this knowledge would load into Rig

Box only. Nothing here is in the repo, and no PR was opened.

## What Rig reads today (read from Tervory-AI/tervory-tank, main, agents/rig)
- `catalogues/<slug>/products.csv`. Columns: sku, gtin, name, brand, category, price, currency, image_url, product_url, family, active, attributes (JSON). `rigbox/catalogue.py` rejects any row missing sku, name, brand, category, price, currency, image_url or active.
- `catalogues/<slug>/fits.csv`. Columns: part_sku, fits_sku **or** fits_family (one only), rule (JSON), note. Imported fits are saved as approved, and shoppers see them.
- Families are not a separate file. They are built from the `family` column (`families_from`).
- Search indexes name, brand, sku and the `attributes` JSON text. Facts in `attributes` therefore become searchable, for example "suppressor ready".

## The seed files here (`seed/`)
- `products.csv`: one Archon Type B pistol (family `ARCHON-TYPE-B`) and three parts seen fitted in the Versatility video: a threaded barrel, a grip module and a large-capacity magazine. Each `attributes` value holds the features seen and the media file plus timestamp. Anything inferred sits under `"inferred"`.
- `fits.csv`: those three parts fit family `ARCHON-TYPE-B`. The note says where in the video each one is shown fitted.

## Why it will not load yet (on purpose)
- **SKU, price and image_url are blank or `TBD-`.** None of them appear in the media, so the loader rejects the sheet as it stands. That is the safe default. Custom Nation's real SKUs and prices go in first.
- `active` is `no` until those are filled in.
- **Fits are auto-approved on import.** Seeing a part fitted in a marketing video is good evidence, but Custom Nation should confirm each fit before importing. The other route is to load them as suggested (unapproved) fits through the review queue.
- **No part numbers.** The folder had no exploded-view PDF. When it arrives, its part numbers can go into each product's `attributes.part_number`, with one product row per sellable part.

## How the other two files would be used
- `archon_parts.json` is the source list of features and parts seen, with media timestamps. It is the input for writing more product rows, and for Ask Rig grounding text such as "the Type B has a flared magazine well (shown in the Control video, 0:30)".
- `archon_media_index.json` maps product and view to a file, timestamp and frame path. A later "media" step (not in today's schema) could pick the right frame for each view, and the spin viewer could pick its source clip.
