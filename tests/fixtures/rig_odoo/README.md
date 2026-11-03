# Offline Odoo quotation recording

`quotation.json` is a synthetic recording of the fake server's complete draft
quotation exchange. It contains only invented credentials and identities. It is
not a recording from Custom Nation or a live Odoo installation.

`tests/test_rig_odoo_contract.py` replays the recording through an independent
ASGI HTTP server, checks every request exactly, and records observed exchanges in
the pytest temporary directory. The server accepts no unrecorded calls. Variants
cover Odoo 16/17/18, a committed order whose response is lost, unsupported versions,
authentication/error envelopes and each missing setting. Existing quote tests
also cover product mapping, setup repricing, partner reconciliation and privacy.

Contract references: Odoo's [JSON-RPC envelope and service dispatch](https://www.odoo.com/documentation/18.0/developer/howtos/web_services.html),
[authentication and execute_kw positional/keyword arguments](https://www.odoo.com/documentation/18.0/developer/reference/external_api.html),
and [relational field command protocol](https://www.odoo.com/documentation/18.0/developer/reference/backend/orm.html#odoo.fields.Command).
No confirm, invoice, payment, card, refund or mail method appears in the recording.
Live module configuration, permissions and product mappings still require a
separate operator check when the existing Odoo settings are populated.
