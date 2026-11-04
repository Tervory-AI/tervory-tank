"""Offline preflight and reporting: no socket, Docker, model or target access."""
import asyncio
import contextlib
import io
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

import harness as h


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
                    h.preflight({'network': 'rigstress-smoke', 'dedicated_spare_host': value,
                                 'stores': [{'target': 'http://10.1.2.3:8000'}],
                                 'target_allowlist': ['http://10.1.2.3:8000']})

    def test_config_binds_exact_operation_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'private-fixture').write_text('offline wiring only')
            operations = {'search': {'method': 'GET', 'path': '/v1/rig/search', 'expected_statuses': [200]},
                          'setup': {'method': 'POST', 'path': '/v1/rig/setups', 'expected_statuses': [200]},
                          'quote': {'method': 'POST', 'path': '/v1/rig/quote', 'expected_statuses': [200]}}
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
        operation = {'method': 'GET', 'path': '/v1/rig/search', 'expected_statuses': [200]}
        connection = MagicMock()
        response = connection.getresponse.return_value
        response.status = 200
        with patch.object(h.http.client, 'HTTPConnection', return_value=connection):
            _, ok = h.request('http://10.1.2.3:8000', operation)
            self.assertTrue(ok)
            connection.request.assert_called_once_with('GET', '/v1/rig/search', None,
                                                       {'Content-Type': 'application/json'})
            connection.close.assert_called_once()
            response.status = 500
            self.assertFalse(h.request('http://10.1.2.3:8000', operation)[1])
            response.status = 302
            self.assertFalse(h.request('http://10.1.2.3:8000', operation)[1])
            connection.getresponse.side_effect = OSError('placeholder-offline-error')
            self.assertFalse(h.request('http://10.1.2.3:8000', operation)[1])
        unit_input = {'latency': {'search': [.01], 'setup': [.02], 'quote': [.03]},
                      'errors': 0, 'dropped': 0}
        metrics = h.report(unit_input, [{'memory_used_bytes': 10, 'memory_total_bytes': 100}], [1, 2])
        self.assertEqual(metrics['failed_limits'], [])
        self.assertFalse(metrics['capacity_valid'])
        absent = h.report(unit_input, [], [])
        self.assertIn('memory_fraction', absent['failed_limits'])
        self.assertIn('forge_queue_wait_s', absent['failed_limits'])

    def test_nonfinite_negative_or_boolean_observations_cannot_pass(self):
        good = {'search_p95_s': .1, 'quote_p95_s': .2, 'memory_fraction': .5,
                'forge_queue_wait_s': 1, 'errors': 0, 'dropped': 0}
        for value in (float('nan'), float('inf'), -1, False, '0', None):
            for key in h.LIMITS:
                with self.subTest(key=key, value=value):
                    self.assertIn(key, h.failures({**good, key: value}))
            self.assertIsNone(h.quantile([.1, value], .95))
        for key in ('errors', 'dropped'):
            self.assertIn(key, h.failures({**good, key: False}))

    def test_bad_memory_or_queue_measurements_remain_invalid(self):
        traffic = {'latency': {'search': [.01], 'setup': [.02], 'quote': [.03]},
                   'errors': 0, 'dropped': 0}
        for used, total in ((1, 0), (-1, 100), (101, 100), (float('nan'), 100), (1, None)):
            report = h.report(traffic, [{'memory_used_bytes': used, 'memory_total_bytes': total}], [1])
            self.assertIn('memory_fraction', report['failed_limits'])
            self.assertFalse(report['capacity_valid'])
        for waits in ([], [float('nan')], [1, -1], [False]):
            self.assertIn('forge_queue_wait_s', h.report(traffic, [], waits)['failed_limits'])

    def test_cli_is_preflight_only_and_requires_explicit_flag(self):
        with patch('sys.argv', ['harness', 'placeholder.json']), patch.object(h, 'docker') as docker:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stopped:
                h.main()
            self.assertEqual(stopped.exception.code, 2)
            docker.assert_not_called()
        with patch('sys.argv', ['harness', 'placeholder.json', '--isolated-test-target']), \
                patch.object(h, 'load_config', return_value={}), patch.object(h, 'preflight') as guard, \
                patch.object(h, 'traffic') as traffic, contextlib.redirect_stdout(io.StringIO()) as output:
            h.main()
        guard.assert_called_once_with({})
        traffic.assert_not_called()
        result = json.loads(output.getvalue())
        self.assertEqual(result['status'], 'preflight_only')
        self.assertFalse(result['capacity_valid'])

    def test_spare_refusal_precedes_any_docker_inspection(self):
        with patch.object(h, 'docker') as docker, self.assertRaises(ValueError):
            h.preflight({'dedicated_spare_host': False})
        docker.assert_not_called()

    def test_config_rejects_error_statuses_and_unreviewed_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'placeholder-fixture').write_text('offline placeholder')
            operations = {kind: {'method': method, 'path': path, 'expected_statuses': [200]}
                          for kind, (method, path) in h.OPERATIONS.items()}
            config = {'rps_per_store': 1, 'concurrency_per_store': 1,
                      'catalogue_fixture': 'placeholder-fixture', 'forge_fixture': 'placeholder-fixture',
                      'target_allowlist': ['http://10.1.2.3:8000'], 'network': 'rigstress-placeholder',
                      'dedicated_spare_host': True,
                      'stores': [{'target': 'http://10.1.2.3:8000', 'operations': operations}] * 30}
            path = root / 'config.json'
            for statuses in ([], [500], [302], [True], '200', None, [200, 503]):
                operations['search']['expected_statuses'] = statuses
                path.write_text(json.dumps(config))
                with self.subTest(statuses=statuses), self.assertRaises(ValueError):
                    h.load_config(path)
            operations['search']['expected_statuses'] = [200]
            operations['search']['headers'] = {'placeholder': 'placeholder'}
            path.write_text(json.dumps(config))
            with self.assertRaises(ValueError):
                h.load_config(path)

    def test_overload_is_reported(self):
        async def slow_worker(*args):
            await asyncio.sleep(.05)
            return .05, True

        async def execute():
            with patch.object(h.asyncio, 'to_thread', side_effect=slow_worker):
                operations = {name: {} for name in ('search', 'setup', 'quote')}
                return await h.traffic([{'target': 'unused', 'operations': operations}], 100, 1, .15)
        self.assertGreater(asyncio.run(execute())['dropped'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
