// Render the existing Command window with the merged bot adapter's wire shape.
const assert = require('node:assert/strict');
const path = require('node:path');
const modules = path.resolve(__dirname, '../../workspace/node_modules');
const React = require(path.join(modules, 'react'));
const { renderToStaticMarkup } = require(path.join(modules, 'react-dom/server'));
const jsx = require(path.join(modules, 'react/jsx-runtime'));
const { workspace } = require('../command_acceptance_20261031/workspace_loader.cjs');
const tool = 'trigger.bot.source.add';
const card = {card_id: 'bot-card', kind: 'other', tool, summary: tool, status: 'pending',
  arguments: {kind: 'website', title: 'Store', url: 'https://store.invalid/'}};
const thread = {thread_id: 'thread', title: 'Store', squad: 'trigger', status: 'open'};
const load = workspace({env: {}, fetch: async () => {throw Error('no network');}, mocks: {
  'react': {...React, useEffect: () => {}, useRef: value => ({current: value}),
    useState: value => [value, () => {}]},
  'react/jsx-runtime': jsx,
  '../squad-links': {SquadLinks: () => null, SQUAD_MEMBERS: []},
  './assets/done.svg': 'done.svg', './assets/attention.svg': 'attention.svg',
  './assets/planned.svg': 'planned.svg', './window.css': {},
}});
const presentation = load('app/chats/presentation.ts');
assert(presentation.visibleCard(card, false));
const projected = presentation.presentCard(card, false);
assert(projected.targets.some(target => target.href === card.arguments.url));
// Inject a saved snapshot into hooks; component, visibility and Confirm rendering are real.
let hook = 0;
const renderer = workspace({env: {}, fetch: async () => {throw Error('no network');}, mocks: {
  'react': {...React, useEffect: () => {}, useRef: value => ({current: value}),
    useState: value => [++hook === 4 ? 'thread' : hook === 5 ?
      {thread, messages: [], steps: [], cards: [projected]} : value, () => {}]},
  'react/jsx-runtime': jsx,
  '../squad-links': {SquadLinks: () => null, SQUAD_MEMBERS: []},
  './assets/done.svg': 'done.svg', './assets/attention.svg': 'attention.svg',
  './assets/planned.svg': 'planned.svg', './window.css': {},
}});
const {CommandWindow} = renderer('app/chats/window.tsx');
const html = renderToStaticMarkup(CommandWindow({initialThreads: [thread], models: [],
  founder: false, account: 'Store', initialTools: [tool]}));
assert.equal(projected.targets.find(target => target.label === 'URL').href, new URL(card.arguments.url).href);
assert(html.includes('>Confirm</button>'));
assert(html.includes('NEEDS YOUR OK'));
console.log('PASS bot Confirm card renders in existing signed-in Command window');
