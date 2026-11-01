// Actual page and access helpers, isolated from Clerk and all network services.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const ts = require(path.join(root, 'workspace/node_modules/typescript'));
function load(file, mocks) {
  const code = ts.transpileModule(fs.readFileSync(path.join(root, file), 'utf8'), {
    compilerOptions: {module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022},
  }).outputText;
  const exports = {};
  vm.runInNewContext(code, {exports, process: {env: {TERVORY_ADMIN_USER_IDS: 'founder'}}, require(name) {
    if (name in mocks) return mocks[name];
    if (name === 'server-only' || name.endsWith('.css')) return {};
    throw Error(`Unmocked dependency ${name}`);
  }});
  return exports;
}
let userId, orgRole, reads = [];
const navigation = {notFound() {throw Error('404');}};
const founder = load('workspace/app/review/founder.ts', {});
const access = load('workspace/app/review/access.ts', {
  './founder': founder, 'next/navigation': navigation,
  '@clerk/nextjs/server': {
    auth: async () => ({userId, orgRole}),
    clerkClient: async () => ({users: {getUser: async () => ({publicMetadata: {jurisdiction: 'us', admission_no: 'fixture-admission'}})}}),
  },
});
const tenant = {activeTenant: async () => {reads.push('tenant'); return {orgName: 'Fixture'};}};
const gold = load('workspace/app/skala/gold/access.ts', {
  '@clerk/nextjs/server': {auth: async () => ({userId})},
  'next/navigation': navigation, '@/app/review/access': access, '@/lib/tenant': tenant,
});
const page = load('workspace/app/tank/page.tsx', {
  '../skala/gold/access': gold, '@/app/review/access': access, 'next/navigation': navigation,
  'react/jsx-runtime': {jsx: (type, props) => ({type, props})},
  './graduation-panel': {GraduationPanel: 'GraduationPanel'}, './view': {TankView: 'TankView'},
  '@/lib/tenant': tenant,
  '@/lib/tank': {
    listRoster: async () => {reads.push('roster'); return [];},
    trainingGraduation: async () => {reads.push('graduation'); return [];},
  },
  './workers-server': {listWorkers: async () => {reads.push('workers'); return {available: true, tasks: []};}},
}).default;
(async () => {
  for (const [user, role] of [[null, null], ['customer', 'org:member'], ['reviewer', 'org:reviewer']]) {
    userId = user; orgRole = role; reads = [];
    await assert.rejects(page(), /404/);
    assert.deepEqual(reads, [], `${user} must be denied before all reads`);
  }
  // Reviewer admission stays valid in its legitimate review and gold corridors.
  assert.equal((await access.requireReviewer()).founder, false);
  assert.equal((await gold.goldIdentity('platform')).role, 'reviewer');
  userId = 'founder'; orgRole = 'org:member'; reads = [];
  assert.equal((await page()).type, 'TankView');
  assert.deepEqual(reads, ['tenant', 'roster', 'workers', 'graduation']);
  console.log('Tank: founder renders; signed-out/customer/admitted reviewer denied before reads; reviewer gold/review admission preserved.');
})().catch(error => {console.error(error); process.exitCode = 1;});
