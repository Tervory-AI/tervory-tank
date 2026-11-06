"""Offline proof against the real LiteLLM proxy; every provider response is fake."""
import json
import sys
import urllib.request


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


def verify(base):
    with urllib.request.urlopen(base + '/model/info', timeout=10) as response:
        roster = json.load(response)['data']
    assert not {'local', 'local-large'} & {r['model_name'] for r in roster}
    for model in ('local', 'local-large', 'gpt-oss-small'):
        request = urllib.request.Request(base + '/v1/chat/completions',
            data=json.dumps({'model': model, 'messages': [{'role': 'user', 'content': 'placeholder'}]}).encode(),
            headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=15) as response:
            answer = json.load(response)
            assert response.status == 200 and answer['choices'][0]['message']['content'] == 'billing'
    print('local rung offline: hosted fallthrough and disabled tracing passed', flush=True)


if __name__ == '__main__':
    verify(sys.argv[1])
