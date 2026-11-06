import json
from pathlib import Path
import re
import subprocess

import pytest

from test_tiger import ROOT
from tiger_sheet.patch_source import source


@pytest.mark.parametrize('scenario', ['chart', 'overview', 'history', 'alerts', 'watch',
    'position', 'matches', 'sites', 'unknown_site_counts', 'API keys', 'Files',
    'Source links', 'MCP connections', 'loaders'])
def test_rendered_day_zero_has_no_sample_values_and_an_action(tmp_path, scenario):
    import os
    project = Path(os.environ['TIGER_PROJECT_ROOT'])
    patch = (project/'tank-patches/gate4-workspace.patch').read_text()
    files = re.findall(r'^\+\+\+ b/(.+)$', patch, re.MULTILINE)
    proposed = tmp_path/'proposed.json'
    proposed.write_text(json.dumps({name: source(name) for name in files}))
    result = subprocess.run(['node', str(ROOT/'tests/tiger_sheet/gate4_ui.cjs'), str(proposed), scenario],
                            cwd=ROOT, text=True, capture_output=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
