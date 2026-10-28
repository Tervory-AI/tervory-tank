# Tiger domain playbooks

Branch: `codex/tiger-domain-playbooks`, started from main `678d47e`.

Plan: reuse `learn_layout`/`read_page` and the existing public-page check path.
Promote a public structural marker after confirmation on three distinct pages
of the same host. New pages try that marker before per-URL learning. Three
consecutive playbook mismatches retire it; fresh confirmations can promote it
again. Client observations remain tenant-scoped. Shared state excludes tenant
identities, prices, names, HTML, credentials and raw page URLs.

No UI, model, scope-policy, site-limit or worker changes. Offline fixtures and
local disposable Postgres will exercise promotion, fallback, retirement,
reconfirmation, restart and privacy. Exact results and file/line inventory
will replace this checkpoint. Founder browser proof is pending deployment.

Claude opens the PR; git pushes only, no GitHub API or merge.

Implementation checkpoint (after `source /workspace/tervory-env/activate.sh`):

```sh
python -m pytest -q tests/tiger_playbooks tests/tiger_alert_page/test_page_changed.py tests/test_tiger_missing_name.py
```

Result: **41 passed in 2.28s**, exit 0. Output: `evidence/focused.txt`.
The new cases run against memory and real disposable Postgres, with the
additive schema applied twice. Broader regression proof follows.
