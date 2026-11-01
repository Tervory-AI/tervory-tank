# ZA LiteLLM: DeepSeek off-peak windows live since 31 Oct 2026, 11:48 AM PT

Record correction for [#486](https://github.com/Tervory-AI/tervory-tank/pull/486)
(Tervory Review, [item 1](https://github.com/Tervory-AI/tervory-tank/pull/486#issuecomment-6548577556)).

#486 said the `litellm/config.za.yaml` change "takes effect on the next ZA LiteLLM
deploy". That was wrong. It shipped with #486 itself:

- `.github/scripts/deploy_changed.py:39-40`: `litellm/` is in `MAIN_PREFIXES`, so any
  change under it deploys the main app and then `tervory-tank-za`.
- `docker-compose.za.yml:96-99`: the ZA stack's `litellm` service is built from
  `./litellm` and runs `--config /app/config.za.yaml`.
- Deploy-on-merge run [41230550787](https://github.com/Tervory-AI/tervory-tank/actions/runs/41230550787)
  (push of merge `bd792fb8`, `BEFORE=35cae5ff`) logged `main finished`,
  `tervory-tank-za finished` and `agent-market-lab finished`. The script's output was
  flushed at 18:48:14Z, so the ZA deploy finished at or before 11:48 AM PT on 31 Oct.

What changed on ZA: `deepseek-flash` and `deepseek-pro` gained the same `model_info.offpeak`
block as US (UTC; Mon-Fri 00-01, 04-06, 10-24; weekends all day; charge multiplier 0.5).
Routing uses it only for requests whose priority is `offpeak`, set on the request or by its
policy (`tank/main.py:649`, `:1345-1361`; `tank/priority_queue.py`), and Tank's model listing
shows it (`tank/main.py:1616`). No seed or migration in the repo sets an `offpeak` policy;
policies in the live database were not checked. Review found the values correct, so it is
not reverted.
`litellm/config.za.yaml` has not changed on main since `bd792fb8`.

Not verified here: the running ZA LiteLLM container's loaded config. This record is from
the repo, the deploy script and the deploy run log; no live Coolify or LiteLLM call was made.

Rule from now on (also in `AGENTS.md`): region or runtime config lands in its own PR,
merged and deployed first, before any CI or test PR that depends on it.
