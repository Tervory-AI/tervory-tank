# READ-1: agents read a page the way a person does

> Written 21 Oct 2026. Founder (20 Oct): agents must have "the tools to be a human". Today Base's brain gets a web page as **raw HTML, cut at about 8,000 characters** (`agents/_brain/runner.py`, the browser branch of `tool_result`). A page's HTML starts with its `<head>` (scripts, fonts, styles, tracking), so the brain often sees mostly setup code. The page's links come after the HTML and are cut off entirely. So the brain can't see "Contact", "About" or "Locations" to click next, and misses phone numbers, emails and addresses that are on the page.

**Files you may change:**
- `agents/_brain/` (`runner.py`, `browser.py`, and a new `agents/_brain/reader.py`);
- `agents/tiger/` (only if Tiger's room shares the same reader path);
- tests.

No change to Tank, the gateway's security checks, or approved skill versions.

1. **What the brain receives from every page, in this order, within the same size budget:**
   1. **page facts:** final URL, title, language, and whether a human check, age gate, login wall or error page was detected;
   2. **links** (up to 30), as visible text plus URL, ranked so contact, about, location, store, dealer, hours and FFL links come first, and same-site links before others;
   3. **contact details found on the page:** phones, emails, street addresses, opening hours, and social profile links, extracted by code (no model) and each tagged with where it was found;
   4. **visible text:** what a person sees on screen (no scripts, styles or hidden elements), in reading order, with headings kept, cut to about 5,000 characters.
2. **Structured data first.** If the page has schema.org JSON-LD or microdata (LocalBusiness, Store, Organization), read name, address, phone, hours and geo from it before parsing text. It is the most reliable source and costs nothing.
3. **PDFs** get the same shape: facts, links found in the PDF, contact details, and text.
4. **Raw HTML is never sent to a model.** It stays in the room's own storage (BUCKET-1) as evidence, with the page's screenshot, so a person can check what the agent saw.
5. **Free and fast:** extraction is plain code (selectolax or the existing parser), with no model call. Record the extraction time per page on the receipt.
6. **Measure it.** Add a counter per run: pages read, links followed, contact details found per page, and sites resolved. The pilot before and after this change shows the difference.

## Done when
CI green. Tests:
- a page with a long `<head>` still gives the brain its links and contact details;
- JSON-LD LocalBusiness is read first;
- hidden text and scripts are never included;
- links are ranked contact-first;
- PDFs give the same shape;
- the size budget is respected;
- the raw HTML goes to storage, not to the model.
