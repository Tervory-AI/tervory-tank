# Sample feeds

These synthetic office products exercise RIG-3 without supplier credentials or live shopper data. They are never loaded on startup. Open `/rig/admin`, choose **Any catalogue**, name each feed, supply a sample website, and declare the currency, country and price type below. Use **Suggest field mapping**, check the fields, confirm and import.

Set the default private rule to freight **1** per item in feed currency, duty **10%**, gross margin **20%**, shop currency **ZAR**. As founder set USD→ZAR **18.50**, EUR→ZAR **20**, NZD→ZAR **11**. These are synthetic test assumptions, not live exchange rates.

| File | Currency | Country | Price type | Product list path | Expected ZAR price |
| --- | --- | --- | --- | --- | ---: |
| `us-distributor.csv` | USD | US | Supplier cost | empty | 534.19 |
| `eu-distributor.xml` | EUR | DE (EU rule) | Supplier cost | empty | 440.00 |
| `nz-distributor.json` | NZD | NZ | Supplier cost | `catalogue.products` | 196.63 |
| `distributor.xlsx` | USD | US | Supplier cost | empty | 788.56 |
| `store-catalogue.csv` | ZAR | ZA | Selling price | empty | 799.95 |

Each file adds one product and writes a receipt. Re-importing with its saved map updates one product. The selling price stays 799.95 when freight, duty or margin changes; it needs no cost rule. To test regional overrides, save an EU rule with freight 2, duty 5%, margin 0%: `EU-STAND` becomes 357.00. A feed override with freight 3, duty 0%, margin 0% takes precedence and makes it 360.00.

All original importers and samples are retained: `shopify.json`, `woocommerce.json`, `google.xml`, and `distributor.csv` (Zanders, Sports South, RSR or Jerry's). Declare USD, US and supplier cost for those files; use their matching source choice and confirm the suggested fields. The optional `rig` object in JSON carries `families`, `setup_templates` and supplier `fits` with evidence in `note`. Supplied fits remain hidden until approved. Human reviews and retailer templates survive refreshes.

Excel uses a deterministic, value-only first worksheet. No macros or formulas run. Source amounts, freight, duty, margin and FX remain server-side. Only one indicative shop price is public.
