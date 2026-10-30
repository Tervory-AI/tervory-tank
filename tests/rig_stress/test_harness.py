"""Offline wiring only. Fake HTTP is loopback inside a network-none container."""
import asyncio
import json
import threading
import tempfile
from pathlib import Path
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import harness as h


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(500 if self.path.endswith('/fail') else 200)
        self.end_headers()
        self.wfile.write(b'{}')

    do_POST = do_GET

    def log_message(self, *args):
        pass


class Wiring(unittest.TestCase):
    def test_nearest_rank_and_empty(self):
        self.assertEqual(h.quantile(list(range(1, 101)), .95), 95)
        self.assertEqual(h.quantile([1, 2, 3, 4], .5), 2)
        self.assertIsNone(h.quantile([], .95))

    def test_all_exact_boundaries_fail(self):
        good = {'search_p95_s': .1, 'quote_p95_s': .2, 'memory_fraction': .5,
                'forge_queue_wait_s': 1, 'errors': 0, 'dropped': 0}
        self.assertEqual(h.failures(good), [])
        for key, boundary in h.LIMITS.items():
            self.assertIn(key, h.failures({**good, key: boundary}))
        self.assertIn('errors', h.failures({**good, 'errors': 1}))
        self.assertIn('dropped', h.failures({**good, 'dropped': 1}))
        self.assertEqual(len(h.failures({})), 6)

    def test_production_and_dns_rejected(self):
        for url in ['https://rig.tervory.com', 'http://agent-rig:8000',
                    'http://197.242.151.183:8000', 'http://127.0.0.1:8000',
                    'http://169.254.169.254:80', 'http://user:password@10.1.2.3:80',
                    'http://10.1.2.3:80/evil', 'http://10.1.2.3:80/#fragment']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                h.validate_url(url, [url])
        self.assertEqual(h.validate_url('http://10.1.2.3:8000', ['http://10.1.2.3:8000']), '10.1.2.3')
        with self.assertRaises(ValueError):
            h.validate_url('http://10.1.2.3:8000', [])

    def test_network_and_container_guards(self):
        config = {'network': 'rigstress-smoke', 'dedicated_spare_host': True,
                  'stores': [{'target': 'http://10.1.2.3:8000'}],
                  'target_allowlist': ['http://10.1.2.3:8000']}
        network = {'Internal': True, 'Labels': {h.LABEL: 'true'}, 'Containers': {'id': {}}}
        container = {'Config': {'Labels': {h.LABEL: 'true'}}, 'Mounts': [],
                     'HostConfig': {'NetworkMode': 'rigstress-smoke'},
                     'NetworkSettings': {'Networks': {'rigstress-smoke': {'IPAddress': '10.1.2.3'}}}}
        with patch.object(h, 'docker', side_effect=[[network], [container]]):
            h.preflight(config)
        for field, value in [('Internal', False), ('Labels', {}), ('Containers', {})]:
            with patch.object(h, 'docker', return_value=[{**network, field: value}]), self.assertRaises(ValueError):
                h.preflight(config)
        for mutate in [lambda c: c['HostConfig'].update(Privileged=True),
                       lambda c: c['HostConfig'].update(PortBindings={'8000/tcp': []}),
                       lambda c: c.update(Mounts=[{'Source': '/production'}]),
                       lambda c: c['Config'].update(Labels={}),
                       lambda c: c['NetworkSettings']['Networks'].update(coolify={})]:
            changed = json.loads(json.dumps(container))
            mutate(changed)
            with patch.object(h, 'docker', side_effect=[[network], [changed]]), self.assertRaises(ValueError):
                h.preflight(config)
        with self.assertRaises(ValueError):
            h.preflight({**config, 'network': 'coolify'})

    def test_spare_confirmation_requires_boolean_true(self):
        network = {'Internal': True, 'Labels': {h.LABEL: 'true'}, 'Containers': {'id': {}}}
        container = {'Config': {'Labels': {h.LABEL: 'true'}}, 'Mounts': [],
                     'HostConfig': {'NetworkMode': 'rigstress-smoke'},
                     'NetworkSettings': {'Networks': {'rigstress-smoke': {'IPAddress': '10.1.2.3'}}}}
        for value in (False, 'false', 'true', 0, 1, None):
            with self.subTest(value=value), patch.object(h, 'docker', side_effect=[[network], [container]]):
                with self.assertRaises(ValueError):
                    h.preflight({'network': 'rigstress-smoke', 'dedicated_spare_host': value})

    def test_config_binds_exact_operation_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'private-fixture').write_text('offline wiring only')
            operations = {'search': {'method': 'GET', 'path': '/v1/rig/search'},
                          'setup': {'method': 'POST', 'path': '/v1/rig/setups'},
                          'quote': {'method': 'POST', 'path': '/v1/rig/quote'}}
            config = {'rps_per_store': 1, 'concurrency_per_store': 1,
                      'catalogue_fixture': 'private-fixture', 'forge_fixture': 'private-fixture',
                      'target_allowlist': ['http://10.1.2.3:8000'],
                      'network': 'rigstress-smoke', 'dedicated_spare_host': True,
                      'stores': [{'target': 'http://10.1.2.3:8000', 'operations': operations}] * 30}
            path = root / 'config.json'
            path.write_text(json.dumps(config))
            self.assertEqual(len(h.load_config(path)['stores']), 30)
            for kind, method, route in (
                ('search', 'GET', '/v1/rig/../../v1/controls/workers-paused'),
                ('search', 'GET', '/v1/rig/%2e%2e/%2e%2e/v1/controls'),
                ('search', 'GET', '/v1/rig/search?path=/v1/controls'),
                ('search', 'GET', '/v1/rig/search#fragment'),
                ('search', 'GET', '/v1/rig//search'),
                ('search', 'POST', '/v1/rig/search'),
                ('quote', 'POST', '/v1/rig/setups'),
                ('setup', 'GET', '/v1/rig/setups'),
            ):
                changed = json.loads(json.dumps(config))
                changed['stores'][0]['operations'][kind] = {'method': method, 'path': route}
                path.write_text(json.dumps(changed))
                with self.subTest(route=route, method=method), self.assertRaises(ValueError):
                    h.load_config(path)

    def test_fake_http_errors_and_reports(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            origin = 'http://127.0.0.1:' + str(server.server_port)
            operations = {kind: {'method': 'GET', 'path': '/v1/rig/' + kind,
                                 'expected_statuses': [200]} for kind in ('search', 'setup', 'quote')}
            result = asyncio.run(h.traffic([{'target': origin, 'operations': operations}], 15, 1, .5))
            self.assertEqual(result['errors'], 0)
            self.assertTrue(all(result['latency'].values()))
            metrics = h.report(result, [{'memory_used_bytes': 10, 'memory_total_bytes': 100,
                                        'cpu_percent': 1, 'disk_io_bytes': 0,
                                        'per_container_memory_bytes': {'fixture': 10}}], [1, 2])
            self.assertEqual(metrics['failed_limits'], [])
            self.assertFalse(metrics['capacity_valid'])
            self.assertIn('memory_fraction', h.report(result, [], [])['failed_limits'])
            _, ok = h.request(origin, {'method': 'GET', 'path': '/fail', 'expected_statuses': [200]})
            self.assertFalse(ok)
            print('OFFLINE_WIRING_REPORT=' + json.dumps(metrics), flush=True)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        self.assertFalse(thread.is_alive())

    def test_overload_is_reported(self):
        async def execute():
            with patch.object(h, 'request', side_effect=lambda *_: (__import__('time').sleep(.05) or (.05, True))):
                operations = {name: {} for name in ('search', 'setup', 'quote')}
                return await h.traffic([{'target': 'unused', 'operations': operations}], 100, 1, .15)
        self.assertGreater(asyncio.run(execute())['dropped'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
