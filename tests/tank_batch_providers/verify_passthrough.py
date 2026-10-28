"""Execute the pinned LiteLLM route/credential selector with offline dependencies.

No upstream import, environment credential read, or network request is made.
"""
import ast
import asyncio
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import httpx

root = Path(sys.argv[1])
assert subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip() == 'ea7ca16dbc3904d9e59a9505f379a2ca3091821f'


def load_function(relative, name, namespace):
    tree = ast.parse((root / relative).read_text())
    function = next(node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name)
    function.decorator_list = []
    # Depends(user_api_key_auth) is a FastAPI dependency; the offline call supplies
    # the already-authenticated caller explicitly, without importing the proxy.
    function.args.defaults = [ast.Constant(None) for _ in function.args.defaults]
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), function], type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), relative, 'exec'), namespace)
    return namespace[name]


lookups = []


def secret_by_name(name):
    lookups.append(name)
    assert name == 'ANTHROPIC_API_KEY'
    return 'offline-credential-placeholder'


router_file = 'litellm/proxy/pass_through_endpoints/passthrough_endpoint_router.py'
namespace = {'verbose_router_logger': SimpleNamespace(debug=lambda *_: None),
             '_resolve_oidc_reference': lambda value: value, 'get_secret_str': secret_by_name}
get_default_name = load_function(router_file, '_get_default_env_variable_name_passthrough_endpoint', namespace)
get_credentials = load_function(router_file, 'get_credentials', namespace)
selector = SimpleNamespace(_get_deployment_api_key=lambda **_: None,
                           _get_default_env_variable_name_passthrough_endpoint=get_default_name)


async def auth_header(value, **kwargs):
    assert value == 'offline-credential-placeholder'
    assert kwargs == {'allow_workload_identity': True}
    return {'x-api-key': value}


seen = []


def create_route(**kwargs):
    assert kwargs['custom_headers'] == {'x-api-key': 'offline-credential-placeholder'}

    async def forward(request, response, caller):
        seen.append((request.method, kwargs['target']))
        return {'forwarded': True}
    return forward


async def streaming(_):
    return False


namespace = {
    'os': SimpleNamespace(getenv=lambda _: None), 'httpx': httpx,
    'HttpPassThroughEndpointHelpers': SimpleNamespace(join_base_and_endpoint_path=lambda base, endpoint: endpoint),
    'passthrough_endpoint_router': SimpleNamespace(get_credentials=lambda **kw: get_credentials(selector, **kw)),
    'is_streaming_request_fn': streaming, 'AnthropicModelInfo': SimpleNamespace(aget_auth_header=auth_header),
    'create_pass_through_route': create_route,
    '_upstream_headers_for_anthropic_route': lambda request, caller, auth: auth,
}
route = load_function('litellm/proxy/pass_through_endpoints/llm_passthrough_endpoints.py', 'anthropic_proxy_route', namespace)


async def check():
    for method, endpoint in [('POST', 'v1/messages/batches'),
                             ('GET', 'v1/messages/batches/msgbatch_offline'),
                             ('GET', 'v1/messages/batches/msgbatch_offline/results'),
                             ('POST', 'v1/messages/batches/msgbatch_offline/cancel')]:
        assert await route(endpoint, SimpleNamespace(method=method), None, object()) == {'forwarded': True}
        assert seen[-1] == (method, 'https://api.anthropic.com/' + endpoint)
        print(f'PASS pinned LiteLLM pass-through: {method} /anthropic/{endpoint}')
    assert lookups == ['ANTHROPIC_API_KEY'] * 4
    print('PASS existing credential selected inside LiteLLM by name; no real values read')


asyncio.run(check())
