const assert = require('node:assert/strict');
const path = require('node:path');
const {workspace} = require('../command_acceptance_20261031/workspace_loader.cjs');
const tools = process.env.COMMAND_TEST_TOOLS;
const React = require(path.join(tools, 'react'));
const {renderToStaticMarkup} = require(path.join(tools, 'react-dom/server'));
let reads = 0;
const mocks = {
  react: React, 'react/jsx-runtime': require(path.join(tools, 'react/jsx-runtime')),
  'next/link': {__esModule: true, default: ({children, href, ...props}) => React.createElement('a', {href, ...props}, children)},
  'next/navigation': {useRouter: () => ({push(){}, refresh(){}}), notFound: () => {throw Error('not found');}},
  './actions': {proposeTrigger(){throw Error('No action on a read');}, confirmTrigger(){throw Error('No action on a read');}},
  '../actions': {readTrigger: async () => {reads++; return {}; }},
  '@/app/trigger-signin-provider': {TriggerSigninProvider: ({children})=>children},
  '@/lib/trigger-signin': {auth: async()=>{throw Error('Must not authenticate without settings');}},
  './review/founder': {isListedFounder:()=>false},
  './shell': {Shell:({children})=>children},
  './fonts': {inter:{variable:''},jost:{variable:''},mono:{variable:''}},
  './globals.css': {},
  './mobile-shell/install': {InstallShell:()=>null},
  '@/lib/mobile': {mobileIdentity:async()=>{throw Error('Must not fetch without settings');}},
  './mobile/account': {MobileAccount:()=>null},
};
const load = workspace({env: {}, fetch(){throw Error('No network');}, mocks});
const view = load('app/trigger/view.tsx').default;
const records = load('app/trigger/records.tsx').default;
const first = load('app/trigger/day-zero.tsx').FirstAction;
const render = (type, props) => renderToStaticMarkup(React.createElement(type, props));
for (const resource of ['leads','contacts','estimates','invoices']) {
  const html = render(records, {resource, data:{items:[]}, detail:false});
  assert.match(html, /<table/);
  assert.match(html, /<output>0<\/output>/);
  assert.match(html, /Create your first/);
  assert.doesNotMatch(html, /data-record/);
  assert.doesNotMatch(html, /Demo|Sample|Acme/);
}
for (const [area, section, action] of [
  ['marketing','channels','Connect Google'], ['marketing','composer','Create a draft'],
  ['marketing','calendar','Create a draft'], ['marketing','posts','Create a draft'],
  ['marketing','reviews','refresh reviews'], ['bot','inbox','start a chat'], ['bot','settings','Add an approved source'],
]) {
  const html = render(view, {area, section, data:{posts:[],reviews:[],sources:[],conversations:[]}});
  assert.match(html, /<output>0<\/output>/);
  assert.ok(html.includes(action));
  assert.match(html, /— · Confirm an action to create its receipt/);
  assert.doesNotMatch(html, /\/ledger\?entry=/);
  if(section==='calendar') assert.match(html, /trigger-calendar/);
}
assert.match(render(first,{area:'crm',section:'leads',data:{}}), /<output>—<\/output>/);
assert.equal(render(first,{area:'crm',section:'leads',data:{items:[{id:'placeholder'}]}}), '');
assert.equal(render(first,{area:'marketing',section:'channels',data:{gbp:{status:'connected'}}}), '');
(async()=>{
  const Page = load('app/trigger/[[...segments]]/page.tsx').default;
  const html = renderToStaticMarkup(await Page({params:Promise.resolve({segments:['crm','leads']})}));
  assert.match(html,/Missing setting: TANK_API_KEY/);
  assert.equal(reads,0);
  const Layout = load('app/layout.tsx').default;
  const layout = renderToStaticMarkup(await Layout({children:React.createElement('p',null,'private content')}));
  assert.match(layout,/TANK_API_KEY/);
  assert.match(layout,/TRIGGER_SIGNIN_WORKSPACE_SECRET/);
  assert.doesNotMatch(layout,/private content/);
  console.log('PASS: day-zero lists, calendar shape, counts, receipts, first actions and missing-key startup');
})().catch(e=>{console.error(e);process.exitCode=1;});
