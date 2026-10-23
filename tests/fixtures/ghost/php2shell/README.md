# PHP2Shell replay fixtures (21 Oct 2026)

Local test data only. Nothing here is fetched from, or sent to, any live system.

- `nvd-CVE-2026-109618.json`, `nvd-CVE-2026-109619.json`: NVD 2.0 shaped records
  for the PHP2Shell pair (PHP before 8.4.27; Coolify before 4.4.7).
- `kev.json`: a CISA KEV shaped feed listing both.
- `inventory-before.json`: a host report showing Coolify 4.4.6 on PHP 8.4.23.
- The "after" inventory is the sanitised host report in `../host-a-report-2026-10-23.json`
  (Coolify 4.4.7 on PHP 8.4.27).
