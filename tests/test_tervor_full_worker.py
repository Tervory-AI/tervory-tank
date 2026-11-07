"""Full recorded FFL worker replay, with every vendor/model boundary faked."""
import json
from unittest.mock import AsyncMock

import pytest
from test_base_finish_training import database as _database, postgres as _postgres
from test_base_finish_training import recorded as _recorded, RecordedSkills, TODAY
from agents.base import training_day
from training_jobs.round_one import replay_ffl
from pathlib import Path
import room

database, postgres, recorded = _database, _postgres, _recorded


@pytest.mark.asyncio
@pytest.mark.timeout(1200)
async def test_complete_ffl_source_runs_all_base_worker_states_and_resumes_without_rework(database, recorded, tmp_path, monkeypatch):
    monkeypatch.setattr(room, 'publish', AsyncMock())
    skills = RecordedSkills()
    result = await training_day.execute(database, skills, recorded, tmp_path, today=TODAY)
    assert result['complete'] and result['records'] == result['done'] == 77611
    assert result['states'] == 55 and result['failed'] == result['model_spend'] == 0
    attempted = list(skills.attempted)
    assert len(set(attempted)) == 77611
    assert await training_day.execute(database, skills, recorded, tmp_path, today=TODAY) == result
    assert skills.attempted == attempted
    stored = json.loads((tmp_path/result['run_id']/'result.json').read_text())
    assert stored == result
    handoff = await replay_ffl(Path(__file__).parent/'fixtures/base-atf/0925-ffl-list-complete.txt.gz', tmp_path)
    assert handoff['base_records'] == handoff['tiger_receipts'] == result['done']
    assert handoff['resume_verified'] and handoff['external_requests'] == handoff['model_cost_usd'] == 0
