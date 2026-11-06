"""Offline proof against the real LiteLLM proxy; every provider response is fake."""
import asyncio
import sys
from urllib.parse import urlsplit

import httpx


def config():
    return {
        'model_list': [
            {'model_name': model, 'litellm_params': {'model': 'openai/' + model,
             'api_base': 'http://127.0.0.1:1/v1', 'api_key': 'placeholder'}}
            for model in ('local', 'local-large')
        ] + [{'model_name': 'gpt-oss-small', 'litellm_params': {
            'model': 'openai/gpt-4o-mini', 'api_key': 'placeholder', 'mock_response': 'billing'}}],
        'litellm_settings': {
            'callbacks': ['tenant_traces.callback'], 'num_retries': 0,
            'fallbacks': [{'local': ['local-large', 'gpt-oss-small']}, {'local-large': ['gpt-oss-small']}]},
    }


async def verify(base):
    # Reuse the existing audited fake-provider gateway probe; no new provider path.
    from litellm_probe import completion
    assert urlsplit(base).hostname == '127.0.0.1'
    async with httpx.AsyncClient(base_url=base, timeout=15, trust_env=False) as client:
        roster = (await client.get('/model/info')).json()['data']
        assert not {'local', 'local-large'} & {r['model_name'] for r in roster}
        for model in ('local', 'local-large', 'gpt-oss-small'):
            response = await completion(client, model=model, messages=[{'role': 'user', 'content': 'placeholder'}])
            assert response.status_code == 200 and response.json()['choices'][0]['message']['content'] == 'billing'
    print('local rung offline: hosted fallthrough and disabled tracing passed', flush=True)


if __name__ == '__main__':
    asyncio.run(verify(sys.argv[1]))
