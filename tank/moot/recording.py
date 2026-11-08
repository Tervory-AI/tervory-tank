"""Consent and local object retention. No recording is started implicitly."""
from datetime import datetime, timezone
from pathlib import Path
from .contracts import MediaError


class Recording:
    def __init__(self, journal):
        self.journal = journal

    @staticmethod
    def consent_key(seat, epoch):
        return f'{seat}:{epoch}'

    def consent(self, scope, request, revision, *, seat, user, projection, accepted):
        if seat not in projection.get('my_seats', []):
            raise MediaError('seat_not_owned')
        controller = projection['seats'][seat]
        if controller['kind'] != 'human':
            raise MediaError('seat_not_owned')
        return self.journal.append(scope, request, revision, {'kind': 'recording_consent',
            'seat': seat, 'epoch': controller['epoch'], 'accepted': accepted is True})

    def allowed(self, scope, projection):
        values = {}
        for event in self.journal.events(scope):
            if event.get('kind') == 'recording_consent':
                values[self.consent_key(event['seat'], event['epoch'])] = event['accepted']
        return all(controller['kind'] == 'ai' or values.get(self.consent_key(seat, controller['epoch'])) is True
            for seat, controller in projection['seats'].items())

    @staticmethod
    def local_delete(root, relative, *, due_at, now=None):
        now = datetime.now(timezone.utc) if now is None else now
        if now < due_at:
            raise MediaError('retention_not_due')
        base = Path(root).resolve(strict=True)
        path = (base / relative).resolve()
        if not path.is_relative_to(base) or path == base:
            raise MediaError('invalid_recording_path')
        if path.is_file():
            path.unlink()
