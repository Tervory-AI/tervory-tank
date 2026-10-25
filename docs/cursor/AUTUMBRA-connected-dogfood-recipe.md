# Autumbra connected dogfood recipe (fixtures only)

**Product copy:** Autumbra / Autumbra Watch / Autumbra Enforce only.  
**Hold:** no merge, no deploy, no live HF Inference, no live CF WAF apply.  
Leave `AUTUMBRA_HF_LIVE` unset. Call helpers with `live=False`. Guard / Enforce / OSS flags stay OFF unless a test arms them briefly.

## Official stack (AMMOSYNC)

1. #281 ThreatPayload + SLO tile polish  
2. #284 air-gap + Enforce stub (flag OFF) + SLO receipts  
3. #286 Dual-LLM / guardrails tip `620c2ae` (fixtures; NO live HF)  
4. #288 `/admin/autumbra` panel + `/admin/ghost` redirect  
5. #290 Watch OSS ingest (flag OFF; Watch restacks onto #288 tip)  
6. #291 Enforce OSS tip `99c50f0` (flag OFF; ThreatPayload → plan)  
7. #287 patch-as-PR (last; out of SLO lane ownership)

Integration draft branch `grok/autumbra-connected-dogfood` = #286@`620c2ae` + restacked #288 panel.

## Single run (connected tip)

From a checkout of the connected tip (or #286 tip for backend-only):

```bash
# Prefer tank-venv. Never export AUTUMBRA_HF_LIVE.
unset AUTUMBRA_HF_LIVE
source /workspace/tank-venv/bin/activate   # or: /workspace/tank-venv/bin/python -m pytest …

python -m pytest -q \
  tests/test_ghost_threat_payload.py \
  tests/test_ghost_airgap_slo_wraith.py \
  tests/test_autumbra_dogfood_hf.py \
  tests/test_autumbra_dogfood_airgap.py \
  -k 'not test_live_hf_dogfood_when_armed'
```

### Path order proven by fixtures

1. **Propose / match → ThreatPayload burn**  
   - `tests/test_ghost_threat_payload.py`  
   - `tests/test_ghost_airgap_slo_wraith.py::test_match_to_threat_payload_*`  
   - `::test_propose_for_matches_goes_through_air_gap_and_burns_skip`
2. **Practice Shield dry-run → Shields tile medians + Tank receipts**  
   - `tests/test_ghost_airgap_slo_wraith.py::test_dogfood_cycle_populates_slo_medians`  
   - Empty tile: `tests/test_ghost_threat_payload.py::test_summary_stub_metrics_when_no_receipts`  
   - UI copy: `::test_tile_copy_mentions_median_and_goal_without_vendor_names`
3. **Dual-LLM air-gap E2E (fixtures only, #286@620c2ae)**  
   - `dogfood_airgap_e2e(live=False)` in `agents/ghost/dogfood_airgap.py`  
   - `tests/test_autumbra_dogfood_airgap.py::test_dogfood_airgap_e2e_fixtures_only`  
   - `::test_dogfood_airgap_e2e_refuses_live`  
   - `::test_fixture_e2e_loads_synthetic_only`
4. **HF dogfood helpers (still fixtures; refuse live)**  
   - `tests/test_autumbra_dogfood_hf.py` with `live=False` / env unset  
   - Skip or do not arm `test_live_hf_dogfood_when_armed`

### Optional later-stack fixture checks (not on connected tip until restack)

**#290 Watch OSS** @ `b1bba3e` (restacked onto #292 `a374a48`; run from `grok/autumbra-watch-oss`):  
`tests/test_ghost_watch_oss_intake.py`, `tests/test_ghost_watch_oss_wire.py` — flag OFF. Local: **19 passed** (Oct 24 ~5:58pm PT). CI on `b1bba3e`: **pending** (`changes` queued).

**#291 Enforce OSS** tip `99c50f0` (after #290 in merge order):  
- ThreatPayload → `POST /ghost/enforce/oss/plan`  
- propose → Shield → dry_run → Undo  
- Files: `tests/test_ghost_enforce_oss.py` (14) + `tests/test_ghost_enforce_connections.py` (9) = **23** collected  
  - Cycle: `test_shields_propose_raise_undo_dry_run_cycle`  
  - Plan route: `test_post_enforce_oss_plan_404_off_200_on_422_burn`  
  - No HF: `test_no_hf_imports_in_enforce_oss`

**#287** patch-as-PR — last; CI-only; never merge from this recipe.

## Panel wiring

- Route: `/admin/autumbra` (founder). `/admin/ghost` redirects.  
- Shields tile reads `summary()` medians (`None yet` / `No receipts yet` when empty).  
- Practice Shield raise (`dry_run`) stamps `dry_run_at` → time-to-shield medians.
