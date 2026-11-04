# Tisan sections contract (tisan.sections/1)

Written by Claude on 1 Nov 2026 so that the three Tisan threads (sections, builder and publish) build to one file. `manifest.json` is the contract. Change it only through a PR that names all three threads.

- **Header and footer are site-level.** They are described under `site` (logo, nav, footer, ui), not as page sections. Page sections are the keys of `sections`.
- **`content/site.json`:** `{"schema":"tisan.content/1","logo","nav","footer","ui","pages":[{"name","path","title","sections":[{"type","id","props"}]}]}`. Site-level fields validate against `site.props`; each section's `props` validates against `sections.<type>.props`. A section `id` matches `^[a-z0-9-]{1,40}$` and is unique within its page.
- **Text slots** are prop paths, where `[]` means every array item. Every text slot that is present is filled only from an accepted Trigger write (`GET /v1/trigger/copy/{write_id}`). The copy key is `site/<path>` for site-level slots and `<page name>/<section id>/<path>` for sections, with array indexes as path parts. For example: `site/nav/0/label` and `home/hero-1/items/2/title`.
- **Page titles** are text slots too, keyed `<page name>/title`.
- **Image slots** are filled only from the builder input `media` (the same keys), with URLs the founder supplies: `https://...` or `/media/<file>`. Nothing is invented.
- **`purpose`** says, for each slot, what the copy is for. The builder uses it to tell the founder what to ask Trigger for.
- **Contact** reuses the template's existing contact form unchanged, with its existing labels.
- **Visual design** of each section waits for approved Figma frames (rule 2). Until then the template only renders the existing contact and privacy pages.

## Founder design check — 3 November 2026

The founder approved the short section designs on 3 November. The following limit revisions and redrawn max/optional states are **Changed after approval, awaiting founder** in Figma page `197:9`; unchanged specimens remain **Approved 3 Nov**. Sections, builder and publish consume this same manifest; no schema version, required field, optional slot, URL rule, minimum count or source-of-copy rule changes.

| Content                             | Maximum characters |
| ----------------------------------- | -----------------: |
| Navigation label; footer link label |                 40 |
| Footer text                         |                600 |
| Hero and all section headings       |                 80 |
| Section body / intro                |                600 |
| Item title / product name           |                 80 |
| Item body                           |                400 |
| FAQ answer                          |                800 |

Maximum counts: nav 8; footer links 12; features 12; products 12; steps 8; FAQ 20; gallery 12. Other bounds stay unchanged, including FAQ questions, CTA/UI labels and alt attributes (200), media sources (1000), link destinations (500), and the two-step minimum. `scripts/content-check.cjs` reads the manifest directly; its boundary tests accept each revised limit and reject one character/item over.

Optional images and logos stay optional. A hero without an image uses the whole content width. With no logo, the header shows only left-aligned navigation: no invented site-name slot or empty logo space. Image `alt` values remain accessibility metadata; Figma alt annotations never become visible page text.

Navigation: below 1024 the existing menu closed/open states apply; wherever links are visible they wrap within their container. At 1024 and above the navigation is always expanded, inside the centered 1200px content area. The 1440 header-open references are unused. The no-logo specimen shows nav only, at all three review widths. No new visible website wording or runtime implementation is introduced by these design changes.
