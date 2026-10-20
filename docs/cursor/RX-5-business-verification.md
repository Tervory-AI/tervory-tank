# RX-5 — Radix: business verification and platform integrity

> Written 18 Oct 2026, 18:30 PT. Founder decision: Radix checks **businesses** and activity on a client's own platform. It never builds profiles of individual people (no person look-ups, no aliases, no dark-web or personal-record searches on individuals).

**Files you may change:** `agents/radix/` (new `verify/` module, routes), `tank/skills/radix.*` (new skills at 1.0.0 with evals + CHANGELOG), policy rows appended to `tank/schema.sql` (additive, `ON CONFLICT DO NOTHING`), `agents/radix/schema.sql` (additive), `.env.example` (names only), new tests. Radix stays sealed: any outside host it reaches must be on its approved host list, and adding a host is the founder's approval (RX-2 rule).

## What it does
1. **Business verification** (`radix.verify_business`, code first): from a company name, registration number, domain or licence number: does the business exist in the official registers, is it active, registered address and officers **as published by the register**, licence status (e.g. ATF FFL via Base's data), domain age and owner of record, website matches the registered business. Reuse Base's records and Base's skills; do not re-scrape what Base already holds.
2. **Shell-company signals** (`radix.entity_links`, code): companies sharing a registered address, agent, phone, domain or website template; newly formed clusters; mismatches between the register and the website.
3. **Platform integrity on a client's own data** (`radix.account_links`, code): within one tenant's own seller or account records (which the client uploads or connects), link accounts that share business identifiers (registration number, domain, payout business name, listing templates) to spot a banned operation returning under a new account. Only the client's own data; nothing from outside about individuals.
4. **Website and domain risk** (`radix.site_risk`, code + the existing RX scans): look-alike domains of the client's brand, newly registered domains, missing privacy and cookie notices (RX-4), exposed admin pages (existing scans).
5. **Risk score** (`radix.business_risk`, code): 0–100 with every factor listed and a source link for every finding. No finding without a source.

## Rules
- Code first; a model only for reading unstructured register pages, via Tank, cheapest available, cached.
- Every read and write scoped by tenant. Results are the client's own; nothing is shared across tenants.
- Sources: official business registers and licence lists (US state registers, SEC EDGAR, ATF FFL list via Base, CIPC for South Africa in the ZA region), WHOIS/RDAP for domains. Each source recorded in a catalogue with its terms as information; keyed sources read their key by name and are skipped until set.

## Done when
CI green on fixtures; a fixture business verifies with sources; two fixture companies sharing an address and agent are linked; a fixture banned seller is linked to its new account by shared business identifiers; every score lists its factors with sources; a test proves no skill accepts a person's name, email or phone number as its lookup key.
