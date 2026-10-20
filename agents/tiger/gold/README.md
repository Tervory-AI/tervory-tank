# Public price candidates

Rebuild `public-pages.zip` with `python tests/build_tiger_gold_bundle.py` from the repository root. The bundle preserves all 109 source records and PNGs, with scripts and tracking attributes removed from HTML. The endpoint excludes held-out, conflicting and unreadable rows. No human verification is asserted.

For additional snapshots an authorised collector can write `/data/gold/public_snapshots.json`, a JSON array. Each row requires `url`, `html`, `region`, `public: true`, `robots_allowed: true`, `terms_allowed: true`, `challenge: false`, `authenticated: false`; optional `png_base64` supplies the actual same-page screenshot. No private watch data belongs here. Query strings and credential-bearing URLs are refused. Only single visible prices agreeing with JSON-LD or microdata qualify. Collection is not performed by this endpoint.

The result's `expected.items` labels price and known currency only. Unknown names, identifiers and stock status are omitted; downstream comparison must project onto the labelled fields. These are machine candidates for spot-checking, not checked training examples.
