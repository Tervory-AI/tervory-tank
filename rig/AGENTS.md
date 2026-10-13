# Working on Tervory Rig (read this first)

Rig helps a shopper find a product and **complete the setup with parts that actually fit**, then request a quote. No cart, no checkout.

## Two halves, two repos
| Half | Where | What |
| --- | --- | --- |
| **The widget** | this repo, `tervory-rig` | The embeddable shopper UI (web component), retailer themes, the API client. Ships to other people's websites. Holds no secrets. |
| **Rig's brain** | `Tervory-AI/tervory-tank`, `agents/rig/` | Catalogue + search index (Meilisearch), fitment rules, setup builder, price rules, AI ranking/answers via Tank, supplier feeds via Tiger. |

The widget only ever talks to Rig's public API (`docs/api.md`). Until that API is live, the widget runs on a mock that implements the same contract on sample data.

## Rules that are not negotiable
1. **Never push to `main`.** Branch `cursor/<task-id>-<slug>`, open a pull request, stop. Claude reviews before anything merges or ships.
2. **No secrets, ever.** The widget is public JavaScript. It receives a retailer's publishable embed key only. No API keys, no rates, no supplier data.
3. **One indicative total.** The UI shows one indicative price per item or setup. Never cost, duty, VAT, margin or a breakdown — and the API never sends them.
4. **Only parts that fit.** The widget shows what the API returns; it never assembles a setup itself or claims compatibility on its own.
5. **No checkout.** Every path ends in a quote request.
6. **Figma first.** Build what the frames show (Figma file `uRpPy3Hns0WxWZYTPwZ2ni`). If something must change, say so in the PR so the frame is updated too.
7. **Industry-neutral code.** Nothing in the component is specific to firearms; product types, categories, labels and copy come from the API and the retailer theme. A camera shop must be able to embed the same build.
8. **Nothing installed on the founder's laptop.** Cloud agents only.

## Conventions
- TypeScript strict. A framework-free web component (`<tervory-rig>`) built with Vite as one ES module + one UMD bundle; Shadow DOM so retailer CSS cannot break it and it cannot break theirs.
- Theming by tokens only (colour, font, radius, spacing) passed as attributes or a theme object. First theme: Custom Nation.
- Accessible: keyboard throughout, visible focus, labelled controls, works at 390 px and 1440 px with no horizontal scroll.
- Every PR: what changed, screenshots at 390 and 1440 px, how it was tested, anything the founder must decide.
