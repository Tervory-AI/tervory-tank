# Market Lab Wave 4

Branch: `codex/market-lab-w3`, explicitly named in the wave prompt; PR #640
remains open and unmerged. No main merge, force push, PR creation or label.
Each item was checked against fetched main (last checked
`c4e1395ec00831561e26227c602a22dfea7ad915`) and pushed separately.

1. Briefs now save source-backed claims with document page/row or prediction
   references and source URLs. Foreign, withdrawn and unsupported claims are
   excluded. Source-free product recommendations are omitted rather than given
   fabricated citations; an empty brief is held with `no_cited_claims`.
2. Warning predictions freeze the pair's historical Wilson lower bound by calling
   the existing `tank/base_reliability.py` function over the authenticated room
   corridor. Existing additive room confidence storage and predictions projection
   are reused. Predictions without a measured warning pair remain unknown.
3. LegiScan's exact Engrossed stage (from the existing saved API fixture) and NOAA
   events in actual supply states enter separate warning pairs and lag histories.
   States come from observed listing-count series, not inferred locations. Keys
   are tested by name only: LEGISCAN_API_KEY / NOAA_TOKEN. Missing keys disable
   scoring. Event rows are tenant scoped and deduplicated; no missing-day zeros.
4. `market_lab.calibration.curve` is an exact $0 code read through ML3's single
   reads route, returning existing confidence/realised-rate bins and counts.

No model calls, new visible labels, page, feed adapter or approved skill version
was added. The feeds bundle is unchanged. H3 waits for 90 days of outcomes;
USPTO ML7 remains parked.

## Changes by file and line

| File | Line | Change |
| --- | --- | --- |
| agents/market_lab/core/brief_sources.py | 14 | Tenant source-backed brief claims. |
| agents/market_lab/core/evidence.py | 81 | Reuse exact source-point rendering. |
| agents/market_lab/core/jobs.py | 226 | Save only supported text and citations. |
| agents/market_lab/core/briefs.py | 16 | Hold empty briefs. |
| agents/market_lab/core/warnings.py | 49, 201 | Keyed event series and frozen Wilson confidence. |
| agents/market_lab/core/event_signals.py | 13 | Exact-stage/supply-region evidence series. |
| agents/market_lab/core/warning_stats.py | 44 | Discrete observed event episodes. |
| agents/market_lab/engines/ffl/engine.py | 47, 106 | Validate engine event rules. |
| agents/market_lab/engines/ffl/supply_map.json | 1 | Keyed event pairs and stage/region rules. |
| agents/market_lab/core/ml3.py | 52 | Calibration curve room read. |
| tank/market_lab_ml3.py | 25, 48, 238, 290 | Curve command/projection and existing Wilson corridor. |
| tank/command.py | 44, 1356 | Register curve tool and adapter. |
| tests/test_market_lab_wave4.py | 1 | Source, confidence, event and curve proofs. |
| tests/test_market_lab.py | 1 | Omit unsupported source-free fixture prose. |
| tests/test_market_lab_ml4.py | 1 | Keep original keyless-pair baseline checks. |
| tests/market_lab_wave4/verification.txt | 1 | Commands, outcomes and item heads. |
| tests/market_lab_wave4/HANDOFF.md | 1 | This handoff. |

## Verification and remaining acceptance

Source head: `0d6d97de3ea5c906cb86f9b9a141b9ff94986505`.
Full local regression: **352 passed, 12 skipped**, including Market Lab feeds,
Tiger email and Base reliability. Optional skips are not claimed as executed.
Ruff E9/F and diff whitespace checks passed. See verification.txt.

CI is the full-suite result of record; final status is reported in PR #640.
Founder acceptance is outstanding: after deployment, receive the next real
brief with existing alerts enabled, follow its citation links and inspect
market_lab.predictions confidence and market_lab.briefs delivery status.
No real delivery or founder screenshot is claimed by offline tests.

Figma frame needed: Workspace calibration curve showing predicted confidence,
realised hit rate, bins and sample counts. Existing dedicated pattern statistics,
citation/report IDs and delivery-reason labels also remain deferred. No new view
or label was built.
