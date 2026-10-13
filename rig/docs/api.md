# Rig public API (contract the widget builds against)

Base URL from the embed (`api-base` attribute). Every request carries the retailer's publishable key in `X-Rig-Key`. JSON only. Prices are `{ "amount": 12345.00, "currency": "ZAR", "indicative": true }` — never a breakdown.

| Call | Returns |
| --- | --- |
| `GET /v1/rig/search?q=&limit=` | `{ results: [{ id, name, brand, category, image, price, attributes }] }` |
| `GET /v1/rig/products/{id}` | one product with `attributes` and `categories_that_fit: [{ category, count }]` |
| `POST /v1/rig/setups { product_id }` | `{ setups: [{ tier, label, parts: [{ role, product }], total, why, badge? }] }` — tiers and labels come from the engine. `why` is an array of lines. `badge` is optional display text. |
| `POST /v1/rig/swap { setup, role }` | `{ options: [product], setup }` — alternatives for one part that still fit, plus the setup that was sent with `total` priced by the server |
| `GET /v1/rig/graph/{product_id}` | `{ centre: product, branches: [{ category, count, products: [product] }] }` |
| `POST /v1/rig/ask { product_id, setup?, question }` | `{ answer, cites: [product_id] }` — answers only from catalogue and fitment data |
| `POST /v1/rig/link-quote { url, note }` | "Can't find it": `{ request_id }` |
| `POST /v1/rig/quote { setup or product_id, contact }` | `{ request_id }` — the retailer's handoff happens server-side |

Errors: `{ error: { code, message } }` with HTTP 4xx/5xx. The mock in `widget/src/mock/` must implement every call with the same shapes.

## Fields the widget reads

Product `attributes` may include:

- `sample` (boolean) — when true, the widget labels the item SAMPLE DATA
- `summary` (string) — short line under the name
- `detail` (string) — secondary line on the chosen strip
- `match_note` (string) — sentence on the chosen strip

A setup may include `badge` (string), for example "Most chosen". `why` is an array of lines: the fit checks, a short explanation, then a longer reason.

`POST /v1/rig/swap` returns the re-priced `setup`, including `total`. The widget shows that total. It does not add part prices itself.
