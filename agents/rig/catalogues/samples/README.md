# Sample feeds

These synthetic office products exercise RIG-3 without supplier credentials or live shopper data. They are not a retailer catalogue and are never loaded on startup. Import a file through `/rig/admin`, choosing Shopify, WooCommerce, Google Merchant or Zanders (CSV). Sports South, RSR and Jerry's use ACCESS-1's existing aliases or an explicit column mapping.

Set the private price rule and a founder-managed USD-to-ZAR rate first. Feed prices are treated as supplier costs. The result is one indicative ZAR price; source amounts, freight, duty, margin and exchange rates stay server-side.

The optional `rig` object in JSON feeds carries `families`, `setup_templates` and supplier `fits` with evidence in `note`. A supplied fit enters review and is hidden until approved. Standard feeds without this object still import products. Setup templates chosen by a retailer take precedence over subsequent feed defaults.
