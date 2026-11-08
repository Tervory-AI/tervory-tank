import { Room, RoomEvent, Track, type RemoteTrack, type RemoteParticipant } from 'livekit-client';

export type Grant = {url:string;token:string;identity:string;epoch:number;expires_in:number};
export type Seat = 'applicant'|'respondent'|'judge';
export type Hearing = {id:string;region:string;revision:number;floor:Seat;current_issue:number;
  pending_question:unknown;transcript:unknown[];seats:Record<Seat,{kind:'human'|'ai';epoch:number}>;my_seats:Seat[]};

/** Separate Moot transport controller. It never converts captions into legal turns. */
export class Participant {
  room:Room|null=null;
  state:'disconnected'|'connecting'|'connected'|'reconnecting'|'unavailable'='disconnected';
  private epoch=-1;
  private generation=0;
  hearing:Hearing|null=null;
  constructor(private seat:Seat, private load:()=>Promise<Hearing>,
    private grant:()=>Promise<Grant>, private attach:(track:RemoteTrack, participant:RemoteParticipant)=>void,
    private changed:()=>void=()=>{}){}

  async connect(){
    await this.close();
    const generation=++this.generation;
    this.state='connecting';this.changed();
    const room=new Room({adaptiveStream:true,dynacast:true});this.room=room;
    room.on(RoomEvent.TrackSubscribed,(track,_publication,participant)=>this.attach(track,participant));
    room.on(RoomEvent.TrackUnsubscribed,track=>track.detach().forEach(element=>element.remove()));
    room.on(RoomEvent.Reconnecting,()=>{this.state='reconnecting';this.changed();});
    room.on(RoomEvent.Reconnected,()=>{void this.refresh().catch(()=>this.close());});
    room.on(RoomEvent.Disconnected,()=>{this.state='disconnected';this.changed();});
    try{
      const hearing=await this.load();
      if(!hearing.my_seats.includes(this.seat)||hearing.seats[this.seat].kind!=='human')throw Error('seat_revoked');
      const grant=await this.grant();
      if(generation!==this.generation)return;
      this.epoch=grant.epoch;this.hearing=hearing;
      await room.connect(grant.url,grant.token,{autoSubscribe:true});
      if(generation!==this.generation){await room.disconnect();return;}
      await this.refresh();
      this.state='connected';this.changed();
    }catch(error){
      console.warn(error instanceof Error ? error.name : "media_failed");
      await room.disconnect();
      if(generation===this.generation){this.state='unavailable';this.changed();}
      throw Error('media_unavailable');
    }
  }
  async refresh(){
    const hearing=await this.load();
    this.hearing=hearing;
    if(!hearing.my_seats.includes(this.seat)||hearing.seats[this.seat].kind!=='human'||hearing.seats[this.seat].epoch!==this.epoch){
      await this.close();throw Error('seat_revoked');
    }
    // Keep the exact authoritative transcript, issue and pending question.
    this.state='connected';this.changed();return hearing;
  }
  async microphone(enabled:boolean){await this.refresh();await this.room?.localParticipant.setMicrophoneEnabled(enabled);}
  async camera(enabled:boolean){await this.refresh();await this.room?.localParticipant.setCameraEnabled(enabled);}
  async device(kind:'audioinput'|'videoinput'|'audiooutput',id:string){await this.refresh();await this.room?.switchActiveDevice(kind,id);}
  async devices(kind:'audioinput'|'videoinput'|'audiooutput'){return Room.getLocalDevices(kind);}
  tracks(){return [...(this.room?.localParticipant.trackPublications.values()??[])].filter(p=>p.source===Track.Source.Camera||p.source===Track.Source.Microphone);}
  async close(){this.generation++;const room=this.room;this.room=null;await room?.disconnect();this.state='disconnected';this.changed();}
}

/** Strict cursor: transport delivery can repeat or arrive out of order. */
export class Captions {
  cursor=0;
  private pending=new Map<number,{seq:number;seat:Seat;text:string;final:boolean}>();
  constructor(private accept:(event:{seq:number;seat:Seat;text:string;final:boolean})=>void){}
  push(event:{seq:number;seat:Seat;text:string;final:boolean}){
    if(!Number.isSafeInteger(event.seq)||event.seq<=this.cursor||event.seq>this.cursor+500)return;
    if(!['applicant','respondent','judge'].includes(event.seat)||typeof event.text!=='string'||event.text.length>24000)return;
    this.pending.set(event.seq,event);
    while(this.pending.has(this.cursor+1)){
      const next=this.pending.get(++this.cursor)!;this.pending.delete(this.cursor);this.accept(next);
    }
  }
}
