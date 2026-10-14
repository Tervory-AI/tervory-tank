Repo Tervory-AI/tervory-tank. Start only after PRs #46 (B3) and #45 (C13) are merged; pull main first. Read AGENTS.md, then docs/cursor/B3b-base-wiring.md and do all of it.

New base.scrape_site 1.2.0 that also returns the page html (capped 400 KB). In agents/base/pipeline.py pass html and the engine id to base.extract and base.business_data, label code answers site:code, keep 1.0.0 working. In tank/admin.py read agent_base.records instead of base.records (read-only). No model call added anywhere.

Stay inside the brief's "Files you may change". Free steps only: no paid service, key or model call unless the brief names it. No secrets in code or logs. One branch, one PR, never push to main. Do not merge: the founder merges after review (docs/RUNBOOK.md). Open the PR when CI is green and write "ready for review".
