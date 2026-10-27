# market.series_fetch

## 1.2.0
- Refresh the bundled feed dependency closure from Market Lab: county labels, readable publisher pages, commodity units and published-table parsing, history pagination and blocked-site handling. Include the newly required `published.py`.
- Preserve the skill entry point, pure series logic and three saved listing fixtures. No new provider, key or dependency. Versions 1.0.0, 1.1.0 and 1.1.1 are unchanged.
- Add saved county/state listing cases and refusal cases, plus offline feed regressions for every changed bundled module. Run the new candidate in a separate Tank-only interpreter so cached legacy imports cannot hide bundle failures.

## 1.1.0
- Hold a batch that fails the series checks before it is stored. `1.0.0` is unchanged and stays in service until this version passes evals and a founder approves it.
- The feeds copy in this package includes the batch guard. Listing counts that stay inside the jump limit still store.

## 1.0.0
- First version. CSV and XLSX uploads, a monthly listing count through the feeds package, and a FRED read that is never stored.
- Candidate eval fix: ship the unchanged feeds dependency closure and three listing fixtures inside this package, which Tank already copies into its image. Resolve the bundled pure module consistently in repository and Tank runs. All three evals run without network access.
