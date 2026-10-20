Repo Tervory-AI/tervory-tank. Read AGENTS.md, docs/cursor/ROOMS.md, docs/research/AGENT-TESTS.md, then docs/cursor/TRAIN-1-squad-training.md and do all of it.

One store of gold examples for every agent (existing evals imported as candidates, more from accepted live work), a checking page at /skala/gold (Right / Wrong / Skip, 20% held back automatically), a weekly re-test that opens a GitHub issue on a drop of more than 2 points, training pairs from every approved result (region kept), a nightly export to a private Hugging Face dataset when HF_TOKEN and HF_ORG are set, and a squad training view on the Tank page.

Every schema change is tested on an empty database, re-applied, and on a database with the current main schema and agent roles. Stay inside the brief's "Files you may change". No secrets in code, URLs, logs or tests. One branch, one PR, never push to main. Do not merge: the founder merges after review. Open the PR when CI is green and write "ready for review".
