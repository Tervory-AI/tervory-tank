You are Thread C (Brain) in a 12-hour overnight build of Zenas. Repo: https://github.com/Tervory-AI/tervory-tank

Read: AGENTS.md (rules 6, 9, 10), docs/cursor/Z-zenas-plan.md, docs/cursor/Z-BUILD-ALL.md, docs/cursor/ZENAS-12H.md, docs/cursor/Z4-legal-ladder.md.

Your lane: agents/zenas/core/, agents/zenas/schema.sql, agents/zenas/app.py (new endpoints only), tank/skills/zenas.* except zenas.deadlines, policy rows appended to tank/schema.sql (additive, ON CONFLICT DO NOTHING), and your own tests. Do NOT edit agents/zenas/pool/ (Thread A) or the files in Thread B's lane. Read the pool through its existing search/store interfaces.

Your phases, in order:
1. Phase 4, Zenas on the ladder (docs/cursor/Z4-legal-ladder.md): rule cards keyed by law version and stale-on-change; decided cases as worked matters (case_facts, once per judgment, public record as published); our released matters; match by per-element fact difference; apply (reuse matching findings at $0, then code via decision tables, then cheapest model only for what differs); compose; training pairs from every decided case and released matter. Skills retrieve, cite_check, rule_card, case_facts, match, apply, compose, plain_language at 1.0.0 with evals. Publish your endpoint shapes in the PR description early; Thread B's Review page uses them. PR by about 02:30 PT.
2. Phase 5, drafting and contract review (Z-BUILD-ALL.md section 5): clause library and playbooks, zenas.draft and zenas.review on the same ladder, .docx output with real Word tracked changes, the first templates. Stack on phase 4. PR by 06:00 PT.

Every schema change is tested on an empty database, re-applied, and on a database with the current main schema and agent roles. Rules: one phase = one branch = one PR to main; never push to main; never merge. Open each PR when CI is green with "ready for review", then carry on. Mock every model in tests. No secrets anywhere. No criminal law, ever. When the Lead posts CHANGES NEEDED on your PR, fix it on the same branch.
