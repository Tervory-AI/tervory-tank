from types import SimpleNamespace

import pytest
from tank.training_jobs import run, train


@pytest.mark.parametrize('name', ['HF_TRAIN_BASE_MODEL', 'HF_TRAIN_BASE_REVISION'])
def test_gpu_entrypoint_has_no_default_base_or_revision(monkeypatch, name):
    for key in ('HF_TOKEN','HF_ORG','OUTPUT_REPO','TRAIN_DAY'):
        monkeypatch.setenv(key, 'fixture')
    monkeypatch.setenv('HF_TRAIN_BASE_MODEL', 'fixture/base')
    monkeypatch.setenv('HF_TRAIN_BASE_REVISION', 'a' * 40)
    monkeypatch.delenv(name)
    assert train.main() == {'status': 'not_configured', 'settings': [name]}


@pytest.mark.asyncio
@pytest.mark.parametrize('submit', [False, True])
async def test_dry_run_and_submission_stop_before_hf_without_founder_base(monkeypatch, submit):
    for key in ('HF_TOKEN','HF_ORG','DATABASE_URL'):
        monkeypatch.setenv(key, 'fixture')
    monkeypatch.delenv('HF_TRAIN_BASE_MODEL', raising=False)
    monkeypatch.delenv('HF_TRAIN_BASE_REVISION', raising=False)
    args = SimpleNamespace(submit=submit, dry_run=not submit, receipt=None, job_id='', agent='zenas')
    assert await run.run(args) == {'status': 'not_configured',
                                  'settings': ['HF_TRAIN_BASE_MODEL', 'HF_TRAIN_BASE_REVISION']}


@pytest.mark.parametrize('base,revision', [('fixture/base','main'), ('../base','a'*40), ('fixture/base','')])
def test_moving_revision_or_invalid_base_cannot_construct_trainer(monkeypatch, base, revision):
    for key in ('HF_TOKEN','HF_ORG','OUTPUT_REPO','TRAIN_DAY'):
        monkeypatch.setenv(key, 'fixture')
    monkeypatch.setenv('HF_TRAIN_BASE_MODEL', base)
    monkeypatch.setenv('HF_TRAIN_BASE_REVISION', revision)
    if revision:
        with pytest.raises(ValueError, match='explicit base'):
            train.main()
    else:
        assert train.main()['settings'] == ['HF_TRAIN_BASE_REVISION']


@pytest.mark.parametrize('private', [False, True])
def test_job_reads_only_private_pinned_configuration(monkeypatch, tmp_path, private):
    import json
    import sys
    path = tmp_path / 'training-config.json'
    path.write_text(json.dumps({'base_model': 'founder/chosen-base', 'base_revision': 'b' * 40}))
    calls = []
    def download(repo, name, **kwargs):
        calls.append((repo, name, kwargs))
        return path
    api = SimpleNamespace(model_info=lambda repo: SimpleNamespace(private=private, sha='c' * 40))
    monkeypatch.setitem(sys.modules, 'huggingface_hub', SimpleNamespace(HfApi=lambda **kwargs: api, hf_hub_download=download))
    monkeypatch.setenv('HF_TOKEN', 'fixture')
    monkeypatch.setenv('OUTPUT_REPO', 'fixture/output')
    if private:
        train.load_job_configuration()
        assert train.os.environ['HF_TRAIN_BASE_MODEL'] == 'founder/chosen-base'
        assert train.os.environ['HF_TRAIN_BASE_REVISION'] == 'b' * 40
        assert calls == [('fixture/output', 'training-config.json', {'revision': 'c' * 40})]
    else:
        with pytest.raises(ValueError, match='must be private'):
            train.load_job_configuration()
        assert calls == []
