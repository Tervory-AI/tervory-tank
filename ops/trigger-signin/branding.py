"""Configure native hosted branding; never supply a replacement login or email renderer."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

LABEL = {'primaryColor': '#001840', 'backgroundColor': '#F4F6FB', 'fontColor': '#001840',
         'primaryColorDark': '#001840', 'backgroundColorDark': '#F4F6FB',
         'fontColorDark': '#001840', 'hideLoginNameSuffix': True,
         'disableWatermark': True, 'themeMode': 'THEME_MODE_LIGHT'}
ASSETS = [('logo', 'tervory-logo.png', 'image/png'), ('logo/dark', 'tervory-logo.png', 'image/png'),
          ('icon', 'tervory-logo.png', 'image/png'), ('icon/dark', 'tervory-logo.png', 'image/png'),
          ('font', 'Inter-latin.woff2', 'font/woff2')]
EMAILS = {'verifyemail': 'Verify your Trigger sign-in email',
          'passwordreset': 'Reset your Trigger sign-in password', 'init': 'Set up Trigger sign-in',
          'passwordchange': 'Your Trigger sign-in password changed',
          'verifyphone': 'Verify your Trigger sign-in phone',
          'verifyemailotp': 'Your Trigger sign-in code', 'verifysmsotp': 'Your Trigger sign-in code',
          'domainclaimed': 'Your Trigger sign-in username changed',
          'passwordless_registration': 'Add a passkey to Trigger sign-in',
          'inviteuser': 'You are invited to Trigger sign-in'}
# Every native email is renamed: the upstream provider's name never reaches a recipient.
PROVIDER_NAMES = ('ZITADEL', 'Zitadel', 'zitadel')
FIELDS = ('title', 'preHeader', 'subject', 'greeting', 'text', 'buttonText', 'footerText')


def merge(current, desired):
    result = deepcopy(current)
    for key, value in desired.items():
        result[key] = merge(result.get(key, {}), value) if isinstance(value, dict) else value
    return result


def configure_branding(api, bootstrap: Path, assets: Path, issuer: str):
    marker = bootstrap / 'trigger-signin-branding.json'
    try:
        previous = json.loads(marker.read_text())
    except (FileNotFoundError, ValueError):
        previous = {}
    previous = previous if previous.get('issuer') == issuer else {}
    hashes = {}
    changed = False
    current = api.request('GET', '/admin/v1/policies/label').get('policy', {})
    if any(current.get(key) != value for key, value in LABEL.items()):
        api.request('PUT', '/admin/v1/policies/label', json={
            **{key: current[key] for key in ('warnColor', 'warnColorDark') if key in current}, **LABEL,
        })
        changed = True
    for target, filename, mime in ASSETS:
        data = (assets / filename).read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        hashes[target] = digest
        if previous.get('assets', {}).get(target) != digest:
            api.request('POST', '/assets/v1/instance/policy/label/' + target,
                        files={'file': (filename, data, mime)})
            changed = True
    if changed:
        api.request('POST', '/admin/v1/policies/label/_activate', json={})
    translation_path = '/v2/settings/hosted_login_translation'
    current = api.request('GET', translation_path,
                          params={'instance': 'true', 'locale': 'en', 'ignore_inheritance': 'true'}).get('translations', {})
    desired = json.loads((Path(__file__).with_name('translations.json')).read_text())
    translated = merge(current, desired)
    if translated != current:
        api.request('PUT', translation_path, json={'instance': True, 'locale': 'en', 'translations': translated})
    for kind, subject in EMAILS.items():
        path = '/admin/v1/text/message/' + kind + '/en'
        current = api.request('GET', path).get('customText', {})
        if not current.get('text'):
            current = api.request('GET', '/admin/v1/text/default/message/' + kind + '/en').get('customText', {})
        if not isinstance(current.get('text'), str) or not current['text']:
            raise ValueError('Trigger sign-in native email text unavailable')
        desired = {field: current.get(field, '') for field in FIELDS}
        desired.update(title=subject, subject=subject, footerText='Trigger sign-in')
        for field in ('text', 'greeting', 'preHeader', 'buttonText'):
            for name in ('Tervory',) + PROVIDER_NAMES:
                desired[field] = desired[field].replace(name, 'Trigger sign-in')
        if any(current.get(key, '') != value for key, value in desired.items()):
            api.request('PUT', path, json=desired)
    pending = marker.with_suffix('.pending')
    pending.write_text(json.dumps({'issuer': issuer, 'assets': hashes}) + '\n')
    pending.replace(marker)
