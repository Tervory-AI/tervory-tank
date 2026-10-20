# 1.1.0

- Stage code-first series lookups and gap scoring before summary generation.
- Room supplies existing series adapter inputs in `series`. Areas may reference
  their `demand_series_id` and `supply_series_id`; unresolved or duplicate IDs fail.
- Structured citations and arithmetic cannot be replaced by model output.
- Preserve passage-only and missing-source behavior. No paid route changes.
- Depends on the existing bundled market.series_fetch 1.0.0 pure module (same
  resolver as research 1.0.0); supports its existing adapter input contracts.
- FRED observations remain transient and are omitted from returned series.
- Evals reuse repository gold fixtures for citations, series and gap math.
  `model_text` supplies fixture prose, following the existing skill convention.
  These fixtures are not claimed to be 100 checked real-world examples or a
  live grok-top comparison. Founder approval and shadow evidence remain required.
