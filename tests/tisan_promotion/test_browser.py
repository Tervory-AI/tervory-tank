"""Real Chromium with intercepted synthetic HTTPS pages; no live host is contacted."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = r'''
const pw = require(process.env.TISAN_TEST_PLAYWRIGHT);
const fs = require('node:fs');
module.exports.chromium = {launch: async options => {
  const browser = await pw.chromium.launch(options);
  const originalContext = browser.newContext.bind(browser);
  browser.newContext = async options => {
    const context = await originalContext(options);
    const originalRoute = context.route.bind(context);
    context.route = (pattern, handler) => originalRoute(pattern, route => handler(new Proxy(route, {
      get(target, key) {
        if (key === 'continue') return () => target.fulfill({
          status: process.env.TISAN_TEST_MODE === 'denied' ? 403 : 200,
          contentType: 'text/html', body: `<h1>Ready</h1><script>
          fetch('https://foreign.example.org/').catch(()=>{});
          fetch('/submit', {method:'POST'}).catch(()=>{});
          ${process.env.TISAN_TEST_MODE === 'crash' ? "setTimeout(()=>{throw Error('local check')},100);" : ''}
          </script>`});
        if (key === 'abort') return () => {
          fs.appendFileSync(process.env.TISAN_TEST_TRACE, JSON.stringify({url: target.request().url(), method: target.request().method()})+'\n');
          return target.abort();
        };
        return typeof target[key] === 'function' ? target[key].bind(target) : target[key];
      }
    })));
    return context;
  };
  return browser;
}};
'''


@pytest.mark.parametrize('mode,passed', [('good', True), ('denied', False), ('crash', False)])
def test_staging_mode_checks_status_runtime_both_widths_and_blocks_writes(tmp_path, mode, passed):
    module = os.environ.get('TISAN_TEST_PLAYWRIGHT')
    if not module:
        pytest.skip('opt-in real Chromium runtime not selected')
    wrapper, output, trace = tmp_path / 'browser.cjs', tmp_path / 'proof', tmp_path / 'blocked.jsonl'
    wrapper.write_text(WRAPPER)
    env = {'PATH': os.environ.get('PATH', ''), 'HOME': os.environ.get('HOME', '/tmp'),
        'LIVE_CHECK_PLAYWRIGHT_PATH': str(wrapper), 'TISAN_TEST_PLAYWRIGHT': module,
        'TISAN_TEST_MODE': mode, 'TISAN_TEST_TRACE': str(trace)}
    result = subprocess.run([shutil.which('node'), str(ROOT / 'ops/live_check.mjs'),
        '--site-url', 'https://stage.example.org/', '--output', str(output)],
        env=env, text=True, capture_output=True, timeout=30)
    assert result.returncode == (0 if passed else 1), result.stderr
    rows = json.loads((output / 'results.json').read_text())
    assert len(rows) == 1 and rows[0]['passed'] is passed
    assert {v['width'] for v in rows[0]['viewports']} == {375, 1440}
    assert all((output / v['screenshot']).is_file() for v in rows[0]['viewports'])
    blocked = [json.loads(line) for line in trace.read_text().splitlines()]
    assert any(r['method'] == 'POST' for r in blocked)
    assert any(r['url'] == 'https://foreign.example.org/' for r in blocked)
