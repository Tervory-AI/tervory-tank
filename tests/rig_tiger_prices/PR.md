# Automatic Rig prices from Tiger

Branch: `codex/rig-tiger-prices`, based on main `bde4578`.
Founder decision, 28 Oct 04:10 PT: automatically watch every eligible Rig
product for every tenant; no per-SKU control and no page or wording changes.
This supersedes the previously recorded UI blocker.

Implementation plan:
- Reuse Tiger's existing watch validation, scheduler, dispatch and reading code.
- Discover Rig tenants through Tank, then reconcile each tenant's eligible
  catalogue: product page present, no supplier feed and no deletion tombstone.
- Check eligibility again before reading and updating. Never publish a result
  for an obsolete URL, feed-backed product, deleted SKU or another tenant.
- Persist pending confirmed observations and retry failed deliveries through
  the existing Tiger-key-protected `/v1/access/rig/tiger` receiver.
- Exercise the real services offline with two tenants and record results here.

No application changes in this checkpoint. Tests and founder-browser proof are
pending. No live database access, model calls, new key or GitHub API calls.
Claude opens the PR; no main push or merge.
