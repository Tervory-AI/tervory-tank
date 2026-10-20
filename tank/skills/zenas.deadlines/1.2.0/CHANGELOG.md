# 1.2.0

- South African calculations require `service_date`, the date the sheriff served the papers as recorded in the return of service.
- A generic trigger or order date cannot substitute for service. The result records the service date and explains its exclusion.
- United States trigger handling and court-day counting are unchanged.
- Added eval coverage for different order/service dates and missing service dates. Pending founder approval after staging evals.
