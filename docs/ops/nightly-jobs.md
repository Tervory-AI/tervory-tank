# Nightly and scheduled jobs

Inventory of schedules that fire on Boston / ZA. Coolify scheduled tasks are listed with resource uuid and cron. In-process chassis / Tank loops are **not** duplicated as Coolify tasks.

## Coolify scheduled tasks (added Job 3 / 28 Oct 2026)

| Name | Resource | uuid | Cron (UTC) | Command | Container |
| --- | --- | --- | --- | --- | --- |
| zenas-pool-nightly | agent-zenas (Boston) `r7qzm460bc4scnskurlowbvn` | `fz7xlcsopjtgpmycnb0swwt1` | `0 2 * * *` | `python -c "from agents.zenas.pool.nightly import main; main()"` | `agent-zenas` |
| zenas-pool-nightly | agent-zenas-za (Afrihost) `rslmzhfmq5tf9ipx385gmu6p` | `m6ggpxv2iegsecpkakqzlwxd` | `0 2 * * *` | same | `agent-zenas` |

Timeout 7200s. `python -m agents.zenas.pool.nightly` does **not** run `main()` because `agents.zenas.pool` imports the module first; use the `-c` form above.

## Already triggered (do not duplicate)

| Job | How it fires | Evidence |
| --- | --- | --- |
| Base `gold.nightly` | Chassis `schedule_loop` in agent-base | `agent_base.schedules` cron `15 1 * * *`, `last_run` recent |
| Base / rooms `ping` | Chassis `*/5` | `last_run` every few minutes |
| Zenas `ping` | Chassis `*/5` on agent-zenas | `last_run` recent |
| Tank training `export` / `gold` | `tank/training.py` `schedule_loop` 02:00 UTC | `tank.policy_log` `training.schedule` complete |
| Tank training `retest` | same, Sunday 06:00 UTC | `training.schedule` retest markers |
| Rig expire_searches / pull_feeds | Chassis `0 3 * * *` | `agent_rig.schedules` |
| Rig quote retry / discover | Chassis `*/5` | `agent_rig.schedules` |
| Market Lab refresh / resolve | Chassis daily | `agent_market_lab.schedules` |
| Market Lab opportunities | Chassis `40 6 1 * *` (monthly) | rows present; `last_run` null until due |
| r2-backup nightly | Compose service `r2-backup` (`--nightly`) on Boston tank | container `r2-backup-xnmc0jkz8j9i5jh1jwanbsfv-*` |
| GitHub watchdog | `.github/workflows/watchdog.yml` `*/10` | Actions schedule |
| GitHub live-check | `.github/workflows/live-check.yml` `*/30` | Actions schedule |
| Ghost inventory nightly | In-process `asyncio` task in agent-ghost | process lifespan |

## Was untriggered (now Coolify)

| Job | Before | After |
| --- | --- | --- |
| `agents/zenas/pool/nightly.py` live pool update (+ convert/selftest hooks) | Nothing called it (Prompt A may still add docs; Coolify had 0 tasks) | Coolify tasks above on US and ZA |

## Missing settings (names only)

- `NY_OPENLEG_API_KEY` — `ny-laws` source stays `not_configured` until set on agent-zenas
- SAFLII may return challenge pages on ZA (network/WAF); not a Coolify setting

## Proof

Agent box: `/workspace/boston-nightly-jobs-proof/`
