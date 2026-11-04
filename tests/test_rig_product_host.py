"""Shared host: preserve existing store URLs through the actual Traefik rules."""
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'agents/rig'))
from rigbox.quotes.keys import embed_snippet  # noqa: E402
from rigbox.quotes.hosting import manifest  # noqa: E402


def labels():
    compose = yaml.safe_load((ROOT / 'agents/rig/docker-compose.yml').read_text())
    return dict(row.split('=', 1) for row in compose['services']['agent-rig']['labels'])


def test_routing_rules_preserve_bounded_namespaces_and_priority():
    value = labels()
    rule = value['traefik.http.routers.rig-https.rule']
    assert rule == value['traefik.http.routers.rig-http.rule']
    assert rule.startswith('Host(`rig.tervory.com`) && (') and rule.endswith(')')
    # Compare the complete matcher vocabulary so an added catch-all cannot slip in.
    assert re.findall(r'(Host|Path|PathPrefix)\(`([^`]+)`\)', rule) == [
        ('Host', 'rig.tervory.com'),
        *[(kind, path) for name in ('v1/rig', 'widget', '3d', 'page', 'product', 'v5')
          for kind, path in [('Path', '/' + name), ('PathPrefix', '/' + name + '/')]],
        ('Path', '/cn-classic'), ('Path', '/house'), ('Path', '/health'),
        ('Path', '/storage'), ('PathPrefix', '/storage/'),
    ]
    for name in ('rig-http', 'rig-https'):
        assert value[f'traefik.http.routers.{name}.priority'] == '1000'
    assert value['traefik.http.routers.rig-https.service'] == 'rig'
    assert value['traefik.http.services.rig.loadbalancer.server.port'] == '8000'
    assert not any('stripprefix' in key.lower() or 'replacepath' in key.lower() for key in value)


def test_workspace_middleware_preserves_rig_authentication_and_query_strings():
    result = subprocess.run(['node', 'tests/rig_host_routing/middleware.cjs'], cwd=ROOT,
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr


def agent_paths():
    """Inventory the production image entry point without starting its lifespan."""
    code = '''from rigbox.three_d.asgi import app
from http_routes import http_paths
import json
print(json.dumps(sorted(http_paths(app.routes))))'''
    result = subprocess.run([sys.executable, '-c', code], cwd=ROOT, capture_output=True,
                            text=True, timeout=30,
                            env={**os.environ, 'PYTHONPATH': 'tank:tests:agents/_chassis:agents/rig'})
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@contextmanager
def backend(name):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            raw = self.rfile.read(int(self.headers.get('content-length', 0)))
            data = json.dumps({'backend': name, 'path': self.path, 'method': self.command,
                               'host': self.headers['host'], 'origin': self.headers.get('origin'),
                               'key': self.headers.get('x-rig-key'),
                               'shopify_signature': self.headers.get('x-shopify-hmac-sha256'),
                               'woo_signature': self.headers.get('x-wc-webhook-signature'),
                               'body': raw.decode()}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        do_POST = do_OPTIONS = do_GET

        def log_message(self, *_):
            pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@pytest.mark.skipif(not os.environ.get('RIG_TRAEFIK_TEST_BINARY'),
                    reason='Explicit offline Traefik binary routing proof')
def test_real_traefik_keeps_embed_store_urls_and_sends_app_paths_to_workspace(tmp_path):
    value = labels()
    http_port, https_port = free_port(), free_port()
    with backend('agent-rig') as agent, backend('workspace') as workspace:
        routers = {}
        for name in ('rig-http', 'rig-https'):
            prefix = 'traefik.http.routers.' + name
            routers[name] = {'rule': value[prefix + '.rule'], 'priority': int(value[prefix + '.priority']),
                             'entryPoints': [value[prefix + '.entrypoints']], 'service': 'rig',
                             'middlewares': value[prefix + '.middlewares'].split(',')}
            if name == 'rig-https':
                routers[name]['tls'] = {}  # Local default cert; no ACME or external network.
        for scheme in ('http', 'https'):
            routers['workspace-' + scheme] = {
                'rule': 'Host(`rig.tervory.com`)', 'priority': 100,
                'entryPoints': [scheme], 'service': 'workspace',
                **({'tls': {}} if scheme == 'https' else {'middlewares': ['redirect-to-https']})}
        config = {'http': {'routers': routers, 'middlewares': {
            'rig-gzip': {'compress': {}},
            'redirect-to-https': {'redirectScheme': {'scheme': 'https', 'port': str(https_port), 'permanent': True}}},
            'services': {name: {'loadBalancer': {'servers': [{'url': url}]}}
                         for name, url in [('rig', agent), ('workspace', workspace)]}}}
        config_path = tmp_path / 'routing.yml'
        config_path.write_text(yaml.safe_dump(config))
        with (tmp_path / 'traefik.log').open('w+') as log:
            process = subprocess.Popen([
                os.environ['RIG_TRAEFIK_TEST_BINARY'], '--providers.file.filename=' + str(config_path),
                f'--entrypoints.http.address=127.0.0.1:{http_port}',
                f'--entrypoints.https.address=127.0.0.1:{https_port}', '--log.level=ERROR',
                '--global.checknewversion=false', '--global.sendanonymoususage=false'], stdout=log, stderr=log)
            try:
                with httpx.Client(verify=False, trust_env=False, timeout=5,
                                  headers={'Host': 'rig.tervory.com'}) as client:
                    secure = f'https://127.0.0.1:{https_port}'
                    for _ in range(150):
                        assert process.poll() is None, (tmp_path / 'traefik.log').read_text()
                        try:
                            if client.get(secure + '/health').status_code == 200:
                                break
                        except httpx.TransportError:
                            pass
                        time.sleep(.05)
                    else:
                        pytest.fail('Local Traefik did not start')
                    snippet = embed_snippet('rk_pub_offline_fixture')
                    script = re.search(r'src="([^"]+)"', snippet)[1]
                    assert urlsplit(script).hostname == 'rig.tervory.com'
                    assert 'api-base="https://rig.tervory.com"' in snippet
                    paths = {urlsplit(script).path, '/widget/manifest.json', '/widget/test',
                             '/widget/fonts/custom-nation.css', '/widget/fonts/barlow-condensed-latin-600-normal.woff2',
                             '/page/search.js', '/page/admin.js'}
                    viewer = ROOT / 'agents/rig/rigbox/three_d/widget'
                    paths.update('/3d/' + path.relative_to(viewer).as_posix()
                                 for path in viewer.rglob('*') if path.is_file())
                    # All existing versioned APIs, including callbacks and preflight, plus
                    # public legacy pages/assets and approved models stay on their backend.
                    for path in agent_paths():
                        if path.startswith(('/v1/rig', '/widget/', '/3d', '/page/', '/product/', '/storage/')) or path in ('/health', '/cn-classic', '/house', '/v5', '/v5/cn'):
                            paths.add(re.sub(r'\{[^}]+\}', '11111111-1111-4111-8111-111111111111', path))
                    bundle = (ROOT / 'agents/rig/rigbox/quotes/widget' / manifest()['file']).read_text()
                    paths.update(re.findall(r'/v1/rig/[A-Za-z0-9_/-]+', bundle))
                    (tmp_path / 'covered-paths.json').write_text(json.dumps(sorted(paths), indent=2))
                    for path in sorted(paths):
                        response = client.get(secure + path + '?source=embed&quantity=2')
                        assert response.status_code == 200, (path, response.text)
                        body = response.json()
                        assert body['backend'] == 'agent-rig', path
                        assert body['path'] == path + '?source=embed&quantity=2'
                    for method in ('POST', 'OPTIONS'):
                        response = client.request(method, secure + '/v1/rig/commerce/webhooks/fixture',
                                                  content=b'{"id":1}', headers={
                                                      'Origin': 'https://store.example.invalid',
                                                      'X-Rig-Key': 'rk_pub_offline_fixture',
                                                      'X-Shopify-Hmac-Sha256': 'offline-signature',
                                                      'X-WC-Webhook-Signature': 'offline-woo-signature'})
                        body = response.json()
                        assert body == {'backend': 'agent-rig', 'path': '/v1/rig/commerce/webhooks/fixture',
                                        'host': 'rig.tervory.com', 'origin': 'https://store.example.invalid',
                                        'key': 'rk_pub_offline_fixture', 'method': method, 'body': '{"id":1}',
                                        'shopify_signature': 'offline-signature',
                                        'woo_signature': 'offline-woo-signature'}
                    for path in ('/', '/admin', '/admin/three-d', '/rig', '/rig/admin', '/rig/admin/api',
                                 '/rig/admin/three-d', '/sign-in', '/sign-up', '/api/health',
                                 '/_next/static/chunk.js', '/rig-cart/select-chevron.svg',
                                 '/v1/command', '/v1/rig-extra', '/widget-extra', '/3d-extra', '/page-extra', '/health-extra'):
                        body = client.get(secure + path).json()
                        assert body['backend'] == 'workspace' and body['host'] == 'rig.tervory.com', path
                    for path in ('/', '/admin?cart=orders', urlsplit(script).path,
                                 '/widget/test', '/v1/rig/search?q=part'):
                        response = client.get(f'http://127.0.0.1:{http_port}' + path)
                        assert response.status_code in (301, 308)
                        assert response.headers['location'] == f'https://rig.tervory.com:{https_port}' + path
            finally:
                process.terminate()
                process.wait(timeout=10)
