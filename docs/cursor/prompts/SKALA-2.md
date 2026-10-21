Run in the cloud only, on your own cloud machine. Never use my computer. Work without asking me: the brief, docs/cursor/CONTEXT.md and AGENTS.md are your answers; list your choices under "Decisions I made" in the PR. Stop only for a secret value, a paid service or key the brief does not name, an irreversible production action, or a conflict with a hard rule.

Repo Tervory-AI/tervory-tank. Read AGENTS.md and docs/cursor/CONTEXT.md, then docs/cursor/SKALA-2-approval-safety.md and do all of it.

Approvals that only move forward (newer version and score at least the approved one's on the same cases, else 409 with a plain reason), a separate confirmed rollback, Retire for candidate and staging versions, one row per skill with a collapsed History, "Approve all ready" with one confirm and each approval logged, and 3/3 consecutive passing runs for model-using skills.

Two additions from the founder's review, 21 Oct:
1. Wire the "Approve all ready" button on the founder control panel (/control, from DASH-1) to this route. You may change workspace/app/control/ for that button only.
2. Room-authored candidates (ids starting base.learned. or any <room>.learned.) are never included in "Approve all ready". They need an individual approval that first shows the founder their full run.py, because their evals run model-written code.

Five other lanes are running at the same time. In tank/main.py and tank/schema.sql add only route registrations and additive schema, so merges stay clean. Branch from latest main. Stay inside the brief's "Files you may change". No secrets in code, URLs, logs or tests. One branch, one PR, never push to main. Do not merge: the founder merges after review. Open a draft PR early so CI runs; mark it ready and write "ready for review" only when every check is green. End the PR with how to prove it live after deploy: which page, route or database row to check.
