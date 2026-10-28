# Market Lab prediction confidence and calibration

Branch: `codex/market-lab-calibration`, recovered from base `678d47e`.
Claude opens the PR. Git only; every finished file is committed and pushed.

Implementation checkpoint: the prediction ledger is append-only. Each resolution
links to its original prediction through `sources[].resolves`. Confidence will be
computed at insertion using only the same tenant's earlier, resolved predictions
of the same kind, feed and horizon. The stored confidence and supporting count
will remain frozen when the outcome is appended. No comparable history means
`confidence: null`, `confidence_count: 0`, rather than an invented prior.

Calibration will expose ten fixed probability bands as API data, grouped by kind,
comparing the confidence stated on the original prediction with realised hit rate.
Unknown/unmeasurable outcomes and historical predictions without a stated
confidence will not be presented as calibrated predictions. Repeated resolution
rows must not count the same forecast twice. No model calls or page changes.

Implementation, exact API contract, file references and offline proof are pending.
No deployment or founder-browser acceptance is claimed.
