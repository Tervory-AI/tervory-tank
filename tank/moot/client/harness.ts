import { Room, RoomEvent } from 'livekit-client';
import { Participant, Captions } from './participant';
Object.assign(window, { LiveKitRoom:Room, LiveKitRoomEvent:RoomEvent, MootParticipant:Participant, MootCaptions:Captions });
