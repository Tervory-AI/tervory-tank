"""J2: real local HTTPS through the unchanged locked proxy; no external network."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import socket
import ssl
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'tank/skills/tisan.figma/1.1.0'
TENANT = 'placeholder-tenant'
OTHER = 'placeholder-other-tenant'
FILE = 'placeholderFigmaFileKey01'
TOKEN = 'placeholder-figma-token'
FAILED = 'Figma request failed'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def live(tmp_path, monkeypatch):
    reader = load(ROOT / 'agents/tisan/figma.py', 'placeholder_reader')
    egress = load(ROOT / 'agents/radix/egress.py', 'placeholder_egress')
    recorded = json.loads((SKILL / 'evals/recorded-rest.json').read_text())
    state = SimpleNamespace(reader=reader, nodes=recorded['nodes'], variables=recorded['variables'],
                            requests=[], connects=[], mode='ok', variables_status=200)
    # Ephemeral test-only TLS material, never a service credential or repository asset.
    cert, key = tmp_path / 'placeholder-cert.pem', tmp_path / 'placeholder-key.pem'
    subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                    '-keyout', str(key), '-out', str(cert), '-days', '1',
                    '-subj', '/CN=api.figma.com', '-addext', 'subjectAltName=DNS:api.figma.com'],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            state.requests.append(self.path)
            assert self.headers['X-Figma-Token'] == TOKEN
            variables = self.path.endswith('/variables/local')
            status = state.variables_status if variables else 200
            if state.mode == 'timeout':
                threading.Event().wait(0.15)
            if state.mode in {'500', '401', '403', '404', '429', '302'}:
                status = int(state.mode)
            body = json.dumps(state.variables if variables else state.nodes).encode()
            if state.mode == 'echo':
                # Unicode-escaped credential echo must also be refused.
                body = json.dumps({'name': TOKEN}, ensure_ascii=True).replace('p', '\\u0070').encode()
            if state.mode == 'malformed':
                body = b'placeholder-invalid-json'
            self.send_response(status)
            if state.mode == '302':
                self.send_header('Location', 'https://placeholder-other.invalid/')
            if state.mode != 'oversized-stream':
                self.send_header('Content-Length', str(5_000_001 if state.mode == 'oversized-header' else len(body)))
            self.send_header('Connection', 'close')
            self.end_headers()
            try:
                if state.mode == 'oversized-stream':
                    # The smaller unchanged proxy limit will cut this stream first.
                    for _ in range(90):
                        self.wfile.write(b' ' * 64_000)
                else:
                    self.wfile.write(body)
            except (OSError, ssl.SSLError):
                pass

    api = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert, key)
    api.socket = tls.wrap_socket(api.socket, server_side=True)
    thread = threading.Thread(target=api.serve_forever, daemon=True)
    thread.start()

    def connect(address, port):
        state.connects.append((address, port))
        assert address == '93.184.216.34' and port == 443
        return socket.create_connection(('127.0.0.1', api.server_port), timeout=1)

    proxy = egress.Proxy(verified_host='api.figma.com', allow_storage=False, require_sni=True,
                         resolve=lambda host: '93.184.216.34', connect=connect)
    server = egress.Server(proxy).start()
    state.proxy_url = f'http://127.0.0.1:{server.port}'
    state.original_client = httpx.AsyncClient
    trust = ssl.create_default_context(cafile=str(cert))

    def client(**kwargs):
        assert kwargs['proxy'] == 'http://figma-egress-proxy:8080'
        assert kwargs['trust_env'] is False
        assert kwargs['follow_redirects'] is False
        assert kwargs['timeout'] == reader._REQUEST_SECONDS
        assert kwargs['headers'] == {'X-Figma-Token': TOKEN}
        return state.original_client(**{**kwargs, 'proxy': state.proxy_url, 'verify': trust})

    monkeypatch.setattr(reader.httpx, 'AsyncClient', client)
    monkeypatch.setenv('FIGMA_TOKEN', TOKEN)
    monkeypatch.setenv('TISAN_FIGMA_FILES', f'{OTHER}=placeholderOtherFileKey01, {TENANT}={FILE}')
    # Poison ambient routing. The explicit client must never consult it.
    monkeypatch.setenv('HTTPS_PROXY', 'http://placeholder-outside.invalid:1')
    monkeypatch.setenv('NO_PROXY', '*')
    state.root = tmp_path / 'data'
    try:
        yield state
    finally:
        server.close()
        api.shutdown()
        api.server_close()
        thread.join(timeout=2)


@pytest.mark.asyncio
async def test_paired_live_page_uses_two_proxy_requests_and_recorded_tokens(live, caplog):
    caplog.set_level(logging.DEBUG)
    result = await live.reader.execute({'file_key': FILE, 'node_id': '0:1'}, TENANT, data_root=live.root)
    expected = live.reader.compile_reading(live.reader.load_fixture('0:1'))
    assert result['tokens'] == expected['tokens']
    assert result['source'] == 'figma'
    assert live.requests == [f'/v1/files/{FILE}/nodes?ids=0:1', f'/v1/files/{FILE}/variables/local']
    assert live.connects and all(port == 443 for _, port in live.connects)
    saved = (live.root / result['stored']).read_text()
    assert TOKEN not in saved and TOKEN not in json.dumps(result) and TOKEN not in caplog.text
    assert 'X-Figma-Token' not in saved


@pytest.mark.asyncio
@pytest.mark.parametrize('tenant,file', [(OTHER, FILE), (TENANT, 'placeholderUnpairedFile01')])
async def test_unpaired_file_refused_before_client_or_request(live, tenant, file, monkeypatch):
    def forbidden(**kwargs):
        pytest.fail('unpaired read created an HTTP client')
    monkeypatch.setattr(live.reader.httpx, 'AsyncClient', forbidden)
    with pytest.raises(live.reader.FigmaError, match='^Figma file is not paired with this tenant$'):
        await live.reader.execute({'file_key': file}, tenant, data_root=live.root)
    assert live.requests == [] and live.connects == [] and not live.root.exists()


@pytest.mark.asyncio
async def test_proxy_refuses_other_host_without_upstream_connect(live):
    async with live.original_client(proxy=live.proxy_url, trust_env=False) as client:
        with pytest.raises(httpx.ProxyError):
            await client.get('https://placeholder-other.invalid/')
    assert live.connects == [] and live.requests == []


@pytest.mark.asyncio
async def test_variables_403_preserves_unknown_collections_and_no_values(live):
    live.variables_status = 403
    result = await live.reader.execute({'file_key': FILE}, TENANT, data_root=live.root)
    assert len(live.requests) == 2
    assert result['collections_known'] is False
    assert all(not values for values in result['tokens'].values())
    assert any(gap['kind'] == 'variables_unavailable' for gap in result['gaps'])


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['timeout', '500', '401', '403', '404', '429', '302',
                                  'oversized-header', 'oversized-stream', 'malformed', 'echo'])
async def test_fixed_errors_never_store_or_log_tokens(live, mode, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    live.mode = mode
    if mode == 'timeout':
        monkeypatch.setattr(live.reader, '_REQUEST_SECONDS', 0.02)
    with pytest.raises(live.reader.FigmaError) as raised:
        await live.reader.execute({'file_key': FILE}, TENANT, data_root=live.root)
    assert str(raised.value) == FAILED
    assert raised.value.__suppress_context__ is True
    assert TOKEN not in caplog.text and TOKEN not in str(raised.value)
    assert not live.root.exists() and len(live.requests) <= 1


@pytest.mark.asyncio
async def test_no_token_reads_recording_without_an_http_client(tmp_path, monkeypatch):
    reader = load(ROOT / 'agents/tisan/figma.py', 'placeholder_offline_reader')
    monkeypatch.delenv('FIGMA_TOKEN', raising=False)
    monkeypatch.delenv('TISAN_FIGMA_FILES', raising=False)
    def forbidden(**kwargs):
        pytest.fail('offline fixture created an HTTP client')
    monkeypatch.setattr(reader.httpx, 'AsyncClient', forbidden)
    result = await reader.execute({}, TENANT, data_root=tmp_path)
    assert result['source'] == 'fixture'
    with pytest.raises(reader.FigmaError, match='not paired'):
        await reader.execute({'file_key': FILE}, TENANT, data_root=tmp_path)
    monkeypatch.setenv('TISAN_FIGMA_FILES', f'{TENANT}={FILE}')
    with pytest.raises(reader.FigmaError, match=f'^{FAILED}$'):
        await reader.execute({'file_key': FILE}, TENANT, data_root=tmp_path)


@pytest.mark.asyncio
async def test_deadline_bounds_a_slow_drip_response_and_decoded_body_limit(monkeypatch):
    reader = load(ROOT / 'agents/tisan/figma.py', 'placeholder_limit_reader')
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(10):
                await asyncio.sleep(0.01)
                yield b' ' * 64_000
    async def handler(request):
        return httpx.Response(200, stream=Body())
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        monkeypatch.setattr(reader, '_REQUEST_SECONDS', 0.03)
        with pytest.raises(reader.FigmaError, match=f'^{FAILED}$'):
            await reader._get_rest(client, 'files/placeholder/nodes', TOKEN)
        monkeypatch.setattr(reader, '_REQUEST_SECONDS', 20)
        monkeypatch.setattr(reader, '_MAX_RESPONSE_BYTES', 64_001)
        with pytest.raises(reader.FigmaError, match=f'^{FAILED}$'):
            await reader._get_rest(client, 'files/placeholder/nodes', TOKEN)


def test_deploy_routing_and_all_proxy_copy_sources_resolve():
    import ast
    script = ROOT / '.github/scripts/deploy_changed.py'
    tree = ast.parse(script.read_text())
    wanted = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'wanted')
    namespace = {'MAIN_PREFIXES': (), 'ALL_ROOMS_PREFIXES': ()}
    exec(compile(ast.Module(body=[wanted], type_ignores=[]), str(script), 'exec'), namespace)
    assert namespace['wanted'](['agents/tisan/docker-compose.yml']) == (False, {'agent-tisan'}, False)
    setup = (ROOT / '.github/scripts/room_setup.py').read_text()
    assert '"base_directory": f"/agents/{ROOM}"' in setup
    assert '"docker_compose_location": "/docker-compose.yml"' in setup
    import shlex
    for line in (ROOT / 'agents/radix/Dockerfile').read_text().splitlines():
        if not line.startswith('COPY ') or '--from=' in line:
            continue
        for source in shlex.split(line)[1:-1]:
            assert list((ROOT / 'agents').glob(source)), source


@pytest.mark.asyncio
async def test_new_skill_nine_evals_are_eligible_and_free_offline(live, monkeypatch):
    from skala import _parse_package, run_evals
    skill = load(SKILL / 'run.py', 'placeholder_skill')
    monkeypatch.setattr(skill, '_load', lambda: live.reader)
    monkeypatch.setenv('DATA_DIR', str(live.root))
    package = _parse_package(SKILL / 'skill.yaml', SKILL)
    cases = iter(package.cases)

    async def execute(_package, payload, ctx):
        case = next(cases)
        if case.get('recorded_rest'):
            assert case['recorded_rest'] == 'recorded-rest.json'
            monkeypatch.setenv('FIGMA_TOKEN', TOKEN)
        else:
            monkeypatch.delenv('FIGMA_TOKEN', raising=False)
        live.variables_status = case.get('variables_status', 200)
        ctx.tenant_id = payload.get('tenant_id', TENANT)
        return await skill.run(payload, ctx)

    result = await run_evals(package, lambda: SimpleNamespace(tenant_id=TENANT, cost_usd=0, calls=0),
                             execute=execute)
    assert result['passed'] == result['total'] == 9, result['details']
    assert result['eligible'] is True and result['score'] == 1.0
    assert result['cost_usd'] == 0 and all(not row['used_model'] for row in result['details'])
    assert len(live.requests) == 4  # two live successes, zero requests for the tenant refusal


@pytest.mark.asyncio
async def test_skill_context_identity_overrides_payload_tenant(live, monkeypatch):
    skill = load(SKILL / 'run.py', 'placeholder_identity_skill')
    monkeypatch.setattr(skill, '_load', lambda: live.reader)
    payload = {'file_key': FILE, 'tenant_id': TENANT}
    with pytest.raises(live.reader.FigmaError, match='not paired'):
        await skill.run(payload, SimpleNamespace(tenant_id=OTHER))
    with pytest.raises(RuntimeError, match='tenant_id is required'):
        await skill.run(payload, SimpleNamespace())
    assert live.requests == [] and live.connects == []


@pytest.mark.asyncio
@pytest.mark.parametrize('status', [401, 500])
async def test_other_variables_errors_are_fixed_failures_without_a_reading(live, status):
    live.variables_status = status
    with pytest.raises(live.reader.FigmaError, match=f'^{FAILED}$'):
        await live.reader.execute({'file_key': FILE}, TENANT, data_root=live.root)
    assert len(live.requests) == 2 and not live.root.exists()
