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

Implementation checkpoint: discovery, ordinary scheduled watches, durable
confirmed-observation delivery, feed provenance and receiver guards are built.

Commands (after `source /workspace/tervory-env/activate.sh`):

```text
python -m pytest -q tests/rig_tiger_prices/test_prices.py tests/test_rig_feeds_retailer.py
31 passed, 1 warning in 1.55s
python -m pytest -q tests/rig_tiger_prices tests/test_rig_feeds.py tests/test_rig_feeds_retailer.py tests/test_rig_delete_products.py
77 passed, 1 warning in 8.19s
```

Outputs: `evidence/receiver.txt`, `evidence/cycle-and-feeds.txt`. The second
command uses disposable loopback Postgres databases, real Tiger handlers and
Tank/Rig ASGI routes, and offline saved pages. Both schemas are applied twice.
Broader regressions and final file/line inventory are next. Founder-browser
proof remains pending; this branch is not deployed. No live database access,
model calls, new key or GitHub API calls. Claude opens the PR; no main push or merge.
