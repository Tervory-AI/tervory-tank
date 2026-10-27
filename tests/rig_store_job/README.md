# Rig store job on the real Tank

Run in a disposable cloud workspace with Docker, Python 3.12, Node 22+, openssl,
Chromium, and `workspace/node_modules` installed:

```sh
python tests/rig_store_job/run.py
```

`CODEX_PROXY_CERT` supplies the managed cloud CA for the image build when set.
The runner preserves Docker registry configuration and uses the local daemon.
`CHROMIUM_PATH` can select the installed Chromium executable. It starts isolated
Postgres 16, Redis, Tank's real `main:app`, Rig's production
`rigbox.three_d.asgi:app`, and a local SMTP catcher requiring STARTTLS with a
fixture certificate. Runtime credentials are generated into mode-0600 temporary
files; they are never put in logs, URLs, fixtures or command arguments.

The browser runs the production retailer component, route, server actions and
`workspace/lib/tank.ts`. The external Clerk session boundary supplies two fixture
organization administrators; production sign-in is not exercised. Public DNS is
routed to the local services. API responses, catalogue parsing, field mapping,
publication, key issuance, approved setup building, quotes, SMTP delivery and
training storage are real. There is no provider connection or model stub.

Only the two store IDs and Rig entitlements are seeded. The browser supplies the
CSV and delivery settings through the admin. A second store imports an unrelated
catalogue through Tank. Checks cover cross-tenant catalogue, key, origin, setup,
quote read/retry/resume and settings access, including an injected tenant ID.
The catcher rejects one send with SMTP 451, then accepts the durable retry.
After restarting Tank, the runner observes its actual background collector write
`rig_no_result` and `rig_quote` pairs, including repeated cached misses.

Containers, their database volumes and the test network are removed on exit.
The printed temporary evidence directory retains startup tails, job output,
1440px/390px screenshots and private fixture emails/configuration. Do not commit
its env files, keys, raw snippets or browser-result JSON. The checked-in screenshots
mask the public key and snippet fields. The current job does not deploy anything.

The widget's upstream source is pinned in
`agents/rig/rigbox/quotes/rebuild-widget.sh`; the adjacent `widget-source.patch`
contains the source and test changes. Running the script rebuilds the shopper
UMD and the 3D frontend assets. It leaves the 3D engine and forge unchanged.

For deployment, pass the stack's existing `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`,
`SMTP_PASSWORD` and `SMTP_FROM` to the Rig service. SMTP uses verified STARTTLS.
A new email-only store uses that transport; existing webhook/Odoo configuration
continues to select those senders. Delivery errors use the existing retry state
and safe error codes. An SMTP acknowledgement lost after acceptance can cause a
repeat email; retries preserve the same Message-ID and quote reference.

The additive `agent_rig.training_events` queue commits alongside each quote.
Every completed, nonempty no-result query adds an event, including cache hits.
Tank's five-minute collector saves each tenant/region/source/reference through
`save_pair` and deletes the event in the same transaction. Contacts are excluded;
these pairs are marked private client matter and are not public training exports.
