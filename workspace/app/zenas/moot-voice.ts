/** On-device speech only. No audio or provider keys leave this browser. */
import type { Hearing } from './moot-hearing-types';
import { REQUEST_TIMEOUT_MS } from './request';

type Segment = {text:string;start_ms:number;end_ms:number};
type Capture = {engine:'web_speech_local';language:string;segments:Segment[]};
type ResultEvent = {resultIndex:number;results:{length:number;[index:number]:{isFinal:boolean;0:{transcript:string}}}};
type Recognition = {processLocally:boolean;lang:string;continuous:boolean;interimResults:boolean;
  onresult:((event:ResultEvent)=>void)|null;onerror:(()=>void)|null;onend:(()=>void)|null;
  start:()=>void;stop:()=>void;abort:()=>void};
type Factory = {new():Recognition;available?:(options:{langs:string[];processLocally:true})=>Promise<string>;
  install?:(options:{langs:string[];processLocally:true})=>Promise<boolean>};
type LocalWindow = Window & {SpeechRecognition?:Factory;webkitSpeechRecognition?:Factory};
const ERROR='Room unavailable';

export class LocalHearingVoice {
  private recognition:Recognition|null=null;
  private generation=0;
  private field:HTMLTextAreaElement|null=null;
  private timer:ReturnType<typeof setTimeout>|null=null;
  private captured:Capture|null=null;
  private hearing:Hearing|null=null;
  private seen=new Set<string>();
  private enabled=false;
  private speaking=false;
  private playbackTimer:ReturnType<typeof setTimeout>|null=null;
  constructor(private fail:(message:string)=>void) {window.speechSynthesis?.getVoices();}

  private stop(abort=true) {
    if(this.timer)clearTimeout(this.timer);
    this.timer=null;
    this.field?.setAttribute('aria-busy','false');
    this.field?.removeAttribute('data-moot-listening');
    const recognition=this.recognition;
    this.recognition=null;
    if(abort){this.generation++;recognition?.abort();}else recognition?.stop();
  }
  close(){this.stop();if(this.playbackTimer)clearTimeout(this.playbackTimer);window.speechSynthesis?.cancel();this.enabled=false;this.speaking=false;this.captured=null;}
  metadata(text:string):Capture|undefined {
    return this.captured&&this.captured.segments.map(row=>row.text).join(' ')===text.trim()
      ? structuredClone(this.captured):undefined;
  }
  observe(hearing:Hearing|null){
    if(!hearing||this.hearing?.id!==hearing.id){this.close();this.captured=null;}
    if(this.hearing&&(this.hearing.floor!==hearing?.floor||this.hearing.seats[this.hearing.floor].epoch!==hearing?.seats[this.hearing.floor].epoch))this.stop();
    const prior=this.hearing;this.hearing=hearing;
    for(const turn of hearing?.transcript??[]){
      const key=hearing!.id+':'+turn.number;
      if(this.seen.has(key))continue;
      this.seen.add(key);
      if(prior?.id===hearing?.id&&this.enabled&&turn.seat==='judge')this.read(turn.text,turn.kind==='ruling'?hearing!.ruling:null);
    }
  }
  replayJudge(){
    this.enabled=true;
    const last=this.hearing?.transcript.filter(turn=>turn.seat==='judge').at(-1);
    if(last)this.read(last.text,last.kind==='ruling'?this.hearing!.ruling:null);
  }
  readPublished(text:string,ruling:Hearing['ruling']){this.enabled=true;this.read(text,ruling);}
  private read(text:string,ruling:Hearing['ruling']){
    this.stop();
    const synthesis=window.speechSynthesis;
    const voice=synthesis?.getVoices().filter(v=>v.localService&&v.lang.toLowerCase().startsWith('en')).sort((a,b)=>
      Number(b.lang.toLowerCase()===(this.hearing?.region==='za'?'en-za':'en-us'))-Number(a.lang.toLowerCase()===(this.hearing?.region==='za'?'en-za':'en-us')))[0];
    if(!voice||typeof SpeechSynthesisUtterance==='undefined'){this.fail(ERROR);return;}
    synthesis.cancel();
    const paragraphs=[text,...(ruling?[ruling.order,...ruling.reasons]:[])].filter(part=>part.trim());
    const generation=this.generation;let index=0;
    this.speaking=true;
    const next=()=>{
      if(generation!==this.generation)return;
      const paragraph=paragraphs[index++];
      if(!paragraph){this.speaking=false;return;}
      const utterance=new SpeechSynthesisUtterance(paragraph);
      utterance.voice=voice;utterance.lang=voice.lang;utterance.rate=1;
      const timer=setTimeout(()=>{if(generation!==this.generation)return;synthesis.cancel();this.speaking=false;this.fail(ERROR);},Math.max(REQUEST_TIMEOUT_MS,paragraph.length*100));
      this.playbackTimer=timer;
      utterance.onend=()=>{clearTimeout(timer);next();};
      utterance.onerror=()=>{clearTimeout(timer);if(generation===this.generation){this.speaking=false;this.fail(ERROR);}};
      try{synthesis.speak(utterance);}catch{clearTimeout(timer);this.speaking=false;this.fail(ERROR);}
    };
    next();
  }
  async dictate(field:HTMLTextAreaElement){
    if(this.recognition){this.stop(false);return;}
    if(!this.hearing||this.hearing.phase!=='hearing'||!this.hearing.my_seats.includes(this.hearing.floor)||this.speaking){this.fail(ERROR);return;}
    const Constructor=(window as LocalWindow).SpeechRecognition??(window as LocalWindow).webkitSpeechRecognition;
    if(!Constructor){this.fail(ERROR);return;}
    const recognition=new Constructor();
    if(!('processLocally' in recognition)){this.fail(ERROR);return;}
    let language=this.hearing.region==='za'?'en-ZA':'en-US';
    const generation=++this.generation;
    try{
      if(Constructor.available){
        const options={langs:[language],processLocally:true as const};
        let timer:ReturnType<typeof setTimeout>|undefined;
        try {
          await Promise.race([(async()=>{
            let available=await Constructor.available!(options);
            if(available==='unavailable'&&language==='en-ZA'){
              language='en-GB';options.langs=[language];available=await Constructor.available!(options);
            }
            if(available==='downloadable'&&Constructor.install)available=await Constructor.install(options)?'available':'unavailable';
            if(available!=='available')throw Error(ERROR);
          })(),new Promise<never>((_,reject)=>{timer=setTimeout(()=>reject(Error(ERROR)),REQUEST_TIMEOUT_MS);})]);
        }finally{if(timer)clearTimeout(timer);}
      }
      if(generation!==this.generation)return;
      window.speechSynthesis?.cancel();
      recognition.processLocally=true;recognition.lang=language;recognition.continuous=true;recognition.interimResults=true;
      this.recognition=recognition;this.field=field;this.enabled=true;
      const prefix=field.value.trim();
      const segments:Segment[]=this.captured&&prefix===this.captured.segments.map(s=>s.text).join(' ')?structuredClone(this.captured.segments):[];
      const offset=segments.at(-1)?.end_ms??0;
      const started=performance.now();let previous=offset;const finalized=new Set<number>();
      let appended='';
      recognition.onresult=event=>{
        if(generation!==this.generation)return;
        for(let i=event.resultIndex;i<event.results.length;i++){
          const result=event.results[i];if(!result.isFinal||finalized.has(i))continue;
          const text=result[0].transcript.trim();if(!text)continue;finalized.add(i);
          const ended=offset+Math.max(0,performance.now()-started);
          segments.push({text,start_ms:previous,end_ms:ended});previous=ended;
          appended=[appended,text].filter(Boolean).join(' ');
        }
        const text=[prefix,appended].filter(Boolean).join(' ');
        Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value')!.set!.call(field,text);
        field.dispatchEvent(new Event('input',{bubbles:true}));
        if(field.name==='text')this.captured=segments.map(row=>row.text).join(' ')===text?{engine:'web_speech_local',language,segments}:null;
      };
      recognition.onerror=()=>{if(generation===this.generation){this.stop();this.fail(ERROR);}};
      recognition.onend=()=>{if(generation===this.generation){this.stop();}};
      field.setAttribute('aria-busy','true');field.setAttribute('data-moot-listening','true');
      recognition.start();
      this.timer=setTimeout(()=>{this.stop();this.fail(ERROR);},REQUEST_TIMEOUT_MS);
    }catch{if(generation===this.generation){this.stop();this.fail(ERROR);}}
  }
}
