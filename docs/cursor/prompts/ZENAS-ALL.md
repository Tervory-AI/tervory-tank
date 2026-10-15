You are building Zenas, the legal agent of Tervory AI, from start to finish. Repo: https://github.com/Tervory-AI/tervory-tank

Read first, in this order: AGENTS.md, docs/cursor/ROOMS.md, docs/cursor/Z-zenas-plan.md, then docs/cursor/Z-BUILD-ALL.md (your build order and rules). Each phase points to its own brief; read it before starting that phase.

Do phases 1 to 6 in order:
1. US law library at scale (docs/cursor/Z2b-us-law-bulk.md)
2. South Africa box, second region (docs/cursor/ZA1-za-region.md)
3. SA law library, live loading (Z-BUILD-ALL.md section 3)
4. Zenas on the ladder: rule cards, decided cases as worked matters, matching, apply, memos, training pairs (docs/cursor/Z4-legal-ladder.md)
5. Drafting and contract review with Word tracked changes (Z-BUILD-ALL.md section 5)
6. Deadlines, Matters and Review pages, and the Zenas feeds switchboard (Z-BUILD-ALL.md section 6)

Rules:
- One phase = one branch = one PR to main. Stack on the previous phase's branch when you need it and say "stacked on #N" in the PR. Never push to main. Never merge: the founder merges after review.
- Open each PR when CI is green, write "ready for review" in its description, then go straight to the next phase.
- Stay inside each brief's "Files you may change".
- Every schema.sql change is tested on an empty database, re-applied on itself, and on a database where the current main schema and agent roles already exist (Tank went down on 14 Oct from an ownership change on a table-owned sequence).
- Mock every model and network call in tests. No secrets in code, URLs, logs or tests. Keys only from the environment by name, listed in .env.example, skipped cleanly until set.
- Data use is the founder's decision: record each source's terms as information, never block a source yourself. Judgments are public record, stored as published. No criminal law, ever.

When all six PRs are open, post one summary: each PR link, what it does, the merge order, and every key name the founder must add in Coolify.
