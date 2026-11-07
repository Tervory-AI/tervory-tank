"""Local runtime must stay internal, bounded, reproducible and honestly priced."""
import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_local_model_is_private_cpu_only_and_zero_provider_cost():
    services = yaml.safe_load((ROOT / 'docker-compose.yml').read_text())['services']
    service = services['local-model']
    assert 'ports' not in service and service['cpus'] == 8 and service['mem_limit'] == '3g'
    assert service['read_only'] and service['cap_drop'] == ['ALL']
    docker = (ROOT / 'litellm/local-model/Dockerfile').read_text()
    assert 'USER 65532:65532' in docker and '"--n-gpu-layers", "0"' in docker
    rows = yaml.safe_load((ROOT / 'litellm/config.yaml').read_text())['model_list']
    local = next(row for row in rows if row['model_name'] == 'local')
    assert local['litellm_params']['api_base'] == 'http://local-model:8080/v1'
    for block in ('litellm_params', 'model_info'):
        assert local[block]['input_cost_per_token'] == local[block]['output_cost_per_token'] == 0
    assert 'Apache License' in (ROOT / 'litellm/local-model/LICENSE.model').read_text()


def test_download_rejects_wrong_bytes(tmp_path, monkeypatch):
    import io
    spec = importlib.util.spec_from_file_location('local_model_install', ROOT / 'litellm/local-model/install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from types import SimpleNamespace
    monkeypatch.setattr(module.urllib.request, 'build_opener', lambda *a: SimpleNamespace(open=lambda *a, **k: io.BytesIO(b'corrupt')))
    import pytest
    with pytest.raises(ValueError, match='checksum mismatch'):
        module.install(tmp_path)
    assert not list(tmp_path.iterdir())


def test_local_and_open_weight_serving_chain():
    config = yaml.safe_load((ROOT / 'litellm/config.yaml').read_text())
    chains = {key: value for item in config['litellm_settings']['fallbacks'] for key, value in item.items()}
    assert chains['local'] == ['local-large', 'llama-small', 'gpt-oss-small', 'qwen-small', 'gpt-oss', 'llama']
    assert chains['local-large'] == chains['local'][1:]
    service = yaml.safe_load((ROOT / 'docker-compose.yml').read_text())['services']['local-model-large']
    assert 'ports' not in service and service['cpus'] == 8 and service['mem_limit'] == '6g'
    assert service['command'][-2:] == ['--reasoning', 'off']
    assert 'Apache License' in (ROOT / 'litellm/local-model/LICENSE.large').read_text()


def test_runtime_archive_cannot_escape_and_download_cannot_redirect_to_local(tmp_path):
    import io
    import tarfile
    import pytest
    spec = importlib.util.spec_from_file_location('local_install_guard', ROOT / 'litellm/local-model/install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w') as archive:
        entry = tarfile.TarInfo('../escaped')
        entry.size = 4
        archive.addfile(entry, io.BytesIO(b'nope'))
    buffer.seek(0)
    with tarfile.open(fileobj=buffer) as archive, pytest.raises(ValueError, match='Unsafe'):
        module.extract_runtime(archive, tmp_path / 'runtime')
    assert not (tmp_path / 'escaped').exists()
    for destination in ('file:///etc/passwd', 'http://huggingface.co/file', 'https://127.0.0.1/file'):
        with pytest.raises(ValueError, match='HTTPS'):
            module.HTTPSRedirect().redirect_request(None, None, 302, '', {}, destination)
