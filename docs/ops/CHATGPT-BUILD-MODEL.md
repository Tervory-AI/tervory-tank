# ChatGPT sign-in: a build-only model

Founder decision, 31 Oct 2026: "Add ChatGPT, this is a part of the build, not selling to customers."

`build-chatgpt` is a LiteLLM model that uses a ChatGPT subscription login (LiteLLM's `chatgpt/`
provider, model `chatgpt/gpt-6.1-sol`) instead of an API key. It exists so Tervory's own build
work can run when no API provider is funded:

- Skala evals that need a model step (`POST /v1/skala/{id}/{ver}/evals` runs as the platform tenant)
- the Zenas made-up-case self-test, 50 of 50 (`POST /v1/zenas/selftest?home_region=za`, platform tenant)
- test samples run as the platform tenant

It must never answer a customer or tenant. OpenAI's terms do not allow programmatic use of a
ChatGPT login, so the account that signs in can be suspended. Use a login you can afford to lose.

## How it is walled off

1. **Name.** Every build-only alias starts with `build-`. Tank also treats any `chatgpt/` deployment as build-only.
2. **Tenant wall.** `model_call_refusal` refuses a `build-*` model for every tenant except the platform
   tenant (`00000000-0000-0000-0000-000000000001`) and the ids in `TANK_BUILD_TENANTS` (internal test
   tenants only). This covers `/v1/route`, tasks, batch, MoA seats, agent chat and Skala runs.
3. **Policy wall.** `PUT /v1/policy/{task}` refuses a `build-*` model (or escalation model) on the
   platform default row (`tenant_id` null, which every customer inherits), on any non-build tenant,
   and with batching or caching switched on.
4. **Not on the roster.** `/v1/models`, the Command model picker and overrides, the bench, the
   cheapest-model search and graduation never see it.
5. **No graduation.** It cannot be a shadow candidate or be promoted; `_llm` (shadow) and the bench refuse it.
6. **No reuse.** Its policy rows must have `cache_scope` `none` and the semantic cache off (point 3), and the
   semantic cache skips it anyway, so its answers are never reused.
7. **Zenas rule cards.** A card drafted by `build-*` belongs to the build tenant that asked (so no client
   lookup reuses it) and `approve_rule_card` refuses it.
8. **LiteLLM.** No fallback chain points to it and it has no fallbacks. Only Tank holds the LiteLLM key.
9. **South Africa.** The identifier rule still applies: a prompt with a personal identifier is never sent to it.

## Where the login lives

LiteLLM reads and rewrites `auth.json` in `CHATGPT_TOKEN_DIR=/var/lib/litellm-chatgpt`, a named volume
(`litellm_chatgpt_token` on Boston, `za_litellm_chatgpt_token` on ZA) so it survives redeploys. The access
token lasts about ten days and LiteLLM refreshes it in place; each refresh token works once, so the
file must stay writable and must not be copied between boxes. Never back it up, print it or paste it.
Each box signs in separately.

## Sign in (once per box, after the PR is deployed)

Before the first time: in ChatGPT, Settings → Security, allow device code sign-in.

1. Open a shell in the running `litellm` container of the stack (Coolify → the stack → Terminal →
   `litellm`). It runs as uid 10001 with `CHATGPT_TOKEN_DIR` already set.
2. Run:

   ```bash
   python -c "from litellm.llms.chatgpt.authenticator import Authenticator; Authenticator().get_access_token()" > /dev/null
   ```

   It prints `Visit https://auth.openai.com/codex/device` and `Enter code: XXXX-XXXX`, then waits
   up to 15 minutes. (`> /dev/null` hides the returned token; the prompt still prints.)
3. The founder opens that URL, signs in to ChatGPT, and enters the code. Only he enters it; the code
   is a phishing target, so it goes nowhere else.
4. When the command returns, restart the `litellm` container (LiteLLM creates the `chatgpt/` deployment
   at startup). Check: `ls -l /var/lib/litellm-chatgpt` shows `auth.json` owned by 10001; nothing else.
5. Test through Tank as the platform tenant (`task_type` set to a row switched to `build-chatgpt`).

If a second run starts within five minutes of an abandoned one, it waits out the rest of that window first.

## Switch a task to it for a test run, and back

Tank's `PUT /v1/policy/{task_type}` with the Workspace key (`X-Tank-Key: $TANK_API_KEY`). Put the row on
the platform tenant only. Before switching, `GET /v1/policy?tenant_id=00000000-0000-0000-0000-000000000001`
and keep any existing platform-tenant rows for these tasks.

```bash
for t in zenas.rule_card zenas.apply zenas.compose; do
  curl -sS -X PUT "$TANK/v1/policy/$t" -H "X-Tank-Key: $TANK_API_KEY" -H 'content-type: application/json' \
    -d "{\"task_type\":\"$t\",\"tenant_id\":\"00000000-0000-0000-0000-000000000001\",\"rung\":1,\"model\":\"build-chatgpt\",\"max_tokens_out\":4096,\"cache_scope\":\"none\"}"
done
```

Copy `system_prompt`, `max_tokens_out` and `eval_threshold` from the platform default row if the task
has them, so the test measures the same prompt. Then run the test, for example
`POST /v1/zenas/selftest?home_region=za` on za.tervory.com.

Back afterwards (the platform tenant follows the platform default again):

```bash
for t in zenas.rule_card zenas.apply zenas.compose; do
  curl -sS -X DELETE "$TANK/v1/policy/$t?tenant_id=00000000-0000-0000-0000-000000000001" -H "X-Tank-Key: $TANK_API_KEY"
done
```

If a platform-tenant row existed before, PUT it back from the copy you kept instead of deleting.

## Revoke

1. Stop using it: switch every platform-tenant row off `build-chatgpt` (above).
2. Remove the login from the box: in the `litellm` container, `rm /var/lib/litellm-chatgpt/auth.json`,
   then restart `litellm`. (Or delete the volume `litellm_chatgpt_token` / `za_litellm_chatgpt_token` while LiteLLM is stopped.)
3. Kill the tokens: ChatGPT → Settings → Security → sign out of all devices (or the Codex device session).
4. Remove the model for good: a PR that deletes the `build-chatgpt` entries from `litellm/config.yaml` and
   `litellm/config.za.yaml`.

LiteLLM has no logout call for this provider; steps 2 and 3 are the revoke.
