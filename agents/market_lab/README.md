# Market Lab gold candidates

`GET /gold/candidates?limit=N` requires `X-Tank-Key` equal to this room's `TANK_KEY`. The check compares the header and the key as bytes. Limits are 1–200. The box region comes from `TANK_REGION`, not from the request.

The route reads `/data/gold/<region>/public-feeds.jsonl`. A missing file returns an empty list. Only records with `public: true` and this box's region are labelled. Another tenant's series is skipped. The room image copies `gold_sources.py` next to `app.py` so this import loads. Nothing else in the room changes.

Shift and surge label a past point only after a stored value at least 28 days later is known (`WINDOW_DAYS`). They use the same detection the room already runs, on those later-known points. The newer point, whose own 28 days have not passed, is not labelled. The family is `later-value:{feed}:YYYY-MM`.

`market.series_fetch` labels a fetched point only when its value matches the stored official value. The family is `official-match:{feed}:YYYY-MM`.

A feed marked synthetic uses a family whose name contains `synthetic`. These rows are candidates for a spot check. They are not trained on by themselves.
