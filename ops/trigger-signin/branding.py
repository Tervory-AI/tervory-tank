"""Configure native hosted branding; never supply a replacement login or email renderer."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re

LABEL = {'primaryColor': '#001840', 'backgroundColor': '#F4F6FB', 'fontColor': '#001840',
         'primaryColorDark': '#001840', 'backgroundColorDark': '#F4F6FB',
         'fontColorDark': '#001840', 'hideLoginNameSuffix': True,
         'disableWatermark': True, 'themeMode': 'THEME_MODE_LIGHT'}
ASSETS = [('logo', 'tervory-logo.png', 'image/png'), ('logo/dark', 'tervory-logo.png', 'image/png'),
          ('icon', 'tervory-logo.png', 'image/png'), ('icon/dark', 'tervory-logo.png', 'image/png'),
          ('font', 'Inter-latin.woff2', 'font/woff2')]
EMAILS = {'verifyemail': 'Verify your Trigger sign-in email',
          'passwordreset': 'Reset your Trigger sign-in password', 'init': 'Set up Trigger sign-in',
          'password_change': 'Your Trigger sign-in password changed',
          'verifyphone': 'Verify your Trigger sign-in phone',
          'verifyemailotp': 'Your Trigger sign-in code', 'verifysmsotp': 'Your Trigger sign-in code',
          'domainclaimed': 'Your Trigger sign-in username changed',
          'passwordless_registration': 'Add a passkey to Trigger sign-in',
          'invite_user': 'You are invited to Trigger sign-in'}
# Every native email is renamed: the upstream provider's name never reaches a recipient.
PROVIDER_NAMES = ('ZITADEL', 'Zitadel', 'zitadel')
PROVIDER = re.compile('zitadel', re.IGNORECASE)
FIELDS = ('title', 'preHeader', 'subject', 'greeting', 'text', 'buttonText', 'footerText')
# Every language the pinned hosted login (zitadel-login v4.20.0, src/lib/i18n.ts LANGS) offers.
# login-translations.json overrides, per language, each upstream string of that version that
# names the provider, plus the welcome line. Bumping the login image means regenerating it.
LOGIN_LOCALES = ('en', 'de', 'it', 'es', 'fr', 'nl', 'pl', 'pt', 'zh', 'ru', 'hu', 'tr', 'ja', 'uk', 'ar')
LOGIN_IMAGE_VERSION = 'v4.20.0'


def neutral_welcome(text: str) -> str:
    """'Welcome {user}!' -> 'Welcome!': the welcome line with no name in it."""
    return re.sub(r',?\s*\{user\}(?:さん)?', '', text)


def login_translations(locale: str, admin_named: bool) -> dict:
    """Overrides for one hosted login language. No provider name; a name only when one is set."""
    per_locale = json.loads(Path(__file__).with_name('login-translations.json').read_text())
    desired = deepcopy(per_locale[locale])
    if locale == 'en':
        desired = merge(desired, json.loads(Path(__file__).with_name('translations.json').read_text()))
    if not admin_named:
        # No display name set: "Welcome!", never the provider's default "ZITADEL Admin".
        desired['signedin']['title'] = neutral_welcome(desired['signedin']['title'])
    return desired


def neutral_text(value: str) -> str:
    for name in ('Tervory',) + PROVIDER_NAMES:
        value = value.replace(name, 'Trigger sign-in')
    return PROVIDER.sub('Trigger sign-in', value)


def merge(current, desired):
    result = deepcopy(current)
    for key, value in desired.items():
        result[key] = merge(result.get(key, {}), value) if isinstance(value, dict) else value
    return result


def configure_branding(api, bootstrap: Path, assets: Path, issuer: str, admin_named: bool = False):
    marker = bootstrap / 'trigger-signin-branding.json'
    try:
        previous = json.loads(marker.read_text())
    except (FileNotFoundError, ValueError):
        previous = {}
    previous = previous if previous.get('issuer') == issuer else {}
    hashes = {}
    changed = False
    # Updates and uploads modify the draft; active policy may still be the old one.
    current = api.request('GET', '/admin/v1/policies/label/_preview').get('policy', {})
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
    for locale in LOGIN_LOCALES:
        current = api.request('GET', translation_path, params={
            'instance': 'true', 'locale': locale, 'ignore_inheritance': 'true'}).get('translations', {})
        translated = merge(current, login_translations(locale, admin_named))
        if translated != current:
            api.request('PUT', translation_path, json={'instance': True, 'locale': locale, 'translations': translated})
    languages = api.request('GET', '/admin/v1/languages').get('languages', [])
    if not isinstance(languages, list) or 'en' not in languages:
        raise ValueError('Trigger sign-in email languages unavailable')
    for language in languages:
        if not isinstance(language, str) or not re.fullmatch(r'[a-z]{2,3}(?:-[A-Za-z]{2,4})?', language):
            raise ValueError('Trigger sign-in email languages unavailable')
        for kind, subject in EMAILS.items():
            path = '/admin/v1/text/message/' + kind + '/' + language
            current = api.request('GET', path).get('customText', {})
            if not current.get('text'):
                current = api.request('GET', '/admin/v1/text/default/message/' + kind + '/' + language).get('customText', {})
            if not isinstance(current.get('text'), str) or not current['text']:
                raise ValueError('Trigger sign-in native email text unavailable')
            desired = {field: current.get(field, '') for field in FIELDS}
            if language == 'en':
                desired.update(title=subject, subject=subject)
            desired['footerText'] = 'Trigger sign-in'
            for field in ('title', 'subject', 'text', 'greeting', 'preHeader', 'buttonText'):
                desired[field] = neutral_text(desired[field])
            if any(current.get(key, '') != value for key, value in desired.items()):
                api.request('PUT', path, json=desired)
    pending = marker.with_suffix('.pending')
    pending.write_text(json.dumps({'issuer': issuer, 'assets': hashes}) + '\n')
    pending.replace(marker)
