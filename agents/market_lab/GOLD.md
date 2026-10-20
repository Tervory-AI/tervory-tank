# Public series candidates

The room exports only `market.series_fetch`: CSV parsing examples labelled from
stored public observations. `label_source` names the feed, reference and observed
date. It does not claim a later-confirmed prediction.

Surge and shift candidates are omitted. The current data does not supply
independently confirmed later event labels; running detector or gap-scoring code
to manufacture its own expected answer is not independent evidence.

Only platform-owned, allowlisted FFL public feeds on `us-east` qualify. ZA and
unknown regions return an empty list without reading the database. Authentication
still requires the room key. `TANK_REGION` is passed through the room service.

Generation stops at the requested limit (maximum 200). The database streams series
one at a time and reads at most 90 plus the remaining candidate count of recent
observations per series. Each example contains at most 90 points. Pure callers
provide date-ordered observations; duplicate and out-of-order dates are ignored.
Single-pass point streams represent one series.

The approved `market.gap_score@1.1.0` and `market.research@1.1.0` packages from
main are unchanged and are not used to label this export.
