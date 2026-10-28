# Rig: delete products from the active retailer catalogue

## Changes

Backend step: `Retailer.delete_products` uses one `store.atomic` transaction for products, private costs, direct fits, family membership, dependent 3D jobs, cached answers/search recall, durable removal records and a count-only import receipt. Quote history is retained. Scheduled refreshes skip removals; successful manual imports restore their included products.

Frontend and browser proof are in progress. This branch is not ready for review yet.

## Decisions I made

- Branch `codex/rig-delete-products` starts at `origin/main` (`4e74b42`). Git only; Claude opens the draft PR.
- Both current and legacy scheduled feed paths respect tenant-scoped removals. “Refresh now” also keeps removals; a manual catalogue import restores them.
- Existing receipt fields are retained: provider `delete-products`, `updated` is the deletion count, `added` and `rejected` are zero. No SKU, private price or contact detail is recorded in the receipt.
- 3D jobs reference the product with a foreign key, so derived jobs for removed products are deleted in the same transaction. Quote requests are untouched.
- Clear the affected tenant’s graph/setup answers and search recall; these may mention the removed product indirectly.

## Commands and results so far

```sh
PYTHONPATH=tank /workspace/market-lab-warnings/.venv/bin/python -m pytest -q tests/test_rig_delete_products.py
# 7 passed, 5 skipped (Postgres not configured for this first run)
RIG_TEST_DATABASE_URL=postgresql://postgres@127.0.0.1:54332/rig_delete_test \
  PYTHONPATH=tank /workspace/market-lab-warnings/.venv/bin/python -m pytest -q \
  tests/test_rig_delete_products.py tests/test_rig_feeds_retailer.py tests/test_rig_feeds_catalogues.py
# 61 passed in 2.29s, including disposable local Postgres databases and schema reapplication
/workspace/market-lab-warnings/.venv/bin/ruff check tank tests --select E9,F \
  --per-file-ignores 'tank/skills/base.socials/1.0.0/run.py:F401'
# All checks passed!
```

## Founder test after deploy

Open `/rig/admin` with the retailer selected, find a real product under Products, press Delete and confirm the displayed count. It must disappear from Products and Rig search. The founder’s live browser check is pending; local proof is not a live completion claim.
