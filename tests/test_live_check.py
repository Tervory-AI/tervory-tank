"""Real Chromium, local-only pages. Run directly in CI or under pytest."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def workflow_python(name):
    """Execute the actual workflow snippets with offline dependencies below."""
    workflow = (ROOT / '.github/workflows/live-check.yml').read_text()
    step = workflow.split('- name: ' + name, 1)[1].split('\n      - ', 1)[0]
    script = step.split("python3 - <<'PY'", 1)[1].split('\n', 1)[1]
    script = script.split('\n          PY', 1)[0]
    return '\n'.join(line[10:] for line in script.splitlines())


class WorkflowTests(unittest.TestCase):
    def test_coolify_waits_for_both_apps_and_rejects_unknown(self):
        script = workflow_python('Wait for Coolify to report the public apps healthy')
        for status in ['running:healthy', 'running:unknown', 'running:unhealthy']:
            with self.subTest(status=status):
                deploy = types.ModuleType('deploy_changed')
                deploy.MAIN_APP = 'main-id'
                calls = []

                def api(method, path):
                    calls.append((method, path))
                    return 200, [
                        {'uuid': 'main-id', 'name': 'arbitrary-main-name', 'status': status},
                        {'uuid': 'rig-id', 'name': 'agent-rig', 'status': 'running:healthy'},
                    ]

                deploy.api = api
                watchdog = types.ModuleType('watchdog')
                watchdog.norm_status = str
                with patch.dict('sys.modules', deploy_changed=deploy, watchdog=watchdog), \
                        patch('time.monotonic', side_effect=[0, 601]), patch('builtins.print'):
                    if status == 'running:healthy':
                        exec(compile(script, '<health-workflow>', 'exec'), {})
                    else:
                        with self.assertRaises(SystemExit) as error:
                            exec(compile(script, '<health-workflow>', 'exec'), {})
                        self.assertEqual(error.exception.code, 1)
                self.assertEqual(calls, [('GET', '/applications')])

    def test_coolify_missing_rig_does_not_pass(self):
        deploy = types.ModuleType('deploy_changed')
        deploy.MAIN_APP = 'main-id'
        deploy.api = lambda *_: (200, [{'uuid': 'main-id', 'status': 'running:healthy'}])
        watchdog = types.ModuleType('watchdog')
        watchdog.norm_status = str
        with patch.dict('sys.modules', deploy_changed=deploy, watchdog=watchdog), \
                patch('time.monotonic', side_effect=[0, 601]), patch('builtins.print'):
            with self.assertRaises(SystemExit):
                exec(compile(workflow_python('Wait for Coolify to report the public apps healthy'),
                             '<health-workflow>', 'exec'), {})

    def test_failure_issue_is_updated_without_duplicates(self):
        opened = {}
        events = []

        class FakeGitHub:
            def __init__(self, *_):
                pass

            def ensure_label(self):
                pass

            def open_incidents(self):
                return opened

            def open_issue(self, title, body):
                opened[title] = {'number': 1}
                events.append(('create', title, body))

            def set_body(self, number, body):
                events.append(('update', number, body))

        watchdog = types.ModuleType('watchdog')
        watchdog.GitHub = FakeGitHub
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, 'results.json').write_text(json.dumps([
                {'host': 'good.example', 'passed': True, 'viewports': []},
                {'host': 'bad.example', 'passed': False, 'viewports': [
                    {'width': 375, 'reasons': ['Visible text: Fixture'], 'screenshot': 'bad.example-375.png'},
                ]},
            ]))
            env = {'LIVE_CHECK_OUTPUT': directory, 'GITHUB_REPOSITORY': 'offline/check',
                   'GITHUB_TOKEN': 'offline', 'GITHUB_SERVER_URL': 'https://github.com',
                   'GITHUB_RUN_ID': '123', 'ARTIFACT_URL': 'https://github.com/offline/artifacts/456'}
            with patch.dict(os.environ, env), patch.dict('sys.modules', watchdog=watchdog), \
                    patch('builtins.print'):
                for _ in range(2):
                    exec(compile(workflow_python('Open or update one issue per failed host'),
                                 '<issue-workflow>', 'exec'), {})
        self.assertEqual([event[0] for event in events], ['create', 'update'])
        self.assertEqual(events[0][1], 'Live check failed: bad.example')
        self.assertIn('bad.example-375.png', events[0][2])
        self.assertIn('https://github.com/offline/artifacts/456', events[0][2])


class Pages(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path == '/disconnect':
            self.close_connection = True
            return
        if self.path == '/redirect':
            self.send_response(302)
            self.send_header('Location', '/good')
            self.end_headers()
            return
        if self.path == '/slow.js':
            time.sleep(3)
        pages = {
            '/good': '<h1>Ready</h1><div hidden>Fixture</div><script>/* sample data */</script>',
            '/crash': '<h1>Application error</h1>',
            '/client': '<h1>A client-side exception has occurred</h1>',
            '/banned': '<h1>SAMPLE DATA Fixture [TEST] Demo price CVE-2024-0000 00000000-0000-0000-0000</h1>',
            '/throw': '<script>setTimeout(() => {throw Error("boom")}, 200)</script>',
            '/reject': '<script>setTimeout(() => Promise.reject(Error("boom")), 200)</script>',
            '/console': '<script>console.error("Uncaught Error: boom")</script>',
            '/http500': '<h1>Unavailable</h1>',
            '/timeout': '<h1>Waiting</h1><script src="/slow.js"></script>',
            '/mobile': '<style>@media(min-width:500px){.bad{display:none}}</style><p class="bad">Fixture</p>',
            '/cookie': '<script>document.body.textContent = document.cookie ? "Fixture" : "Ready";document.cookie="seen=1"</script>',
        }
        body = ('<!doctype html><html><body>' + pages.get(self.path, '') + '</body></html>').encode()
        self.send_response(503 if self.path == '/http500' else 200)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


class LiveCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.directory = Path(cls.temp.name)
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Pages)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.paths = ['good', 'crash', 'client', 'banned', 'throw', 'reject', 'console',
                     'http500', 'timeout', 'mobile', 'redirect', 'cookie', 'cookie', 'disconnect']
        cls.urls = cls.directory / 'urls.json'
        cls.urls.write_text(json.dumps([
            f'http://127.0.0.1:{cls.server.server_port}/{item}' for item in cls.paths
        ]))
        cls.output = cls.directory / 'output'
        cls.command = ['node', 'ops/live_check.mjs', '--local-urls', str(cls.urls),
                       '--output', str(cls.output), '--timeout-ms', '1000']
        cls.browser_run = subprocess.run(cls.command, cwd=ROOT, text=True, capture_output=True, timeout=150)
        if not (cls.output / 'results.json').exists():
            raise AssertionError(cls.browser_run.stdout + cls.browser_run.stderr)
        cls.rows = json.loads((cls.output / 'results.json').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        cls.temp.cleanup()

    def reasons(self, index):
        return '; '.join(reason for row in self.rows[index]['viewports'] for reason in row['reasons'])

    def test_good_hidden_text_redirect_and_isolation_pass(self):
        for index in [0, 10, 11, 12]:
            with self.subTest(path=self.paths[index]):
                self.assertTrue(self.rows[index]['passed'], self.reasons(index))

    def test_visible_application_and_client_crashes_fail(self):
        for index, marker in [(1, 'Application error'), (2, 'client-side exception')]:
            self.assertFalse(self.rows[index]['passed'])
            self.assertIn(marker, self.reasons(index))

    def test_every_banned_token_fails(self):
        for marker in ['sample data', 'Fixture', '[TEST]', 'Demo price',
                       'CVE-2024-0000', '00000000-0000-0000-0000']:
            self.assertIn(marker, self.reasons(3))
        self.assertFalse(self.rows[3]['passed'])

    def test_runtime_throw_rejection_and_console_fail(self):
        for index in [4, 5, 6]:
            self.assertFalse(self.rows[index]['passed'])
            self.assertIn('exception', self.reasons(index))

    def test_http_failure_and_navigation_deadline(self):
        self.assertIn('HTTP 503', self.reasons(7))
        self.assertIn('did not load within 1000ms', self.reasons(8))

    def test_connection_failure_has_a_safe_browser_diagnostic(self):
        self.assertFalse(self.rows[13]['passed'])
        self.assertIn('ERR_EMPTY_RESPONSE', self.reasons(13))
        self.assertNotIn('http://', self.reasons(13))

    def test_mobile_visible_text_fails_host(self):
        row = self.rows[9]
        self.assertFalse(row['passed'])
        self.assertEqual(row['viewports'][0]['reasons'], [])
        self.assertIn('Visible text: Fixture', row['viewports'][1]['reasons'])

    def test_every_host_including_failures_has_both_screenshots(self):
        self.assertEqual(len(self.rows), len(self.paths))
        for row in self.rows:
            self.assertEqual([item['width'] for item in row['viewports']], [1440, 375])
            for view in row['viewports']:
                data = (self.output / view['screenshot']).read_bytes()
                self.assertEqual(data[:8], b'\x89PNG\r\n\x1a\n')
                self.assertEqual(int.from_bytes(data[16:20], 'big'), view['width'])

    def test_mixed_run_is_red_and_summary_names_every_host(self):
        self.assertEqual(self.browser_run.returncode, 1, self.browser_run.stderr)
        summary = (self.output / 'summary.md').read_text()
        for row in self.rows:
            self.assertIn(row['host'], summary)
            self.assertIn(row['host'], self.browser_run.stdout)
        self.assertIn('Signed-in checks skipped', summary)

    def test_all_good_run_exits_zero(self):
        urls = self.directory / 'good.json'
        urls.write_text(json.dumps([f'http://127.0.0.1:{self.server.server_port}/good']))
        run = subprocess.run(['node', 'ops/live_check.mjs', '--local-urls', str(urls),
                              '--output', str(self.directory / 'good-output')], cwd=ROOT,
                             text=True, capture_output=True, timeout=30)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_test_mode_refuses_nonlocal_urls(self):
        urls = self.directory / 'invalid.json'
        urls.write_text(json.dumps(['https://app.tervory.com/']))
        run = subprocess.run(['node', 'ops/live_check.mjs', '--local-urls', str(urls),
                              '--output', str(self.directory / 'invalid-output')], cwd=ROOT,
                             text=True, capture_output=True, timeout=10)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn('Offline targets must use', run.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
