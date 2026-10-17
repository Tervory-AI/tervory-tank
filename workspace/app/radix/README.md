# Radix page

Route: /radix. Figma: https://www.figma.com/design/ksi7ctRwEnN8wbip1yfuhL?node-id=75-92

Radix uses Market Lab's clean layout, with standard navigation at the top of the
anchored navy panel, product tabs in the middle, and Workspace/Help at the bottom.
Only the body scrolls at normal viewport heights. The official Tervory logo is
unchanged; no Radix-specific logo is added.

Search and chat both sit in the body. Search reads Radix-tagged requests from the
current tenant's existing Tank task queue. The existing API caps retrieval at the
latest 200 workspace requests; the UI discloses that boundary when reached.
Search matches title, reply, and status. Other products and tenants are filtered
out on the server, including when a record ID is opened or used as a reference.

The request thread sits above the text box and its red Send button. Requests use
the existing tier0.answer policy, tagged agent=radix, and poll the existing task
queue for replies. No new paid provider, policy, scan job, or external tool is
introduced. Failed submissions preserve the draft. Accepted work remains in
records even after a timeout or navigation. Answer Sources lists only actual
Radix records included with that request.

Plugins is the connections tab. Its popup contains API keys, Files, Source links,
and MCP connections, with mobile accordions. These connections and code uploads
remain unavailable. Saved credential examples are dots and labelled Example.
The page does not request keys or change agent egress or hostname configuration.

Offline findings/reports remain clearly labelled examples because no Workspace
endpoint exposes the scanner's findings yet. Request records and model guidance
must not be mistaken for a completed code scan or approval to release code.

## Checks

The existing CI runs the Next build, lint, secret checks, and repository tests.
The Radix workflow bundles the actual UI, CSS, and request-service logic in a
disposable GitHub runner, with a mock authenticated task store for browser tests.
It checks tenant/product isolation, references, validation, search, queued replies,
failed-send recovery, Sources provenance, body scrolling, Plugins, keyboard focus,
mobile layouts, and unchanged logos. Screenshots use labelled test examples.

No production auth bypass or public preview route is added. No builds or installs
are needed on the founder's laptop.

Figma: desktop 75:92, mobile 75:142, example report 75:172,
Plugins 75:215 / 75:260 / 75:305 / 75:350, mobile Plugins 75:395.
