# Moot wave 4

Branch codex/moot-w4 starts from origin/main at 981ac096. No main merge.

Gate 1 reuses the existing AIExecutor, founder-operated hearings, TankClient,
persistent HearingStore, publication projection and public unverified reader.
No new page, UI wording, provider, key, audio service or model bypass is added.

The source builder previously labelled any worked civil case a civil appeal.
It now requires stored appeal=true; false, unknown, string and integer flags are
refused. Criminal matters still hit the existing civil_only gate first. The
source chooser now limits suggestions to decided appeals and filters criminal
metadata; the full source quote, tenant, region and holdout checks remain at
creation/edit time.

Gate 1 checks: test_sources.py and test_api.py, network disabled: 14 passed,
5 database-dependent tests skipped. The durable database path is checked in gate 2.
Required exact repository CI lint passes before push.

Model task types remain moot.counsel and moot.judge through Tank. The existing
policy seeds use rung 1 / luna; a seed is not evidence that the live cheapest
quality threshold passed. No real model call is made for coding/checking, no
price or model-quality result is invented, and no policy is promoted without
actual evaluated evidence. Offline scripted responses prove wiring/guards only.
