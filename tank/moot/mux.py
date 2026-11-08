"""Mux Video API adapter. Only explicit operator actions may incur media costs.

No network call occurs at import/startup. HTTP clients are injected. Credentials,
stream keys, raw response bodies and upstream exception text never leave here.
"""
import base64
import hashlib
import hmac
import json
import time
import jwt
from .contracts import MediaError


class Mux:
    def __init__(self, client, journal, token_id='', token_secret='', webhook_secret='',
                 signing_id='', signing_private_key=''):
        self.client, self.journal = client, journal
        self.auth = (token_id, token_secret)
        self.webhook_secret = webhook_secret
        self.signing_id, self.signing_private_key = signing_id, signing_private_key

    async def _request(self, method, path, **kwargs):
        if not all(self.auth):
            raise MediaError('mux_unavailable')
        try:
            response = await self.client.request(method, 'https://api.mux.com/video/v1/' + path,
                auth=self.auth, timeout=10, **kwargs)
            if method == 'DELETE' and response.status_code == 404:
                return {}
            response.raise_for_status()
            return response.json().get('data', {}) if response.content else {}
        except Exception:
            # May include the RTMP stream key in upstream errors. Never forward.
            raise MediaError('mux_request_failed') from None

    async def create_stream(self, scope, request, *, founder, consented, allow_billable=False):
        if not founder:
            raise MediaError('operator_required')
        if not consented:
            raise MediaError('recording_consent_required')
        if not allow_billable:
            raise MediaError('billable_media_disabled')
        body = {'playback_policies': ['signed'], 'new_asset_settings': {'playback_policies': ['signed']},
                'passthrough': scope.room, 'reconnect_window': 60}
        prior = self.journal.claim(scope, request, body)
        if prior:
            return prior  # Started is uncertain; do not replay a billable creation.
        data = await self._request('POST', 'live-streams', json=body,
            headers={'Idempotency-Key': request})
        resource = data.get('id')
        if not isinstance(resource, str) or not resource:
            raise MediaError('invalid_mux_response')
        self.journal.bind(scope, resource, 'live_stream')
        # Never persist or return stream_key. Egress gets it only via private lookup.
        result = {'id': resource, 'status': data.get('status', 'idle'), 'published': False}
        self.journal.finish(scope, request, result)
        return result

    def verify_webhook(self, raw, signature, *, now=None):
        if not self.webhook_secret or len(raw) > 1024 * 1024:
            raise MediaError('invalid_webhook')
        try:
            fields = [part.strip().split('=', 1) for part in signature.split(',')]
            timestamps = [value for key, value in fields if key == 't']
            if len(timestamps) != 1:
                raise ValueError()
            timestamp = timestamps[0]
            if abs((time.time() if now is None else now) - int(timestamp)) > 300:
                raise ValueError()
            expected = hmac.new(self.webhook_secret.encode(), timestamp.encode() + b'.' + raw,
                hashlib.sha256).hexdigest()
            if not any(hmac.compare_digest(expected, value) for key, value in fields if key == 'v1'):
                raise ValueError()
            event = json.loads(raw)
            if not isinstance(event, dict) or not isinstance(event.get('id'), str) or not event['id']:
                raise ValueError()
            if not isinstance(event.get('type'), str) or not isinstance(event.get('data'), dict):
                raise ValueError()
            return event
        except (ValueError, TypeError):
            raise MediaError('invalid_webhook') from None

    def webhook(self, raw, signature, *, now=None):
        event = self.verify_webhook(raw, signature, now=now)
        data = event['data']
        # A new recording asset must reference an already bound stream. Account
        # passthrough alone never authorizes a resource to enter a hearing.
        if event['type'].startswith('video.asset.') and data.get('live_stream_id'):
            with self.journal.connect() as db:
                row = db.execute("SELECT * FROM mux_bindings WHERE resource=? AND kind='live_stream'",
                    (data['live_stream_id'],)).fetchone()
            if row:
                from .contracts import Scope
                _, region, tenant, hearing = row['room'].split(':')
                self.journal.bind(Scope(tenant, region, hearing), data['id'], 'asset')
        return self.journal.webhook(event)

    def playback(self, scope, resource, *, permitted, now=None):
        item = self.journal.resource(scope, resource)
        if item['state'] not in {'ready', 'live', 'paused', 'ended'} or not item['playback']:
            raise MediaError('playback_unavailable')
        return self.signed_playback(item['playback'], permitted=permitted,
            published=bool(item['published']), now=now)

    def signed_playback(self, playback_id, *, permitted, published, now=None):
        if not permitted or not published:
            raise MediaError('playback_not_published')
        if not self.signing_id or not self.signing_private_key:
            raise MediaError('mux_signing_unavailable')
        # Mux signing-key API returns the PEM as base64. Never expose that value.
        try:
            pem = base64.b64decode(self.signing_private_key, validate=True)
            token = jwt.encode({'sub': playback_id, 'aud': 'v',
                'exp': int(time.time() if now is None else now) + 120}, pem,
                algorithm='RS256', headers={'kid': self.signing_id})
        except Exception:
            raise MediaError('mux_signing_unavailable') from None
        return f'https://stream.mux.com/{playback_id}.m3u8?token={token}'

    async def delete(self, scope, resource, kind):
        with self.journal.connect() as db:
            row = db.execute('SELECT * FROM mux_bindings WHERE resource=? AND room=? AND kind=?',
                (resource, scope.room, kind)).fetchone()
        if not row:
            raise MediaError('not_found')
        await self._request('DELETE', ('assets/' if kind == 'asset' else 'live-streams/') + resource)

    async def egress_output(self, scope, stream_id, *, consented, allow_billable=False):
        if not consented:
            raise MediaError('recording_consent_required')
        if not allow_billable:
            raise MediaError('billable_media_disabled')
        with self.journal.connect() as db:
            row = db.execute("SELECT 1 FROM mux_bindings WHERE room=? AND resource=? AND kind='live_stream'",
                (scope.room, stream_id)).fetchone()
        if row is None:
            raise MediaError('not_found')
        data = await self._request('GET', 'live-streams/' + stream_id)
        key = data.get('stream_key')
        if not isinstance(key, str) or not key or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in key):
            raise MediaError('invalid_mux_response')
        from livekit import api
        # Private server-to-egress object. Never serialize it to a browser/error/log.
        return api.StreamOutput(protocol=api.StreamProtocol.RTMP,
            urls=['rtmps://global-live.mux.com:443/app/' + key])

    async def disable_stream(self, scope, stream_id):
        with self.journal.connect() as db:
            row = db.execute("SELECT 1 FROM mux_bindings WHERE room=? AND resource=? AND kind='live_stream'",
                (scope.room, stream_id)).fetchone()
        if row is None:
            raise MediaError('not_found')
        await self._request('PUT', 'live-streams/' + stream_id + '/disable')
