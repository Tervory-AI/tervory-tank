"""Use production network attachments in isolated, internal-only Compose projects.

Both the two-NIC egress peer and three-NIC passive peer use their exact shared
interface and 8080 healthcheck. Fake DNS/lease/upstream; real peer-container I/O.
No production networks, containers, volumes, credentials or targets are used.
"""
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import yaml

parser = argparse.ArgumentParser()
parser.add_argument('--image', default='radix-passive-proof:verified')
args = parser.parse_args()
repo = Path(__file__).resolve().parents[2]
production = yaml.safe_load((repo / 'agents/radix/docker-compose.yml').read_text())
for role in ['egress-proxy', 'passive-egress']:
    project = 'radix-passive-nic-' + role
    attachments = production['services'][role]['networks']
    shared = [net for net in production['services']['agent-radix']['networks'] if net in attachments]
    assert attachments['proxy-link']['interface_name'] == 'radix-link'
    common = {'image': args.image, 'pull_policy': 'never', 'mem_limit': '256m', 'cpus': 0.5,
              'cap_drop': ['ALL'], 'security_opt': ['no-new-privileges:true'],
              'environment': {'PYTHONPATH': '/app'},
              'volumes': [str(repo / 'tests/radix_passive/private_proxy_smoke.py') + ':/tmp/private-proxy-smoke.py:ro']}
    server = {**common, 'command': ['python', '/tmp/private-proxy-smoke.py', '--server'],
              'networks': attachments, 'healthcheck': {
                  'test': production['services']['egress-proxy']['healthcheck']['test'],
                  'interval': '1s', 'timeout': '3s', 'retries': 20}}
    client = {**common, 'command': ['python', '/tmp/private-proxy-smoke.py'], 'networks': shared,
              'depends_on': {'radix-proxy-bind-proof': {'condition': 'service_healthy'}}}
    config = {'services': {'radix-proxy-bind-proof': server, 'client': client},
              'networks': {name: {'internal': True} for name in attachments}}
    with tempfile.TemporaryDirectory(prefix='radix-nic-proof-') as directory:
        path = Path(directory) / 'compose.json'
        path.write_text(json.dumps(config))
        command = ['docker', 'compose', '-p', project, '-f', str(path)]
        existing = subprocess.check_output(command + ['ps', '-q'], text=True).strip()
        assert not existing, 'isolated proof project already exists; refusing to overwrite it'
        print('TOPOLOGY', role, 'proxy networks', list(attachments), 'scanner networks', shared, flush=True)
        try:
            result = subprocess.run(command + ['up', '--abort-on-container-exit', '--exit-code-from', 'client'],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90, text=True)
            print(result.stdout, flush=True)
            print('COMPOSE_EXIT', result.returncode, flush=True)
            assert result.returncode == 0
        finally:
            cleanup = subprocess.run(command + ['down', '--volumes', '--remove-orphans'],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            print('CLEANUP_EXIT', cleanup.returncode, flush=True)
