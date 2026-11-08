"""Pinned LiveKit API. Browser grants cannot administer, record, or send data."""
from datetime import timedelta
import json
from livekit import api
from .contracts import authorize_projection, MediaError


class Rooms:
    def __init__(self, url, public_url, key, secret):
        self.url, self.public_url, self.key, self.secret = url, public_url, key, secret

    async def create(self, scope):
        async with api.LiveKitAPI(self.url, self.key, self.secret) as client:
            return await client.room.create_room(api.CreateRoomRequest(
                name=scope.room, empty_timeout=120, max_participants=8))

    def grant(self, scope, user, seat, projection):
        identity = authorize_projection(scope, user, seat, projection)
        token = (api.AccessToken(self.key, self.secret).with_identity(identity)
            .with_ttl(timedelta(seconds=60)).with_metadata(json.dumps({'seat': seat,
                'epoch': projection['seats'][seat]['epoch']}))
            .with_grants(api.VideoGrants(room_join=True, room=scope.room,
                can_publish=True, can_subscribe=True, can_publish_data=False,
                can_publish_sources=['camera', 'microphone'], can_update_own_metadata=False)))
        return {'url': self.public_url, 'token': token.to_jwt(), 'identity': identity,
                'epoch': projection['seats'][seat]['epoch'], 'expires_in': 60}

    async def revoke(self, scope, identity):
        # Removing a participant revokes its current token in LiveKit. New grants
        # always re-read the authoritative seat epoch and membership projection.
        async with api.LiveKitAPI(self.url, self.key, self.secret) as client:
            await client.room.remove_participant(api.RoomParticipantIdentity(
                room=scope.room, identity=identity))

    async def record(self, scope, *, consented, request):
        if not consented:
            raise MediaError('recording_consent_required')
        if request.room_name != scope.room:
            raise MediaError('not_found')
        async with api.LiveKitAPI(self.url, self.key, self.secret) as client:
            return await client.egress.start_room_composite_egress(request)

    async def stop_recording(self, egress_id):
        async with api.LiveKitAPI(self.url, self.key, self.secret) as client:
            return await client.egress.stop_egress(api.StopEgressRequest(egress_id=egress_id))
