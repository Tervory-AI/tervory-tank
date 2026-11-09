"""Only external responses are fake; room, brain and Tank dispatch are real ASGI."""
import json

import httpx
from tank_routing.litellm_probe import COMPLETIONS_PATH


async def room_edge(request, runtime, product_transport, native_transport, stack, harness, FIXTURE_COST, FIXTURE_INPUT, FIXTURE_OUTPUT):
    if harness is not None:
        harness.events.append((request.url.host, request.url.path))
    if request.url.host == 'agent-tisan':
        response = await product_transport.handle_async_request(request)
        await response.aread()
        if harness is not None:
            harness.events.append((request.method, request.url.path, response.status_code,
                response.json().get('detail') if response.status_code >= 400 else None,
                bool(request.headers.get('x-tervory-admin'))))
        return response
    if request.url.host == 'tisan-brain':
        assert request.method == 'POST' and request.url.path == '/tasks/plan' and request.url.port == 8001
        response = await httpx.ASGITransport(app=runtime.brain_service.app).handle_async_request(request)
        await response.aread()
        return response
    if request.url.host == 'placeholder-tank':
        response = await native_transport.handle_async_request(request)
        await response.aread()
        if harness is not None:
            harness.events.append((request.url.path, response.status_code,
                response.json() if response.status_code >= 400 else None))
        return response
    if request.url.host == 'hermes':
        outage = harness.transport_outage if harness is not None else None
        if outage == 'auth':
            return httpx.Response(403, json={'detail': 'placeholder scope refusal'})
        if ((outage == 'remember' and request.method == 'POST')
                or (outage in {'list', 'recall'} and request.method == 'GET')):
            return httpx.Response(503, json={'detail': 'placeholder memory unavailable'})
        return await stack.http.send(request)
    if request.method == 'GET' and request.url.path == '/router/settings':
        return httpx.Response(200, json={'current_values': {'fallbacks': []}})
    if request.method == 'GET' and request.url.path == '/model/info':
        from engine_models import OPEN
        return httpx.Response(200, json={'data': [{'model_name': model,
            'litellm_params': {'model': 'openai/placeholder-fixture'},
            'model_info': {'family': 'openai', 'input_cost_per_token': 0.000001,
                           'output_cost_per_token': 0.000003}} for model in (*OPEN, 'luna')]})
    if request.method == 'POST' and request.url.path == COMPLETIONS_PATH:
        plan = {'nav': [{'href': '/'}], 'ui': {}, 'pages': [{'name': 'home', 'path': '/',
            'sections': [{'id': 'placeholder-hero', 'type': 'hero', 'props': {}}]}]}
        call = {'cost': FIXTURE_COST, 'input': FIXTURE_INPUT, 'output': FIXTURE_OUTPUT}
        assert harness is not None
        harness.provider_calls.append(call)
        return httpx.Response(200, headers={'x-litellm-response-cost': str(FIXTURE_COST)}, json={
            'model': json.loads(request.content)['model'], 'choices': [{'message': {'role': 'assistant', 'content': json.dumps(plan)},
                                        'finish_reason': 'stop'}],
            'usage': {'prompt_tokens': FIXTURE_INPUT, 'completion_tokens': FIXTURE_OUTPUT}})
    raise AssertionError('Unexpected external service: ' + request.url.host + request.url.path)
