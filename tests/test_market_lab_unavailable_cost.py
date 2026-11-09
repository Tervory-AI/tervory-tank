"""Only an explicit pre-send refusal certifies zero; dispatched failures propagate."""
from pathlib import Path
import os
import subprocess
import sys


def test_plain_research_outage_keeps_actual_cost_unknown():
    root = Path(__file__).resolve().parents[1]
    program = '''
import asyncio, os
import httpx
from core import personal, research_adapter
os.environ.pop('MARKET_LAB_MEMORY_ENABLED', None)
async def unavailable(*args, **kwargs):
    raise httpx.ReadTimeout('placeholder-dispatched-research')
research_adapter.research_web = unavailable
try:
    asyncio.run(personal.research_result(None, 'placeholder-tenant', None, 'placeholder question'))
except httpx.ReadTimeout:
    pass
else:
    raise AssertionError('A dispatched failure must not become a free result')
async def not_started(*args, **kwargs):
    return None
research_adapter.research_web = not_started
result = asyncio.run(personal.research_result(None, 'placeholder-tenant', None, 'placeholder question'))
assert result == {'cost_usd': 0, 'status': 'unavailable'}
'''
    env = {**os.environ, 'PYTHONPATH': str(root / 'agents/market_lab')}
    result = subprocess.run([sys.executable, '-c', program], cwd=root, env=env,
                            capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
