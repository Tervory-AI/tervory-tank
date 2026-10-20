# Rig gold candidates

`GET /gold/candidates` is room-key only. It labels `rig.search` and `rig.fit_suggest` from a catalogue's own compatibility list, and only when that catalogue is marked public for this box's region.

Every row's `label_family` is `fitment:{catalogue}:YYYY-MM`. The month comes from the catalogue's `observed_on`, then `as_of`, then `updated`. A sealed catalogue with none of those dates uses 2026-10, and that month does not follow the clock. A published date in another month is another family. A catalogue marked synthetic uses a family whose name contains `synthetic`.

Publish keys, shopper mail, and webhooks are not copied. Client catalogues stay out.
