"""Configuration-only branding preserves native templates, URLs and substitutions."""
import copy
import json
from pathlib import Path
import runpy
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRAND = runpy.run_path(str(ROOT / 'ops/trigger-signin/branding.py'))


class NativeSettings:
    def __init__(self):
        self.policy = {'warnColor': '#f8961e', 'warnColorDark': '#ffba08'}
        self.translations = {'common': {'unrelated': 'Keep this native string'}}
        self.messages = {}
        self.writes = []
        self.default = {'greeting': 'Hello {{.DisplayName}},',
                        'text': 'Use {{.Code}} for {{.PreferredLoginName}}.',
                        'buttonText': 'Continue', 'preHeader': 'Native preheader'}

    def request(self, method, path, **kwargs):
        if method != 'GET':
            self.writes.append((method, path, kwargs))
        if path == '/admin/v1/policies/label':
            if method == 'PUT':
                self.policy.update(kwargs['json'])
            return {'policy': copy.deepcopy(self.policy)}
        if path.startswith('/assets/v1/instance/policy/label/'):
            assert method == 'POST'
            assert len(kwargs['files']['file'][1]) > 0
            return {'assetId': str(len(self.writes))}
        if path == '/admin/v1/policies/label/_activate':
            assert method == 'POST'
            return {}
        if path == '/v2/settings/hosted_login_translation':
            if method == 'PUT':
                assert kwargs['json']['instance'] is True
                assert kwargs['json']['locale'] == 'en'
                self.translations = kwargs['json']['translations']
            return {'translations': copy.deepcopy(self.translations)}
        if path.startswith('/admin/v1/text/default/message/'):
            return {'customText': copy.deepcopy(self.default)}
        assert path.startswith('/admin/v1/text/message/')
        if method == 'PUT':
            self.messages[path] = kwargs['json']
        return {'customText': copy.deepcopy(self.messages.get(path, {}))}


@pytest.fixture
def resources(tmp_path):
    assets = tmp_path / 'brand'
    assets.mkdir()
    shutil.copyfile(ROOT / 'workspace/public/brand/tervory-logo.png', assets / 'tervory-logo.png')
    shutil.copyfile(ROOT / 'workspace/app/fonts/Inter-latin.woff2', assets / 'Inter-latin.woff2')
    bootstrap = tmp_path / 'bootstrap'
    bootstrap.mkdir()
    return bootstrap, assets


def test_branding_is_light_native_named_and_idempotent(resources):
    bootstrap, assets = resources
    api = NativeSettings()
    configure = BRAND['configure_branding']
    configure(api, bootstrap, assets, 'https://auth.tervory.com')
    before = list(api.writes)
    configure(api, bootstrap, assets, 'https://auth.tervory.com')
    assert api.writes == before
    assert api.policy == {**BRAND['LABEL'], 'warnColor': '#f8961e', 'warnColorDark': '#ffba08'}
    assert api.policy['primaryColor'] == '#001840'
    assert api.policy['themeMode'] == 'THEME_MODE_LIGHT'
    assert api.policy['backgroundColorDark'] == api.policy['backgroundColor']
    assert api.translations['loginname']['title'] == 'Trigger sign-in'
    assert api.translations['common']['unrelated'] == 'Keep this native string'
    for message in api.messages.values():
        assert 'Trigger sign-in' in message['subject']
        assert message['footerText'] == 'Trigger sign-in'
        for field in ('greeting', 'text', 'preHeader', 'buttonText'):
            assert message[field] == api.default[field]
    marker = json.loads((bootstrap / 'trigger-signin-branding.json').read_text())
    assert marker['issuer'] == 'https://auth.tervory.com'
    assert len(marker['assets']) == 5
    assert 'secret' not in json.dumps(marker)


def test_branding_failure_does_not_publish_a_completion_marker(resources):
    bootstrap, assets = resources
    api = NativeSettings()
    api.default = {}
    with pytest.raises(ValueError, match='native email text unavailable'):
        BRAND['configure_branding'](api, bootstrap, assets, 'https://auth-za.tervory.com')
    assert not (bootstrap / 'trigger-signin-branding.json').exists()
