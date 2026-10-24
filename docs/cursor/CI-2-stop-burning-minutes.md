# CI-2: stop CI running out of minutes

> Written 23 Oct 2026. On 22 Oct GitHub Actions ran out of minutes. Every push to a PR branch re-ran the full suite: `tank` takes about 12 minutes, `workspace` 5, `savings-page` up to 8 and `tisan-site` 5. Older runs were never cancelled. With six builders pushing all day, that used up the plan. **Builder: Grok.**

**Files you may change:** `.github/workflows/ci.yml`, `.github/workflows/tisan-site.yml`, `.github/workflows/rig-forge.yml`, `docs/ops/self-hosted-runner.md`, and `tests/` (workflow tests only).

1. **Cancel superseded runs.** Add this to `ci.yml`, `tisan-site.yml` and `rig-forge.yml`:
   ```yaml
   concurrency:
     group: ${{ github.workflow }}-${{ github.event.pull_request.number || github.ref }}
     cancel-in-progress: ${{ github.event_name == 'pull_request' }}
   ```
   PR runs cancel older runs on the same PR. Runs on `main` are never cancelled, because deploy-on-merge depends on them.
2. **Stop `savings-page` cancelling `main`.** It hit its 8-minute limit twice on 22 Oct, which cancelled CI on `main` and skipped the deploy. Raise it to 12 minutes, and cache whatever it installs every run (Playwright browsers, pip, npm) with `actions/cache`.
3. **Use our own runner.**
   - `ci.yml` already supports a self-hosted runner (`docs/ops/self-hosted-runner.md`, switch `SELF_HOSTED_RUNNER_ONLINE`).
   - Stand one up on a **dedicated small server**, never a production box: for example Hetzner CX22 or similar, which is the founder's cost decision. Follow the doc exactly:
     - the runner user has no sudo;
     - it's an ephemeral runner;
     - labels `self-hosted, linux`;
     - the fork guard stays.
   - Then the founder sets the repo variable `SELF_HOSTED_RUNNER_ONLINE=true`.
4. **Measure it.** In the PR, list each workflow's minutes per run before and after, from the run timings.

## Done when
- A second push to a PR cancels the first run.
- `main` runs are never cancelled.
- `savings-page` passes within the new limit.
- With the switch on, `tank` and `workspace` run on our runner, and with it off they fall back to GitHub's machines.
