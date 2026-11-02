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
