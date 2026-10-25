# Rig v5 shopper page

Built from the approved Figma file "Rig" (pages "Rig — Search v5" and "Custom Nation skin v5").

- `/v5` is the Tervory skin. `/v5/cn` or `/v5?skin=cn` is the Custom Nation skin. Both use the tokens of the Figma collection "Rig Skin v5", switched by `data-skin` on `<html>`.
- Both skins search the Archon demo catalogue (`catalogues/archon`) through this host's `/v1/rig`.

## Real engine

| Step | Call |
| --- | --- |
| Prompt, matched base product, approved fits | `GET /v1/rig/search` (a second search with the base product name lists all its approved fits) |
| Base product when the prompt names only a part | `GET /v1/rig/products/{id}` |
| Market average, low, high | `POST /v1/rig/compare`, only for items the shopper has picked or opened |
| Get A Quote | `POST /v1/rig/quote`, the shop's existing quote request (Custom Nation letter to the shop email in `publish.json`) |
| I don't know | the search's `honest` state (`nothing`, `not_stocked`) |

## Sample, labelled on the page

- `sample-suppliers.json`: Supplier A, B and C stock, lead time and price. Not from distributor feeds. The best in-stock offer always equals the catalogue price, so the build total equals the quote total.
- `catalogues/archon/market.csv`: market rows from "Sample retailer 1–4".
- Catalogue prices are the demo prices already in `catalogues/archon/products.csv`.

## Media

Only Zenas's Archon media, as used in the Figma file: the Type B cut-out render (`TypeB_OR_RMRcut_MG_FLR_PNG.png`), line art cropped from the Type B blueprints, the ACRO crop, and the two logos. Each raster is WebP wrapped in an SVG file so it can be committed as text. Swap them for plain image files when a binary push is available.
