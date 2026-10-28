# Tank request priorities and off-peak scheduling

Branch `codex/tank-priority-offpeak`, from main `73a0e2f`.

Scope: urgent bypasses shadow work and queues; standard retains today's path;
explicit offpeak requests use a tenant-scoped durable queue, configured model
windows and existing batch support. Ledger evidence records requested priority,
actual dispatch time and measured cost. No UI text or agent call changes.

Implementation and tests pending. Work is managed-cloud-only. No credentials,
GitHub API, production SQL, paid model calls, merges or deployment. Founder-browser
acceptance and screenshots are not claimed. Claude opens the PR.

```sh
git fetch origin main
# exit 0, main -> 73a0e2f
git switch -c codex/tank-priority-offpeak origin/main
# exit 0
```

The standing push rule applies: commit and push after every finished file; stop
if push fails. Offline validation and exact commands will be recorded here.
