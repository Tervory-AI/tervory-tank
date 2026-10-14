# Feeding Rig a brand's catalogue

Two sheets per brand. CSV or Excel, one row per item, the first row exactly as the templates in `templates/`.

## 1. `products`: what the brand sells
| Column | Required | Meaning |
| --- | --- | --- |
| `sku` | yes | The brand's own product code. Unique per brand. Re-importing the same sku updates it. |
| `gtin` | no | Barcode (EAN/UPC) if known. |
| `name`, `brand`, `category` | yes | Category is free text but keep it consistent (e.g. `rifle`, `optic`, `mount`). |
| `price`, `currency` | yes | The shopper-facing indicative price. Never cost or margin. |
| `image_url`, `product_url` | image yes | Public links. |
| `family` | no | Groups models that take the same parts (e.g. a platform). Parts can then fit the whole family at once. |
| `active` | yes | `yes`/`no`. `no` hides it without deleting. |
| `attributes` | no | Measurable facts that decide fit, as JSON: thread, rail, tube size, length, calibre, bolt pattern… |

## 2. `fits`: what goes with what (the valuable part)
One row per "this part fits that". Fill **either** `fits_sku` (one product) **or** `fits_family` (a whole family), and optionally a `rule` the two must share (e.g. `{"rail": "picatinny"}`).
- Rows we import from the brand are trusted.
- Rows Rig suggests itself are held back until a person approves them. A shopper only ever sees approved fits.

## How it gets in
- **Now:** send Claude the two sheets (or drop them in the shared Drive folder). Claude imports them through `POST /v1/rig/admin/import`. Rejected rows come back with the row number and the reason.
- **Later, per brand:** a feed URL (Shopify, WooCommerce or a Google Merchant feed) pulled every night, so prices and stock stay current without anyone re-sending sheets.
- **From R5 (3D):** one `.glb` (or the CAD/STEP file) per part, named by `sku`, plus permission to render it.
