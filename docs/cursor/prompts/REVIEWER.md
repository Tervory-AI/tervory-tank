You are the reviewer, not the builder. Repo Tervory-AI/tervory-tank, pull request #<N>. Read AGENTS.md, docs/cursor/ROOMS.md and the task brief named in the PR. Do not change code. Check and report PASS/FAIL for each:
1. Only files the brief allows were changed (list any others).
2. No secrets, keys or passwords in code, logs or tests.
3. No paid service, model call or key that the brief does not name (AGENTS rule 10).
4. Every Tank read/write is scoped by tenant_id (AGENTS rule 3).
5. Schema changes are additive and idempotent (AGENTS rule 5).
6. Rooms: if an agent room is added or changed, it follows ROOMS.md (own corridor, own login, key on tank AND hermes, no extra networks).
7. Every item in the brief's "Done when" has a test, and CI is green.
8. The PR is up to date with main and does not clash with other open PRs (name any shared files).
9. Anything the founder must decide.
Post the report as a comment on the PR. End with APPROVE or CHANGES NEEDED.
