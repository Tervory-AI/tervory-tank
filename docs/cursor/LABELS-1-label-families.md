# LABELS-1: label families in every room, and Market Lab gold

> Written 20 Oct 2026, 10:45 PT. #184 (merged) groups spot checks and trust by `(skill_id, source, label_family)`. A row with no `label_family` now only groups with rows of the exact same `label_source`. Every room except Base sets a per-row source and no family, so their auto labels can never pass a spot check. Training is blocked for them until this lands. Base (#188) already sends families. Market Lab has no gold source yet.

**Files you may change:** `agents/radix/gold_sources.py`, `agents/rig/gold_sources.py`, `agents/tiger/gold_sources.py`, `agents/tisan/gold_sources.py`, `agents/zenas/gold_sources.py`, new `agents/market_lab/gold_sources.py` and its `/gold/candidates` route in `agents/market_lab/app.py`, the room list in `tank/training.py` (only to add market_lab if missing), each room's README gold section, tests.

## What a family is
One family = rows made by the **same code rule, from the same kind of truth, in the same calendar month**. Ten spot checks vouch for that family only. A new rule, new truth source or new month is a new family. Keep `label_source` per row, as now.

## Do
1. Set `label_family` in each room:
   - **Zenas:** `converted:{source_id}:{YYYY-MM}` and `statute_section:{source_id}:{YYYY-MM}`. Held-out rows keep `holdout: true` and are never trained on (unchanged).
   - **Radix:** `radix:fixture:v1:{skill}` (fixtures do not change by month).
   - **Tiger:** the 109-page set is `auto:price-gold-109`. JSON-LD matches are `jsonld-match:{YYYY-MM}`.
   - **Rig:** `fitment:{catalogue}:{YYYY-MM}`.
   - **Tisan:** `founder-approved-page:{YYYY-MM}`.
2. **Market Lab gold**, same shape and room-key auth as the other rooms (`GET /gold/candidates?limit=N`, bytes `compare_digest`):
   - `shift_detect` and `surge_detect`: label a past point only once the value after a fixed window (28 days, a constant in code) is known. Use the rule already used live, applied to the later-known values. Family `later-value:{feed}:{YYYY-MM}`.
   - `series_fetch`: a fetched value that matches the stored official value. Family `official-match:{feed}:{YYYY-MM}`.
   - Only public feeds, `public: true`, the box's own region.
3. Synthetic or planted examples (wrong answers made on purpose) get their own family with `synthetic` in the name, as Base does.

## Done when
CI green; tested:
- each room emits a family on every auto row, and rows from two months fall in two families;
- the #184 spot check releases a family after 9 of 10 agree;
- Market Lab labels nothing whose window has not passed;
- Market Lab rejects a wrong room key.

After merge, Claude runs nightly intake once and reports candidates per room and family.
