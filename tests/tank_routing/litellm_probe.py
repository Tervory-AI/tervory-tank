import asyncio
import faulthandler
faulthandler.dump_traceback_later(180, exit=True)
import importlib.metadata
import json
from litellm import Router


def row(name, ident, cost, text):
    return {'model_name': name, 'litellm_params': {'model': 'openai/gpt-4o-mini',
        'api_key': 'placeholder', 'mock_response': text,
        'input_cost_per_token': cost, 'output_cost_per_token': cost},
        'model_info': {'id': ident}}


async def main():
    assert importlib.metadata.version('litellm') == '1.106.4'
    router = Router(model_list=[row('placeholder-group', 'placeholder-direct', .00000095, 'placeholder direct'),
        row('placeholder-group', 'placeholder-hf', .0000008, 'placeholder hosted'),
        row('placeholder-fallback', 'placeholder-fallback-id', .000001, 'placeholder fallback'),
        row('placeholder-config', 'placeholder-config-id', .000001, 'placeholder config')],
        fallbacks=[{'placeholder-group': ['placeholder-config']}], routing_strategy='cost-based-routing', num_retries=0)
    messages = [{'role': 'user', 'content': 'placeholder question'}]
    deployment = await router.async_get_available_deployment(model='placeholder-group', messages=messages, request_kwargs={})
    assert deployment['model_info']['id'] == 'placeholder-hf', deployment['model_info']['id']
    direct = await router.async_get_available_deployment(model='placeholder-direct', messages=messages, request_kwargs={})
    assert direct['model_info']['id'] == 'placeholder-direct'
    answer = await router.acompletion(model='placeholder-group', messages=messages,
        fallbacks=['placeholder-fallback'], mock_testing_fallbacks=True)
    assert answer.choices[0].message.content == 'placeholder fallback', answer.choices[0].message.content
    pinned = await router.acompletion(model='placeholder-direct', messages=messages, disable_fallbacks=True)
    assert pinned.choices[0].message.content == 'placeholder direct'
    import httpx
    from litellm.proxy import proxy_server
    from litellm.proxy._types import UserAPIKeyAuth
    from litellm.proxy.auth.user_api_key_auth import user_api_key_auth
    proxy_server.llm_router = router
    proxy_server.general_settings['dangerously_allow_mock_testing_request_params'] = True
    async def identity():
        return UserAPIKeyAuth(api_key='placeholder', user_role='proxy_admin')
    proxy_server.app.dependency_overrides[user_api_key_auth] = identity
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=proxy_server.app), base_url='http://placeholder') as client:
        response = await client.post('/v1/chat/completions', json={'model': 'placeholder-group',
            'messages': messages, 'fallbacks': ['placeholder-fallback'], 'mock_testing_fallbacks': True})
        assert response.status_code == 200, response.text
        assert response.json()['choices'][0]['message']['content'] == 'placeholder fallback'
        print("placeholder: fallback HTTP passed", flush=True)
        nested = await client.post('/v1/chat/completions', json={'model': 'placeholder-fallback',
            'messages': messages, 'fallbacks': [{'model': 'placeholder-direct', 'disable_fallbacks': True}],
            'mock_testing_fallbacks': True})
        assert nested.status_code == 200, nested.text
        assert nested.json()['choices'][0]['message']['content'] == 'placeholder direct'
        normal = await client.post('/v1/chat/completions', json={'model': 'placeholder-group', 'messages': messages, 'fallbacks': []})
        assert normal.status_code == 200, normal.text
        assert normal.json()['choices'][0]['message']['content'] == 'placeholder hosted'
        print("placeholder: normal HTTP passed", flush=True)
        direct_response = await client.post('/v1/chat/completions', json={'model': 'placeholder-direct', 'messages': messages, 'disable_fallbacks': True})
        assert direct_response.status_code == 200, direct_response.text
        assert direct_response.json()['choices'][0]['message']['content'] == 'placeholder direct'
        print("placeholder: direct HTTP passed", flush=True)
        for reply, rate in [(normal, .0000008), (direct_response, .00000095)]:
            usage = reply.json()['usage']
            expected = (usage['prompt_tokens'] + usage['completion_tokens']) * rate
            assert abs(float(reply.headers['x-litellm-response-cost']) - expected) < 1e-12, (dict(reply.headers), usage, expected)
        print("placeholder: cost headers passed", flush=True)
        settings = await client.get('/router/settings')
        assert settings.status_code == 200, settings.text
        assert settings.json()['current_values']['fallbacks'] == [{'placeholder-group': ['placeholder-config']}]
        print(json.dumps({'http_status': response.status_code,
            'request_fallback': response.json()['choices'][0]['message']['content'],
            'hosted_cost': normal.headers['x-litellm-response-cost'],
            'direct_cost': direct_response.headers['x-litellm-response-cost'],
            'direct_model_group': direct_response.headers.get('x-litellm-model-group'),
            'configured_chain_readable': True}))

    print(json.dumps({'version': importlib.metadata.version('litellm'),
        'lowest_cost_deployment': deployment['model_info']['id'], 'request_fallback': answer.choices[0].message.content,
        'pinned_direct': pinned.choices[0].message.content}))

asyncio.run(main())
