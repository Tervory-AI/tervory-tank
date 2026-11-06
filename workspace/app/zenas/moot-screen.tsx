'use client';
import {useEffect,useState} from 'react';
import {zenasFetch} from '@/app/zenas/request';
import {MOOT_PARTS} from '@/app/zenas/moot';
import {SEAT_LABELS,type Hearing,type Seat} from '@/app/zenas/moot-hearing-types';
import {ReasonTrace} from '@/app/zenas/moot-court';
import {safeHref} from '@/app/prices/format';

type Screen = {kind:string;id:string;revision:number;title:string;phase:string;floor:Seat;
  problem:Hearing['problem'];transcript:Hearing['transcript'];ruling:Hearing['ruling'];reveal?:string;
  authorities:Hearing['problem']['authorities'];
  feedback:null|{court_holding:string;fairness:{reading:string};counsel:{seat:Seat;arguments:{number:number;text:string;reasoning?:Record<string,unknown>}[];authorities:Hearing['problem']['authorities']}[]}};

export function MootScreen({id,kind}:{id:string;kind:'bench'|'citations'|'feedback'}){
  const [screen,setScreen]=useState<Screen|null>(null),[error,setError]=useState(false);
  useEffect(()=>{
    let stopped=false,inflight=false;const controller=new AbortController();
    async function refresh(){
      if(inflight)return;inflight=true;
      try{
        const response=await zenasFetch(`/api/zenas/moot/hearings/${id}?screen=${kind}`,{signal:controller.signal});
        const result=await response.json();if(stopped)return;
        if(!response.ok||!result.screen){setError(true);setScreen(null);return;}
        setScreen(current=>current&&current.revision>result.screen.revision?current:result.screen);setError(false);
      }catch{if(!stopped){setError(true);setScreen(null);}}finally{inflight=false;}
    }
    function print(){document.querySelectorAll<HTMLDetailsElement>('.zn-moot-screen details').forEach(detail=>{detail.open=true;});}
    window.addEventListener('beforeprint',print);
    void refresh();const timer=setInterval(()=>void refresh(),1000);
    return()=>{stopped=true;controller.abort();clearInterval(timer);window.removeEventListener('beforeprint',print);};
  },[id,kind]);
  const title=kind==='bench'?'The hearing':kind==='citations'?'Authorities':'Reasoning';
  const caption=screen?.transcript.filter(turn=>turn.seat==='judge').at(-1)?.text;
  return <main className="zn zn-moot-screen"><section className="zn-moot"><h1>Moot Court</h1><h2>{title}</h2>
    {error?<p role="alert">Room unavailable</p>:!screen?<p>{MOOT_PARTS[0].empty}</p>:<>
      <h3>{screen.title}</h3>
      {kind==='bench'&&<><p role="status" aria-live="polite">{caption||MOOT_PARTS[0].empty}</p>
        {screen.ruling&&<><h2>Judgment</h2><h3>{screen.ruling.order}</h3><ol>{screen.ruling.reasons.map((reason,i)=><li key={i}>{reason}</li>)}</ol></>}</>}
      {kind==='citations'&&<section aria-label="Authorities">{screen.authorities.length===0?<p>0 · {MOOT_PARTS[0].empty}</p>:screen.authorities.map(authority=><article key={authority.id}><h3>{safeHref(authority.source_url)?<a href={authority.source_url}>{authority.name}</a>:authority.name}</h3><blockquote>{authority.quote}</blockquote><p>{authority.weight||'unknown'}</p></article>)}</section>}
      {kind==='feedback'&&(!screen.feedback?<p>{MOOT_PARTS[2].empty}</p>:<>
        {screen.feedback.counsel.map(counsel=><article className="zn-card" key={counsel.seat}><h2>{SEAT_LABELS[counsel.seat]}</h2>
          {counsel.arguments.map(argument=><section key={argument.number}><p>{argument.text}</p>{argument.reasoning&&<details><summary>Reasoning</summary><ReasonTrace trace={argument.reasoning} problem={screen.problem}/></details>}</section>)}
          <h3>Authorities</h3>{counsel.authorities.map(authority=><p key={authority.id}>{safeHref(authority.source_url)?<a href={authority.source_url}>{authority.name}</a>:authority.name}: {authority.weight||'unknown'}</p>)}</article>)}
        {screen.ruling&&<><h2>Judgment</h2><p>Order: {screen.ruling.order}</p><ol>{screen.ruling.reasons.map((reason,i)=><li key={i}>{reason}</li>)}</ol></>}
        <h2>What the court actually held</h2><p>{screen.feedback.court_holding}</p><h2>Fairness check</h2><p>{screen.feedback.fairness.reading}</p>
      </>)}
    </>}
  </section></main>;
}
