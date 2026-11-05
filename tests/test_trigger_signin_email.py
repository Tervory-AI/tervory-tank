"""Setup turns on email and sends the founder one setup email; the mail password never lands on disk."""
from pathlib import Path
import runpy

import pytest

ROOT = Path(__file__).resolve().parents[1]
EMAIL = runpy.run_path(str(ROOT / 'ops/trigger-signin/email_setup.py'))
ENV = {'TRIGGER_SIGNIN_SMTP_HOST': 'smtp.gmail.com', 'TRIGGER_SIGNIN_SMTP_PORT': '587',
       'TRIGGER_SIGNIN_SMTP_USER': 'tervory@gmail.com', 'TRIGGER_SIGNIN_SMTP_FROM': 'tervory@gmail.com',
       'TRIGGER_SIGNIN_SMTP_PASSWORD': 'synthetic-mail-value', 'TRIGGER_SIGNIN_ADMIN_EMAIL': 'founder@example.test'}


class Native:
    def __init__(self):
        self.configs = []
        self.calls = []

    def request(self, method, path, **kwargs):
        self.calls.append((method, path, kwargs.get('json')))
        if path == '/admin/v1/smtp/_search':
            return {'result': [dict(c) for c in self.configs]}
        if method == 'POST' and path == '/admin/v1/smtp':
            self.configs.append({'id': 's1', 'description': kwargs['json']['description'], 'state': 'SMTP_CONFIG_INACTIVE'})
            return {'id': 's1'}
        if path.endswith('/_activate'):
            self.configs[0]['state'] = 'SMTP_CONFIG_ACTIVE'
            return {}
        if path == '/v2/users':
            return {'result': [{'userId': 'u1'}]}
        return {}


def test_email_on_and_one_setup_email(tmp_path):
    api = Native()
    assert EMAIL['configure_email'](api, tmp_path, ENV) is True
    assert ('POST', '/v2/users/u1/password_reset',
            {'sendLink': {'notificationType': 'NOTIFICATION_TYPE_Email'}}) in api.calls
    assert api.configs[0]['state'] == 'SMTP_CONFIG_ACTIVE'
    created = next(body for m, p, body in api.calls if m == 'POST' and p == '/admin/v1/smtp')
    assert created['host'] == 'smtp.gmail.com:587' and created['tls'] is True
    for f in tmp_path.iterdir():
        assert 'synthetic-mail-value' not in f.read_text()
    api.calls.clear()
    assert EMAIL['configure_email'](api, tmp_path, ENV) is False
    assert not any(p.endswith('/password_reset') for _, p, _ in api.calls)
    assert not any(m == 'POST' and p == '/admin/v1/smtp' for m, p, _ in api.calls)


def test_missing_mail_secret_stops_setup(tmp_path):
    env = {k: v for k, v in ENV.items() if k != 'TRIGGER_SIGNIN_SMTP_PASSWORD'}
    with pytest.raises(ValueError, match='TRIGGER_SIGNIN_SMTP_PASSWORD'):
        EMAIL['configure_email'](Native(), tmp_path, env)


def test_existing_mail_settings_are_reused_not_duplicated(tmp_path):
    api = Native()
    api.configs.append({'id': 'live', 'description': 'set by hand', 'host': 'smtp.gmail.com:587',
                        'user': 'tervory@gmail.com', 'senderAddress': 'tervory@gmail.com',
                        'state': 'SMTP_CONFIG_ACTIVE'})
    EMAIL['configure_smtp'](api, ENV)
    assert not any(m == 'POST' and p == '/admin/v1/smtp' for m, p, _ in api.calls)
    assert not any(p.endswith('/_activate') for _, p, _ in api.calls)
