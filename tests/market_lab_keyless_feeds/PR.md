# Market Lab keyless feeds

Branch: `codex/market-lab-keyless-feeds`, from main `a93da69`.
Work and proof are committed and pushed per completed file. No GitHub API.

Implementation in progress: reuse the existing tenant-scoped Source links form,
feed adapters, stored source documents and schedules for RSS/Atom. Add UN Comtrade
preview and SearXNG collection without model calls. Check current USPTO access;
where a key is required, name its setting and keep the feed off.

The current main has no Job 2 signal schema or `marketlab.signal.scored` contract.
Do not invent or publish a scored event before that dependency is merged.

Census, FRED, EIA, NOAA and LegiScan keep their existing key gates. MarineTraffic,
Freightos and LME are skipped because they are paid. Reddit is skipped because it
requires app sign-in. No credentials or sign-in work is part of this task.

Offline fixture tests, exact commands, source access evidence and founder-facing
proof are pending. No deployed acceptance or founder screenshot is claimed.
