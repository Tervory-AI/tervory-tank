import assert from 'node:assert/strict';
import {test} from 'node:test';
import {renderToStaticMarkup as render} from 'react-dom/server';
import {CalibrationView, BriefView} from '../workspace/app/market-lab/h7-view';
import {Warnings} from '../workspace/app/market-lab/warnings';
import {SourceDocumentView} from '../workspace/app/market-lab/source-view';
import {MarketLabView, PluginsDialog} from '../workspace/app/market-lab/view';
import {QuarantinePanel} from '../workspace/app/market-lab/quarantine-view';
import BriefsPage from '../workspace/app/market-lab/briefs/page';

function noInventedData(html: string) {
  assert.ok(!/placeholder saved|illustrative|demo|sample data|75\.0%|71\.4%/i.test(html));
  assert.ok(!html.includes('data-confidence='));
}

test('empty calibration retains axes with unknown metrics, no dots and a first action', () => {
  for(const value of [{state:'empty'}, {state:'ready',data:[]}] as const) {
    const html=render(<CalibrationView value={value as any}/>);
    assert.match(html,/desktop-imgAxis.svg/);
    assert.match(html,/mobile-imgAxis.svg/);
    assert.match(html,/Confidence — \/ Actual hit rate —/);
    assert.match(html,/Refresh feeds to collect observations; calibration fills after predictions resolve./);
    noInventedData(html);
  }
});
test('loading and failed calibration never present a fabricated empty measurement', () => {
  for(const state of ['loading','error'] as const) {
    const html=render(<CalibrationView value={{state}}/>);
    assert.ok(!html.includes('imgAxis.svg'));
    assert.match(html,/Samples: —/);
    noInventedData(html);
  }
});
test('empty warnings and review lists give a first action without fake rows', () => {
  const warnings=render(<Warnings data={{warnings:[],history:[]} as any}/>);
  assert.match(warnings,/No warnings yet/);assert.match(warnings,/Refresh feeds/);noInventedData(warnings);
  const review=render(<QuarantinePanel batches={[]}/>);
  assert.equal((review.match(/<p>0<\/p>/g)||[]).length,2);
  assert.match(review,/Refresh feeds to collect records for review/);noInventedData(review);
});
test('monthly list and missing brief keep empty state actionable', async () => {
  const fetch=globalThis.fetch;
  try {
    globalThis.fetch=async()=>Response.json({records:[]});
    const html=render(await BriefsPage());
    assert.match(html,/No monthly briefs yet/);assert.match(html,/Refresh feeds to collect observations for the next monthly brief/);
    noInventedData(html);
    assert.match(render(<BriefView value={{state:'empty'}}/>),/Open Monthly briefs to select a saved brief/);
  } finally {globalThis.fetch=fetch;}
});
test('receipt and cited-source emptiness is explicit rather than a fabricated delivery', () => {
  const html=render(<BriefView value={{state:'ready',data:{name:'Saved brief',made_at:'2026-11-05T00:00:00Z',summary:'',deliveries:[],sources:[]} as any}}/>);
  assert.match(html,/Delivery: —/);assert.match(html,/Enable alerts to receive delivery receipts/);
  assert.match(html,/0 · Sources cited/);assert.match(html,/Refresh feeds to collect observations for cited briefs/);
  assert.ok(!html.includes('Email · Sent'));noInventedData(html);
});
test('an empty stored document has no fabricated table rows or pagination', () => {
  const html=render(<SourceDocumentView source={{name:'Empty source',fetched_at:'2026-11-05T00:00:00Z',offset:0,page_size:100,point_count:0,event_count:0,points:[],events:[],downloads:[]} as any}/>);
  assert.match(html,/0 stored observations. Refresh feeds to collect data/);
  assert.ok(!html.includes('<tbody>'));assert.ok(!html.includes('Page 1 of'));noInventedData(html);
  const upload=render(<SourceDocumentView source={{name:'Empty file',kind:'uploaded_file',fetched_at:'2026-11-05T00:00:00Z',passages:[],page_size:100} as any}/>);
  assert.match(upload,/0 passages. Choose files in Plugins/);noInventedData(upload);
});
test('new-client counters show zero and actions, transport errors show unknown', () => {
  const model={onCount:0,linkedCount:0,onEmpty:true,loadError:false,cards:[],featured:[],off:[],groups:[],refreshedLabel:'Not refreshed yet'};
  const props={model,plugins:{state:'off'},envKeys:{},refresh:async()=>{},workspaceName:null} as any;
  const html=render(<MarketLabView {...props}/>);
  assert.equal((html.match(/class="ml-count">0</g)||[]).length,2);
  assert.match(html,/Choose Refresh feeds to collect data/);assert.match(html,/Use Add link in Plugins/);noInventedData(html);
  const failed=render(<MarketLabView {...props} model={{...model,loadError:true}}/>);
  assert.equal((failed.match(/class="ml-count">—</g)||[]).length,2);
});

test('empty plugin lists name the first action for files, links and connections', () => {
  const plugins={enabled:true,message:null,secrets:[],files:[],links:[],connections:[]};
  for(const [tab,action] of [['Files','Choose files to upload your first source'],['Source links','Use Add link to connect a public source'],['Connections','Add a connection to read your source']] as const) {
    const html=render(<PluginsDialog open tab={tab} plugins={plugins} envKeys={{} as any} onTab={()=>{}} onClose={()=>{}}/>);
    assert.ok(html.includes(action));noInventedData(html);
  }
});
