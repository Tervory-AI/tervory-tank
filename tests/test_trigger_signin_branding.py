"""Configuration-only branding preserves native templates, URLs and substitutions."""
import copy
import json
from pathlib import Path
import runpy
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[1]
BRAND = runpy.run_path(str(ROOT / 'ops/trigger-signin/branding.py'))
SETUP = runpy.run_path(str(ROOT / 'ops/trigger-signin/setup.py'))
# Upstream zitadel-login v4.20.0 locales/*.json: every string that names the provider.
UPSTREAM_PROVIDER_KEYS = {locale: ['common.title', 'device.request.disclaimer', 'idp.signInWithZitadel',
                                   'register.description', 'signedin.title']
                          for locale in BRAND['LOGIN_LOCALES']}
UPSTREAM_PROVIDER_KEYS['de'][1] = 'device.request.description'


def strings(value):
    if isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, str):
        yield value


def at(tree, dotted):
    for key in dotted.split('.'):
        tree = tree[key]
    return tree


class NativeSettings:
    def __init__(self):
        self.policy = {'warnColor': '#f8961e', 'warnColorDark': '#ffba08'}
        self.draft = copy.deepcopy(self.policy)
        self.translations = {'common': {'unrelated': 'Keep this native string'}}
        self.locales = {'en': self.translations}
        self.languages = ['en']
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
                if all(self.draft.get(k) == v for k, v in kwargs['json'].items()):
                    raise ValueError('Upstream refuses unchanged draft')
                self.draft.update(kwargs['json'])
            return {'policy': copy.deepcopy(self.policy)}
        if path == '/admin/v1/policies/label/_preview':
            assert method == 'GET'
            return {'policy': copy.deepcopy(self.draft)}
        if path.startswith('/assets/v1/instance/policy/label/'):
            assert method == 'POST'
            assert len(kwargs['files']['file'][1]) > 0
            return {'assetId': str(len(self.writes))}
        if path == '/admin/v1/policies/label/_activate':
            assert method == 'POST'
            self.policy = copy.deepcopy(self.draft)
            return {}
        if path == '/v2/settings/hosted_login_translation':
            if method == 'PUT':
                assert kwargs['json']['instance'] is True
                assert kwargs['json']['locale'] in BRAND['LOGIN_LOCALES']
                self.locales[kwargs['json']['locale']] = kwargs['json']['translations']
                self.translations = self.locales['en']
                return {}
            assert kwargs['params']['locale'] in BRAND['LOGIN_LOCALES']
            return {'translations': copy.deepcopy(self.locales.get(kwargs['params']['locale'], {}))}
        if path == '/admin/v1/languages':
            assert method == 'GET'
            return {'languages': list(self.languages)}
        if path.startswith('/admin/v1/text/'):
            # These legacy-looking spellings are real upstream 404s.
            assert path.split('/')[-2] not in {'passwordchange', 'inviteuser'}
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
        BRAND['configure_branding'](api, bootstrap, assets, 'https://auth.tervory.com')
    assert not (bootstrap / 'trigger-signin-branding.json').exists()


def test_every_native_email_drops_the_provider_name(resources):
    bootstrap, assets = resources
    api = NativeSettings()
    api.default = {**api.default, 'text': 'Your ZITADEL account {{.PreferredLoginName}} changed.',
                   'preHeader': 'Zitadel notice'}
    BRAND['configure_branding'](api, bootstrap, assets, 'https://auth.tervory.com')
    kinds = {path.split('/')[-2] for path in api.messages}
    assert {'init', 'passwordreset', 'password_change', 'verifyemail', 'invite_user'} <= kinds
    for message in api.messages.values():
        assert 'zitadel' not in json.dumps(message).lower()
        assert '{{.PreferredLoginName}}' in message['text']


def test_retry_resumes_existing_draft_after_partial_upload(resources):
    bootstrap, assets = resources
    api = NativeSettings()
    request = api.request
    fail = True

    def interrupted(method, path, **kwargs):
        if fail and path == '/assets/v1/instance/policy/label/logo/dark':
            raise ValueError('Interrupted asset upload')
        return request(method, path, **kwargs)

    api.request = interrupted
    with pytest.raises(ValueError, match='Interrupted asset upload'):
        BRAND['configure_branding'](api, bootstrap, assets, 'https://auth.tervory.com')
    assert api.draft['primaryColor'] == BRAND['LABEL']['primaryColor']
    assert api.policy != api.draft
    assert not (bootstrap / 'trigger-signin-branding.json').exists()
    fail = False
    BRAND['configure_branding'](api, bootstrap, assets, 'https://auth.tervory.com')
    assert api.policy == api.draft
    assert (bootstrap / 'trigger-signin-branding.json').exists()
    assert sum(method == 'PUT' and path == '/admin/v1/policies/label'
               for method, path, _ in api.writes) == 1


def test_no_provider_name_in_any_login_text_title_or_email_in_any_language(resources):
    bootstrap, assets = resources
    api = NativeSettings()
    api.languages = ['en', 'de', 'ja', 'ar']
    api.default = {'greeting': 'Hello {{.DisplayName}},', 'text': 'Your ZITADEL account {{.PreferredLoginName}}.',
                   'buttonText': 'Open Zitadel', 'preHeader': 'zitadel notice', 'title': 'ZITADEL - Verify',
                   'subject': 'ZITADEL - Verify'}
    BRAND['configure_branding'](api, bootstrap, assets, 'https://auth.tervory.com')
    assert set(api.locales) == set(BRAND['LOGIN_LOCALES'])
    for locale, keys in UPSTREAM_PROVIDER_KEYS.items():
        shown = api.locales[locale]
        for key in keys:
            # Each upstream string that names the provider is replaced, so the user sees ours.
            assert 'zitadel' not in at(shown, key).lower(), (locale, key)
        # The browser tab title is common.title.
        assert at(shown, 'common.title').strip()
        assert '{user}' not in at(shown, 'signedin.title'), locale
        assert not [text for text in strings(shown) if 'zitadel' in text.lower()], locale
    assert api.locales['en']['signedin']['title'] == 'Welcome!'
    assert api.locales['ja']['signedin']['title'] == 'ようこそ！'
    kinds = {(path.split('/')[-2], path.split('/')[-1]) for path in api.messages}
    assert kinds == {(kind, language) for kind in BRAND['EMAILS'] for language in api.languages}
    for path, message in api.messages.items():
        assert 'zitadel' not in json.dumps(message, ensure_ascii=False).lower(), path
        assert message['footerText'] == 'Trigger sign-in'
        assert '{{.PreferredLoginName}}' in message['text']
    # No provider watermark; Tervory's own logo and icon (the favicon source) are uploaded.
    assert api.policy['disableWatermark'] is True
    uploaded = {path.rsplit('/label/', 1)[1] for method, path, _ in api.writes if path.startswith('/assets/')}
    assert {'logo', 'logo/dark', 'icon', 'icon/dark'} <= uploaded
    for text in strings(json.loads((ROOT / 'ops/trigger-signin/login-translations.json').read_text())):
        assert 'zitadel' not in text.lower()
    for text in strings(json.loads((ROOT / 'ops/trigger-signin/translations.json').read_text())):
        assert 'zitadel' not in text.lower()


def test_welcome_names_the_admin_only_when_a_display_name_is_set(resources):
    bootstrap, assets = resources
    api = NativeSettings()
    BRAND['configure_branding'](api, bootstrap, assets, 'https://auth.tervory.com', admin_named=True)
    for locale in BRAND['LOGIN_LOCALES']:
        assert '{user}' in api.locales[locale]['signedin']['title'], locale
    before = list(api.writes)
    BRAND['configure_branding'](api, bootstrap, assets, 'https://auth.tervory.com', admin_named=True)
    assert api.writes == before
    BRAND['configure_branding'](api, bootstrap, assets, 'https://auth.tervory.com', admin_named=False)
    for locale in BRAND['LOGIN_LOCALES']:
        assert '{user}' not in api.locales[locale]['signedin']['title'], locale


def test_login_overrides_match_the_pinned_login_image():
    compose = (ROOT / 'ops/trigger-signin/docker-compose.yml').read_text()
    assert 'zitadel-login:' + BRAND['LOGIN_IMAGE_VERSION'] + '@sha256:' in compose
    overrides = json.loads((ROOT / 'ops/trigger-signin/login-translations.json').read_text())
    assert set(overrides) == set(BRAND['LOGIN_LOCALES'])
    for locale, keys in UPSTREAM_PROVIDER_KEYS.items():
        for key in keys:
            assert at(overrides[locale], key)
    dockerfile = (ROOT / 'ops/trigger-signin/Dockerfile.setup').read_text()
    assert 'ops/trigger-signin/login-translations.json' in dockerfile


class Users:
    def __init__(self, profile):
        self.profile = dict(profile)
        self.writes = []

    def request(self, method, path, **kwargs):
        if path == '/management/v1/users/_search':
            assert method == 'POST'
            assert kwargs['json']['queries'][0]['emailQuery']['emailAddress'] == 'admin@example.invalid'
            return {'result': [{'id': '40001', 'human': {'profile': dict(self.profile)}}]}
        assert (method, path) == ('PUT', '/management/v1/users/40001/profile')
        self.writes.append(kwargs['json'])
        self.profile = dict(kwargs['json'])
        return {}


PROVIDER_DEFAULT = {'firstName': 'ZITADEL', 'lastName': 'Admin', 'displayName': 'ZITADEL Admin',
                    'preferredLanguage': 'en', 'gender': 'GENDER_UNSPECIFIED'}


def test_admin_display_name_comes_from_the_setting_and_is_idempotent():
    users = Users(PROVIDER_DEFAULT)
    named = SETUP['configure_admin_name'](users, 'admin@example.invalid', '  Jo   Example Person ')
    assert named is True
    assert users.profile['firstName'] == 'Jo'
    assert users.profile['lastName'] == 'Example Person'
    assert users.profile['displayName'] == 'Jo Example Person'
    assert users.profile['preferredLanguage'] == 'en'
    assert SETUP['configure_admin_name'](users, 'admin@example.invalid', 'Jo Example Person') is True
    assert len(users.writes) == 1
    assert SETUP['configure_admin_name'](users, 'admin@example.invalid', 'Jo') is True
    assert users.profile['firstName'] == users.profile['lastName'] == users.profile['displayName'] == 'Jo'


def test_unset_display_name_never_leaves_the_provider_default():
    users = Users(PROVIDER_DEFAULT)
    assert SETUP['configure_admin_name'](users, 'admin@example.invalid', '') is False
    assert 'zitadel' not in json.dumps(users.profile).lower()
    assert users.profile['displayName'] == 'Tervory'
    assert SETUP['configure_admin_name'](users, 'admin@example.invalid', '') is False
    assert len(users.writes) == 1
    renamed = Users({'firstName': 'Own', 'lastName': 'Name', 'displayName': 'Own Name'})
    assert SETUP['configure_admin_name'](renamed, 'admin@example.invalid', '') is False
    assert renamed.writes == []
    with pytest.raises(SETUP['SetupError'], match='display name refused'):
        SETUP['configure_admin_name'](Users(PROVIDER_DEFAULT), 'admin@example.invalid', 'Zitadel Admin')
    compose = (ROOT / 'ops/trigger-signin/docker-compose.yml').read_text()
    assert 'TRIGGER_SIGNIN_ADMIN_DISPLAY_NAME: ${TRIGGER_SIGNIN_ADMIN_DISPLAY_NAME:-}' in compose
