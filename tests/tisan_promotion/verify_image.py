"""Run only inside the isolated network-none Tisan test image, never production."""
import hashlib
from pathlib import Path
import subprocess
import sys

import app
import httpx
import pydantic

root = Path(__file__).resolve().parents[2]
for relative, deployed in [('agents/tisan/app.py', '/app/app.py'),
                           ('agents/tisan/promotion.py', '/app/promotion.py'),
                           ('agents/tisan/promotion_api.py', '/app/promotion_api.py'),
                           ('ops/live_check.mjs', '/app/ops/live_check.mjs')]:
    digest = hashlib.sha256((root / relative).read_bytes()).hexdigest()
    assert digest == hashlib.sha256(Path(deployed).read_bytes()).hexdigest(), relative
    print(f'PACKAGED {relative} {digest}', flush=True)
paths = app.app.openapi()['paths']
assert all('/promotion/' + name in paths for name in ('sites', 'promote', 'rollback', 'status', 'history'))
print('Packaged room mount passed; Python', sys.version.split()[0], 'httpx', httpx.__version__, 'pydantic', pydantic.__version__, flush=True)
raise SystemExit(subprocess.call([sys.executable, '-m', 'pytest', '-p', 'no:cacheprovider', '-q',
    'tests/tisan_promotion/test_promotion.py', 'tests/tisan_promotion/test_tisan_promotion_api.py',
    'tests/tisan_promotion/test_browser.py', 'tests/test_tisan_figma.py',
    'tests/test_tisan_scaffold.py', 'tests/test_tisan_page.py', '--tb=short'], cwd=root))
