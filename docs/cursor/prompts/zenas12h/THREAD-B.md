You are Thread B (Regions and pages) in a 12-hour overnight build of Zenas. Repo: https://github.com/Tervory-AI/tervory-tank

Read: AGENTS.md, docs/cursor/ROOMS.md, docs/cursor/Z-zenas-plan.md, docs/cursor/Z-BUILD-ALL.md, docs/cursor/ZENAS-12H.md, then each phase's brief.

Your lane: docker-compose.za.yml (except the pool-loader service, which is Thread A's), litellm/config.za.yaml, tank/main.py (region checks and the /v1/zenas/* proxy only), tank/skills/zenas.deadlines/, workspace/app/matters/, workspace/app/review/, workspace/app/admin/ (a new Zenas feeds section only), workspace/app/api/zenas/, docs/cursor/ROOMS.md (Regions section), and your own tests. Do NOT edit agents/zenas/pool/ (Thread A) or agents/zenas/core/ and agents/zenas/schema.sql (Thread C).

Your phases, in order:
1. Phase 2, the South Africa box (docs/cursor/ZA1-za-region.md) WITHOUT its section 3 catalogue entries (Thread A does those). PR by about 22:30 PT.
2. Phase 6a: zenas.deadlines (pure code, FRCP 6 and SA Uniform Rules, holidays per jurisdiction, rule cited per step) and the Tank /v1/zenas/* proxy to the Zenas room.
3. Phase 6b: Workspace pages Matters, Review (reviewer role + jurisdiction tag; draft beside sources and matched worked matters; approve/reject records reviewer, admission number, changes) and Zenas feeds (built on Thread A's pool status API). Stack on Thread C's phase 4 branch for the Review data. One PR for 6a+6b by 06:00 PT.

Every tank/schema.sql or compose change is tested on an empty database, re-applied, and on a database with the current main schema and agent roles. Rules: one phase = one branch = one PR to main; never push to main; never merge. Open each PR when CI is green with "ready for review", then carry on. Mock every model and network call in tests. No secrets anywhere. When the Lead posts CHANGES NEEDED on your PR, fix it on the same branch.
