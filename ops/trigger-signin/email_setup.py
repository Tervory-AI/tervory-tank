"""Turn on Trigger sign-in email and send the founder's setup email.

The SMTP password is read from the environment and sent only to the sign-in
admin API. It is never printed, logged or written to the bootstrap volume.
"""
import json
import os
from pathlib import Path

SMTP_DESCRIPTION = 'Tervory'
SMTP_SETTINGS = ('TRIGGER_SIGNIN_SMTP_HOST', 'TRIGGER_SIGNIN_SMTP_PORT', 'TRIGGER_SIGNIN_SMTP_USER',
                 'TRIGGER_SIGNIN_SMTP_FROM', 'TRIGGER_SIGNIN_SMTP_PASSWORD')


class EmailSetupError(ValueError):
    pass


def smtp_settings(env=os.environ):
    missing = [name for name in SMTP_SETTINGS if not env.get(name)]
    if missing:
        raise EmailSetupError('Trigger sign-in email settings missing: ' + ', '.join(missing))
    return {
        'description': SMTP_DESCRIPTION,
        'senderAddress': env['TRIGGER_SIGNIN_SMTP_FROM'],
        'senderName': env.get('TRIGGER_SIGNIN_SMTP_FROM_NAME') or 'Tervory',
        'tls': True,
        'host': env['TRIGGER_SIGNIN_SMTP_HOST'] + ':' + env['TRIGGER_SIGNIN_SMTP_PORT'],
        'user': env['TRIGGER_SIGNIN_SMTP_USER'],
        'password': env['TRIGGER_SIGNIN_SMTP_PASSWORD'],
    }


def configure_smtp(api, env=os.environ):
    desired = smtp_settings(env)
    found = api.request('POST', '/admin/v1/smtp/_search', json={}).get('result', [])
    same = ('host', 'user', 'senderAddress')
    ours = [c for c in found if c.get('description') == SMTP_DESCRIPTION]
    if not ours:
        # Reuse working mail settings already on the server instead of adding a second set.
        ours = [c for c in found if all(c.get(k) == desired[k] for k in same)][:1]
    if len(ours) > 1:
        raise EmailSetupError('Trigger sign-in found more than one Tervory email setting')
    if ours:
        config_id = ours[0]['id']
        api.request('PUT', '/admin/v1/smtp/' + config_id,
                    json={k: v for k, v in desired.items() if k != 'password'})
        api.request('PUT', '/admin/v1/smtp/' + config_id + '/password',
                    json={'password': desired['password']})
        active = ours[0].get('state') == 'SMTP_CONFIG_ACTIVE'
    else:
        config_id = api.request('POST', '/admin/v1/smtp', json=desired)['id']
        active = False
    if not active:
        api.request('POST', '/admin/v1/smtp/' + config_id + '/_activate', json={})
    return config_id


def founder_user_id(api, email):
    result = api.request('POST', '/v2/users', json={
        'query': {'limit': 2},
        'queries': [{'emailQuery': {'emailAddress': email, 'method': 'TEXT_QUERY_METHOD_EQUALS'}}],
    }).get('result', [])
    if len(result) != 1:
        raise EmailSetupError('Trigger sign-in founder account not found exactly once')
    return result[0]['userId']


def send_founder_setup_email(api, bootstrap: Path, env=os.environ):
    """Send the founder a link to set their own password, once."""
    marker = bootstrap / 'trigger-signin-setup-email.json'
    email = env.get('TRIGGER_SIGNIN_ADMIN_EMAIL', '')
    if not email:
        raise EmailSetupError('Trigger sign-in founder email missing')
    try:
        if json.loads(marker.read_text()).get('email') == email:
            return False
    except (FileNotFoundError, ValueError):
        pass
    user_id = founder_user_id(api, email)
    api.request('POST', '/v2/users/' + user_id + '/password_reset',
                json={'sendLink': {'notificationType': 'NOTIFICATION_TYPE_Email'}})
    marker.write_text(json.dumps({'email': email, 'user_id': user_id}) + '\n')
    return True


def configure_email(api, bootstrap: Path, env=os.environ):
    configure_smtp(api, env)
    return send_founder_setup_email(api, bootstrap, env)
