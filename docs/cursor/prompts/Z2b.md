Repo Tervory-AI/tervory-tank. Read AGENTS.md, docs/cursor/Z-zenas-plan.md (Z2), then docs/cursor/Z2b-us-law-bulk.md and do all of it.

Extend agents/zenas/pool to load the US library at scale from free bulk sources: whole US Code titles (USLM XML), whole CFR parts (eCFR), HTSUS, FRCP/FRE/FRAP, CourtListener and Caselaw Access Project bulk opinions for the named courts (criminal dropped before storage), and the named state statutes where terms allow. Citations extracted with eyecite into a citation graph. A resumable, idempotent one-shot pool-loader with a disk cap and low priority. Tests on fixtures only.

Stay inside the brief's "Files you may change". Free steps only: no paid service, key or model call unless the brief names it. No secrets in code or logs. One branch, one PR, never push to main. Do not merge: the founder merges after review (docs/RUNBOOK.md). Open the PR when CI is green and write "ready for review".
