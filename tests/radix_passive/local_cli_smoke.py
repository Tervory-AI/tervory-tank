"""Real pinned CLIs, synthetic localhost page only. Run with docker --network none.

This checks tool contracts; DNS authorization/HTTPS egress are tested separately.
It is deliberately not a production-target override in the application.
"""
import json
import argparse
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import yaml
from passive_tools import zap_plan, zap_command, zap_findings, nuclei_findings


parser = argparse.ArgumentParser()
parser.add_argument('--response', choices=['200', '404', 'redirect'], default='200')
mode = parser.parse_args().response
landings = []


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/landing':
            landings.append(self.path)
        elif mode == 'redirect':
            self.send_response(302)
            self.send_header('Location', '/landing')
            self.end_headers()
            return
        elif mode == '404':
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<html><title>Offline authorized target</title><body>Local test</body></html>')

    def log_message(self, *args):
        pass


server = HTTPServer(('127.0.0.1', 8090), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        target = 'http://127.0.0.1:8090/'
        plan = zap_plan('https://owned.example/', root)
        context = plan['env']['contexts'][0]
        context['urls'] = [target]
        context['includePaths'] = [r'http://127\.0\.0\.1:8090/.*']
        plan['jobs'][1]['requests'][0]['url'] = target
        plan['jobs'][2]['parameters']['url'] = target
        plan['jobs'][4]['sites'] = [target.rstrip('/')]
        (root / 'plan.yaml').write_text(yaml.safe_dump(plan))
        command = zap_command(root / 'plan.yaml', root / 'zap-home')
        # Only for this offline CLI-contract test: direct to loopback, network disabled.
        command += ['-config', 'network.connection.httpProxy.enabled=false']
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=180)
        print('ZAP exit:', result.returncode, flush=True)
        if mode != '200':
            print('Synthetic response:', mode, '; redirected landing requests:', len(landings), flush=True)
            assert result.returncode != 0, 'non-200/redirect must not pass the root load check'
            assert not landings, 'requestor followed redirect instead of refusing root response'
            print('PASS: non-200 root refused before a clean assessment', flush=True)
            raise SystemExit(0)
        assert result.returncode == 0, 'ZAP passive baseline incomplete'
        report = json.loads((root / 'zap.json').read_text())
        findings = zap_findings(report, target)
        print('ZAP parsed findings:', len(findings), flush=True)
        command = ['nuclei', '-u', target, '-t', '/opt/radix-passive/http-missing-security-headers.yaml',
                   '-ni', '-duc', '-dr', '-nh', '-rl', '1', '-c', '1', '-bs', '1', '-retries', '0',
                   '-timeout', '5', '-jle', str(root / 'n.jsonl'), '-or', '-ot', '-stats', '-sj', '-si', '1', '-nc']
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
        print('Nuclei exit:', result.returncode, flush=True)
        assert result.returncode == 0
        stats = []
        for line in (result.stdout + b'\n' + result.stderr).splitlines():
            try:
                row = json.loads(line)
            except (ValueError, UnicodeError):
                continue
            if isinstance(row, dict) and 'requests' in row and 'errors' in row:
                stats.append(row)
        assert stats and int(stats[-1]['errors']) == 0 and int(stats[-1]['requests']) == 1
        findings = nuclei_findings((root / 'n.jsonl').read_text(), target)
        print('Nuclei confirmed requests: 1; errors: 0; parsed findings:', len(findings), flush=True)
        print('PASS: real passive CLIs against synthetic loopback; no live scan', flush=True)
finally:
    server.shutdown()
