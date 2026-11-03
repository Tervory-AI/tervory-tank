# Rig cart US — dependency stop, 3 November 2026

Incomplete; not ready for founder acceptance. Claude opens the PR. No merge or deployment was performed.

The existing cart work was preserved, main was merged, and the pending test change was committed and pushed as `d1b8bbd3`. That change uses `Service(store)` instead of a partial test double in `tests/test_rig_cart.py`.

## Exact missing dependency

The original brief requires: “Merge it cleanly when it lands, and reuse its ‘store confirms payment’ step rather than writing a second one.” The no-payments branch has not landed on main (`1ad2c794`). Its current head is `2d7de0464f13563fa41440bd4be6392830df3b8d` and defines `QuoteService.confirm_store_payment`. Neither that method nor a `store_confirms_payment` implementation exists in this branch's production service.

`agents/rig/rigbox/cart.py:179` refuses checkout without a callable `store_confirms_payment`; line 244 invokes that callback after verified platform confirmation. The tests substitute a callback. This does not prove real supplier fulfilment, so no such completion is claimed. A bridge to the shared confirmation method remains necessary after the dependency lands, with integration tests proving quantity, tenant scope, and exactly-once supplier orders. Copying a separate fulfilment implementation here would violate the reuse requirement; merging all no-payments changes here would change the ZA quote flow, which the cart brief excludes.

Remaining work includes the shared confirmation integration, complete official-source/line citations for platform fakes and credential mechanisms, evaluation of the four additional platforms, and a fresh full Rig test run with throwaway Postgres. WooCommerce real-store tax and `payment_url` amount remain founder acceptance checks. No UI was added; Figma remains Proposed.

## Commands and evidence from this resume

All commands ran in `/workspace/codex-rig-cart`.

```sh
git status --short && git log -1 --oneline
git fetch origin && git merge origin/main
git add tests/test_rig_cart.py
git commit -m 'tests(rig): use real service interface in cart tests'
git fetch origin && git merge origin/main
git push origin codex/rig-cart-us
git merge-base --is-ancestor 2d7de0464f13563fa41440bd4be6392830df3b8d origin/main
rg -n 'store_confirms_payment|confirm_store_payment' agents/rig/rigbox/quotes/service.py agents/rig/rigbox/service.py agents/rig/rigbox/cart.py
PYTHONPATH=agents/_chassis:agents/rig /workspace/codex-tiger-t1/.venv/bin/python -m pytest tests/test_rig_cart.py -q --tb=short --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
```

Main merged without conflicts (`fb80bd2b`); pending test commit pushed successfully (`d1b8bbd3`). The ancestry command returned exit 1, confirming the dependency is unmerged. The search found only the two cart callback references, at lines 179 and 244. Focused offline tests: **11 passed in 2.24s**. These are callback-contract tests, not proof of complete shared fulfilment. No fresh full-suite/Postgres result or founder screenshots are claimed in this resume.

This handoff was checked with `git diff --check`, committed, then pushed after `git fetch origin && git merge origin/main`. Final head is reported in the task.
