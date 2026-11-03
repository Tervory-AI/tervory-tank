"""Synthetic archive proof for all four real tools inside --network none. No DB."""
import base64
import io
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace

from scanlib.orchestrate import build_result

fixture = 'tvfy-example-fixture-key-' + '0001'
files = {
    'placeholder.env': 'PLACEHOLDER_TOKEN=' + fixture + '\n',
    'package.json': '{"dependencies":{"minimist":"1.2.5"}}\n',
    'placeholder.py': 'def lookup(cur, name):\n    cur.execute("SELECT * FROM users WHERE name = \'%s\'" % name)\n',
    'open.tf': Path('/repo/tank/skills/scan.iac/1.0.0/evals/fixtures/terraform/open.tf').read_text(),
}
buffer = io.BytesIO()
with tarfile.open(fileobj=buffer, mode='w:gz') as archive:
    for name, text in files.items():
        raw = text.encode()
        info = tarfile.TarInfo(name)
        info.size = len(raw)
        archive.addfile(info, io.BytesIO(raw))
tenant = '11111111-1111-1111-1111-111111111111'
ctx = SimpleNamespace(tenant_id=tenant, job_id='33333333-3333-4333-8333-333333333333',
                      input={'tenant_id': tenant, 'ref': 'placeholder-repo',
                             'source': 'b64:' + base64.b64encode(buffer.getvalue()).decode()})
result = build_result(ctx)
assert {row['tool'] for row in result['findings']} == {'scan.secrets', 'scan.dependencies', 'scan.static', 'scan.iac'}
assert result['tool_status']['scan.iac'] == 'run' and result['scan_complete'] is True
assert all(row['severity'] == 'unknown' for row in result['findings'] if row['tool'] == 'scan.iac')
assert fixture not in json.dumps(result) and result['leaked'] is False
print(json.dumps(result), flush=True)
