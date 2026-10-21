Repo Tervory-AI/tervory-tank. Read AGENTS.md, docs/cursor/ROOMS.md, docs/cursor/GRAD-1-squad-graduation.md, then docs/cursor/LABELS-1-label-families.md and do all of it.

Since #184, auto labels only count when rows share a label_family. Add label_family to every room's gold_sources.py (Zenas, Radix, Tiger, Rig, Tisan) by rule + truth + month, and give Market Lab its own /gold/candidates (shift/surge from later-known values, series_fetch from official matches) with room-key auth.

Branch from latest main. Stay inside the brief's "Files you may change". Do not change any room's live behaviour. No secrets in code, URLs, logs or tests. One branch, one PR, never push to main. Do not merge: the founder merges after review. Open the PR when CI is green and write "ready for review".
