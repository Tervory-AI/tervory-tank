"""J2: real local HTTPS through the unchanged locked proxy; no external network."""
from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import sys
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
TENANT = '11111111-1111-4111-8111-111111111111'
OTHER = '22222222-2222-4222-8222-222222222222'
FILE = 'placeholderFigmaFileKey01'
TOKEN = 'placeholder-figma-token'
FAILED = 'Figma request failed'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
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
                    # The bounded proxy/reader must refuse this oversized stream.
                    for _ in range(90):
                        self.wfile.write(b' ' * 64_000)
                else:
                    self.wfile.write(body)
            except (OSError, ssl.SSLError):
                pass

    api = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_2
    tls.load_cert_chain(cert, key)
    api.socket = tls.wrap_socket(api.socket, server_side=True)
    thread = threading.Thread(target=api.serve_forever, daemon=True)
    thread.start()

    def connect(address, port):
        state.connects.append((address, port))
        assert address == '93.184.216.34' and port == 443
        return socket.create_connection(('127.0.0.1', api.server_port), timeout=1)

    proxy = egress.Proxy(verified_host='api.figma.com', allow_storage=False, require_sni=True, max_response_bytes=5_000_000,
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
    result = await live.reader.execute({'file_key': FILE, 'node_id': '0:1'}, TENANT, data_root=live.root, live=True)
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
        await live.reader.execute({'file_key': file}, tenant, data_root=live.root, live=True)
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
    result = await live.reader.execute({'file_key': FILE}, TENANT, data_root=live.root, live=True)
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
        await live.reader.execute({'file_key': FILE}, TENANT, data_root=live.root, live=True)
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
        await reader.execute({'file_key': FILE}, TENANT, data_root=tmp_path, live=True)
    monkeypatch.setenv('TISAN_FIGMA_FILES', f'{TENANT}={FILE}')
    with pytest.raises(reader.FigmaError, match=f'^{FAILED}$'):
        await reader.execute({'file_key': FILE}, TENANT, data_root=tmp_path, live=True)


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
@pytest.mark.parametrize('version,total', [('1.0.0', 3), ('1.0.1', 6), ('1.1.0', 7)])
async def test_real_skala_eval_calls_room_endpoint_with_platform_tenant(tmp_path, monkeypatch, version, total):
    import ast
    import os
    from uuid import UUID
    import skala
    from fastapi.testclient import TestClient

    platform = UUID('00000000-0000-0000-0000-000000000001')
    monkeypatch.setenv('AGENT_NAME', 'tisan')
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    monkeypatch.setenv('TANK_KEY_TISAN', 'placeholder-room-key')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('FIGMA_TOKEN', TOKEN)
    monkeypatch.setenv('TISAN_FIGMA_FILES', f'{OTHER}={FILE}')
    room = load(ROOT / 'agents/tisan/app.py', 'placeholder_eval_room')
    reader = room._load_beside(room._figma_cache(), 'tisan_figma', 'figma.py')
    async def forbidden(*args, **kwargs):
        pytest.fail('fixture/refusal eval contacted Figma')
    monkeypatch.setattr(reader, '_read_live', forbidden)
    client = TestClient(room.app)  # Routes only: no DB/worker lifespan is started.

    class Bridge:
        async def post(self, url, *, headers, json, timeout, follow_redirects):
            assert url == 'http://agent-tisan:8000/evals/run'
            assert json['tenant_id'] == str(platform)
            assert json['version'] == version
            assert timeout == 660 and follow_redirects is False
            return client.post('/evals/run', headers=headers, json=json)

    # Execute Tank's actual run_room_eval definition without importing unrelated
    # model/runtime initialization. It posts into the real room via TestClient.
    tree = ast.parse((ROOT / 'tank/main.py').read_text())
    function = next(node for node in tree.body if isinstance(node, ast.AsyncFunctionDef) and node.name == 'run_room_eval')
    namespace = {'os': os, '_http': Bridge()}
    prefix = ast.parse('from __future__ import annotations').body
    exec(compile(ast.Module(body=prefix + [function], type_ignores=[]), str(ROOT / 'tank/main.py'), 'exec'), namespace)
    import shutil
    packages = tmp_path / 'tisan.figma'
    shutil.copytree(SKILL.parent.resolve(), packages)
    package_path = packages / version
    package = skala._parse_package(package_path / 'skill.yaml', package_path)
    result = await skala.run_evals(package, lambda: SimpleNamespace(tenant_id=platform, cost_usd=0, calls=0),
                                   execute=namespace['run_room_eval'])
    assert result['passed'] == result['total'] == total, result['details']
    assert result['score'] == 1.0 and result['cost_usd'] == 0
    if version != '1.0.0':
        assert result['eligible'] is True
    if version == '1.1.0':
        assert package.cases[:6] == skala._parse_package(packages / '1.0.1/skill.yaml', packages / '1.0.1').cases
    assert client.post('/evals/run', json={'skill_id': 'tisan.figma', 'version': version,
        'tenant_id': str(platform), 'input': {}}).status_code == 401
    assert list((tmp_path / 'readings' / str(platform)).rglob('*.json'))
    client.close()


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
        await live.reader.execute({'file_key': FILE}, TENANT, data_root=live.root, live=True)
    assert len(live.requests) == 2 and not live.root.exists()


@pytest.mark.asyncio
async def test_token_without_pairing_keeps_tervory_recording(tmp_path, monkeypatch):
    reader = load(ROOT / 'agents/tisan/figma.py', 'placeholder_fallback_reader')
    monkeypatch.setenv('FIGMA_TOKEN', TOKEN)
    monkeypatch.setenv('TISAN_FIGMA_FILES', f'{OTHER}={FILE}')
    async def forbidden(*args, **kwargs):
        pytest.fail('unpaired Tervory fixture contacted Figma')
    monkeypatch.setattr(reader, '_read_live', forbidden)
    assert (await reader.execute({}, TENANT, data_root=tmp_path, live=True))['source'] == 'fixture'


@pytest.mark.asyncio
async def test_approved_old_version_and_unversioned_jobs_cannot_opt_into_live(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv('AGENT_NAME', 'tisan')
    monkeypatch.setenv('DATA_DIR', str(tmp_path))
    monkeypatch.setenv('TANK_KEY', 'placeholder-room-key')
    monkeypatch.setenv('FIGMA_TOKEN', TOKEN)
    room = load(ROOT / 'agents/tisan/app.py', 'placeholder_job_room')
    reader = room._load_beside(room._figma_cache(), 'tisan_figma', 'figma.py')
    monkeypatch.setenv('TISAN_FIGMA_FILES', f'{TENANT}={reader.TERVORY_FILE_KEY},{TENANT}={FILE}')
    async def forbidden(*args, **kwargs):
        pytest.fail('old/unversioned execution contacted Figma')
    monkeypatch.setattr(reader, '_read_live', forbidden)
    payload = {'file_key': reader.TERVORY_FILE_KEY, 'live': True, 'version': '1.1.0', 'approved_version': '1.1.0'}
    client = TestClient(room.app)
    response = client.post('/evals/run', headers={'X-Tank-Key': 'placeholder-room-key'},
        json={'skill_id': 'tisan.figma', 'version': '1.0.1', 'tenant_id': TENANT, 'input': payload})
    assert response.status_code == 200 and response.json()['source'] == 'fixture'
    assert (await room.figma(SimpleNamespace(input=payload, tenant_id=TENANT)))['source'] == 'fixture'
    with pytest.raises(reader.FigmaError):
        await room.figma(SimpleNamespace(input={**payload, 'file_key': FILE}, tenant_id=TENANT))
    old_skill = load(SKILL.parent / '1.0.1/run.py', 'placeholder_old_skill')
    monkeypatch.setattr(old_skill, '_load', lambda: reader)
    assert (await old_skill.run(payload, SimpleNamespace(tenant_id=TENANT)))['source'] == 'fixture'
    with pytest.raises(reader.FigmaError):
        await old_skill.run({'file_key': FILE}, SimpleNamespace(tenant_id=TENANT))
    client.close()


@pytest.mark.asyncio
async def test_can_read_a_response_above_the_old_one_megabyte_tunnel_limit(live):
    live.nodes['name'] = 'placeholder' + 'p' * 1_100_000
    result = await live.reader.execute({'file_key': FILE}, TENANT, data_root=live.root, live=True)
    assert result['tokens'] == live.reader.compile_reading(live.reader.load_fixture('0:1'))['tokens']
    assert len(live.requests) == 2


def test_canvas_identity_is_the_requested_node():
    reader = load(ROOT / 'agents/tisan/figma.py', 'placeholder_canvas_reader')
    recorded = json.loads((SKILL / 'evals/recorded-rest.json').read_text())
    nodes = {'nodes': {'7:1': recorded['nodes']['nodes']['0:1']}}
    result = reader.compile_reading(reader.normalise_rest(FILE, '7:1', nodes, recorded['variables']))
    assert result['page']['id'] == result['node']['id'] == '7:1'


@pytest.mark.asyncio
async def test_reading_file_symlink_cannot_write_outside_its_folder(tmp_path):
    reader = load(ROOT / 'agents/tisan/figma.py', 'placeholder_path_reader')
    source = reader.compile_reading(reader.load_fixture('0:1'))
    folder = tmp_path / 'readings' / TENANT / source['file_key']
    folder.mkdir(parents=True)
    outside = tmp_path / 'placeholder-outside.json'
    outside.write_text('placeholder original')
    (folder / '0-1.json').symlink_to(outside)
    with pytest.raises(reader.FigmaError):
        reader._store(source, TENANT, tmp_path)
    assert outside.read_text() == 'placeholder original'
