import json
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tiger_sheet.patch_source import module
from tiger_sheet.test_finish_training import hub, trainer


def test_training_start_command_dry_run_reaches_launch_boundary_without_writes(trainer, hub, monkeypatch, capsys):
    api, _, requests = hub
    api.list_jobs_hardware = lambda: [SimpleNamespace(name='a10g-small', unit_label='minute', unit_cost_micro_usd=10000)]
    def forbidden(**kwargs):
        raise AssertionError('dry-run must not launch or create artifacts')
    api.create_repo, api.run_uv_job = forbidden, forbidden
    conn = SimpleNamespace(fetchval=AsyncMock(return_value=False), close=AsyncMock())
    import asyncpg
    monkeypatch.setattr(asyncpg, 'connect', AsyncMock(return_value=conn))
    monkeypatch.setitem(sys.modules, 'train', trainer)
    for name, value in {'HF_ORG': 'placeholder-org', 'HF_TOKEN': 'placeholder',
                        'DATABASE_URL': 'placeholder', 'TANK_REGION': 'us-east'}.items():
        monkeypatch.setenv(name, value)
    runner = module('tank/training_jobs/run.py')
    result = runner.cli(['--agent', 'tiger', '--day', '2026-11-07', '--dry-run', '--json'])
    assert result['dry_run'] and result['status'] == 'ready'
    assert result['training_rows'] == 60 and result['holdout_rows'] == 2
    assert result['revision'] == 'placeholder-revision' and result['context_length'] == 4096
    assert result['eval_gate'] == 'exact_price_fields'
    assert result['artifacts'] == ['evaluation.json', 'holdout.json']
    assert result['output_prefix'] == 'placeholder-org/tervory-own-tiger-'
    assert str(result['cost_usd']) == '1.20'
    assert requests and all(row[2]['revision'] == result['revision'] for row in requests)
    assert conn.fetchval.call_args.args[0].startswith('SELECT EXISTS')
    conn.close.assert_awaited_once()
    assert json.loads(capsys.readouterr().out.splitlines()[-1])['dry_run']


@pytest.mark.parametrize('name', ['HF_ORG', 'HF_TOKEN', 'DATABASE_URL'])
def test_missing_training_setting_is_reported_without_clients_or_launch(name, monkeypatch, capsys):
    for setting in ('HF_ORG', 'HF_TOKEN', 'DATABASE_URL'):
        monkeypatch.setenv(setting, 'placeholder')
    monkeypatch.delenv(name)
    runner = module('tank/training_jobs/run.py')
    result = runner.cli(['--agent', 'tiger', '--day', '2026-11-07', '--dry-run'])
    assert result == {'status': 'not_configured', 'settings': [name]}
    assert json.loads(capsys.readouterr().out) == result


def test_training_dry_run_cannot_be_combined_with_submit(monkeypatch):
    runner = module('tank/training_jobs/run.py')
    with pytest.raises(SystemExit, match='Training operation failed'):
        runner.cli(['--agent', 'tiger', '--day', '2026-11-07', '--dry-run', '--submit'])


@pytest.mark.parametrize('name', ['HF_TOKEN', 'HF_ORG', 'OUTPUT_REPO', 'TRAIN_DAY'])
def test_gpu_entrypoint_reports_missing_settings_before_importing_gpu_libraries(name, monkeypatch, capsys):
    for setting in ('HF_TOKEN', 'HF_ORG', 'OUTPUT_REPO', 'TRAIN_DAY'):
        monkeypatch.setenv(setting, 'placeholder')
    monkeypatch.delenv(name)
    trainer = module('tank/training_jobs/train.py')
    assert trainer.main() == {'status': 'not_configured', 'settings': [name]}
    assert json.loads(capsys.readouterr().out)['settings'] == [name]
