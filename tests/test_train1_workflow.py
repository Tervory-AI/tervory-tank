"""Execute the actual workflow script with an in-memory GitHub and Tank."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow_script():
    workflow = yaml.safe_load((ROOT / ".github/workflows/retest.yml").read_text())
    return workflow["jobs"]["training"]["steps"][0]["with"]["script"]


@pytest.mark.parametrize("existing,expected", [(False, 1), (True, 0)])
def test_workflow_opens_issue_for_three_point_drop(existing, expected):
    if not shutil.which("node"):
        pytest.skip("Node is required to execute the workflow's JavaScript")
    setup = '''
      const calls = [];
      const core = { notice() {}, setFailed(message) { throw new Error(message); } };
      const context = { repo: {owner: 'fixture', repo: 'fixture'} };
      const github = { rest: { issues: { listForRepo() {}, create: async args => calls.push(args) } },
        paginate: async () => EXISTING ? [{title:'Score drop: base.fixture'}] : [] };
      process.env.TRAINING_TANK_URL = 'https://tank.example.invalid';
      process.env.TRAINING_JOB_KEY = require('node:crypto').randomUUID();
      const fetch = async (url, options) => {
        if (url.search || url.username || options.headers['x-tank-key'] !== process.env.TRAINING_JOB_KEY) throw new Error('unsafe request');
        return { ok: true, json: async () => ({results:[{skill_id:'base.fixture', previous:0.98,score:0.95,n:100,drop:true}]}) };
      };
    '''.replace("EXISTING", json.dumps(existing))
    program = setup + "\n(async () => {\n" + workflow_script() + "\nconsole.log(JSON.stringify(calls)); })();"
    result = subprocess.run(["node", "-e", program], capture_output=True, text=True, check=True)
    calls = json.loads(result.stdout)
    assert len(calls) == expected
    if calls:
        assert calls[0]["title"] == "Score drop: base.fixture"
        assert "98.0% to 95.0%" in calls[0]["body"]
