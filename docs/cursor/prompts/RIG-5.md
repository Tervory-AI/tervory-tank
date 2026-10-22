Run in the cloud only, on your own cloud machine. Never use my computer. Work without asking me: the brief, docs/cursor/CONTEXT.md and AGENTS.md are your answers; list your choices under "Decisions I made" in the PR. Stop only for a secret value, a paid service or key the brief does not name, an irreversible production action, or a conflict with a hard rule.

Repo Tervory-AI/tervory-tank (RIG-4 and RIG-5 also Tervory-AI/tervory-rig; read its AGENTS.md). Read AGENTS.md and docs/cursor/CONTEXT.md, then docs/cursor/RIG-PHASE-1.md and do lane RIG-5 exactly as written there, and nothing from the other lanes.

3D files are made by the RIG-5F forge. Call its job interface; if RIG-5F hasn't merged yet, use a stub with the same interface and say so in the PR.

Other lanes are running at the same time. In tank/main.py and tank/schema.sql add only route registrations and additive schema, so merges stay clean. Branch from latest main. Stay inside the brief's "Files you may change". No secrets in code, URLs, logs or tests. One branch and one PR per repo (same branch name in each, PRs linked to each other), never push to main. Do not merge: the founder merges after review. Open a draft PR early so CI runs; mark it ready and write "ready for review" only when every check is green. End the PR with how to prove it live after deploy: which page, route or database row to check.
