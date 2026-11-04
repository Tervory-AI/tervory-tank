// CI fixture transport for the shipped k6 scenarios; no socket or provider exists.
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const assert = require('node:assert/strict');
const source = fs.readFileSync(path.join(__dirname, 'rig_rooms.js'), 'utf8');
const rooms = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const fixture = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const values = new Map();
const tags = new Map();
const counters = new Map();
let passes = 0, fails = 0;
function percentile(numbers) {
  const sorted = [...numbers].sort((a, b) => a - b);
  const index = (sorted.length - 1) * 0.95;
  const low = Math.floor(index), high = Math.ceil(index);
  return sorted[low] + (sorted[high] - sorted[low]) * (index - low);
}
class Trend {
  constructor(name) { this.name = name; values.set(name, []); }
  add(value, scope) {
    assert.ok(Number.isFinite(value));
    values.get(this.name).push(value);
    const key = `${this.name}{room:${scope.room}}`;
    if (!tags.has(key)) tags.set(key, []);
    tags.get(key).push(value);
  }
}
function response(method, url, data, parameters) {
  const room = rooms.find(row => url.startsWith(row.url + '/'));
  assert.ok(room, 'No foreign or external fixture URL is permitted');
  assert.equal(parameters.headers['X-Rig-Key'], room.key);
  assert.equal(parameters.headers.Origin, 'http://rig-load.fixture');
  const path = url.slice(room.url.length);
  const key = method + room.room;
  const count = counters.get(key) || 0;
  counters.set(key, count + 1);
  let body;
  if (method === 'GET') {
    assert.equal(path, '/v1/rig/search?q=Core');
    body = fixture.search;
  } else {
    assert.equal(path, '/v1/rig/quote');
    const quote = JSON.parse(data);
    assert.deepEqual(Object.keys(quote).sort(), ['contact', 'product_id']);
    assert.equal(quote.product_id, 'CORE-1');
    assert.equal(quote.contact.email, 'load@example.test');
    body = fixture.quote;
  }
  return { status: 200, json: key => body[key], timings: { duration: (method === 'GET' ? 10 : 20) * (count + 1) } };
}
const context = {
  __ENV: { DURATION: '20s' }, __VU: 1, module: { exports: {} },
  open: path => { assert.equal(path, '/results/rooms.json'); return JSON.stringify(rooms); },
  http: { get: (url, p) => response('GET', url, null, p), post: (url, data, p) => response('POST', url, data, p) },
  Trend,
  check: (result, conditions) => {
    for (const condition of Object.values(conditions)) { if (condition(result)) passes++; else fails++; }
  },
  sleep: seconds => { assert.ok(seconds > 0); },
};
const code = source.replace(/^import .*;\s*$/gm, '').replace(/\bexport (?=(const|function))/g, '') +
  '\nmodule.exports = { options, search, quote, handleSummary };';
vm.createContext(context);
vm.runInContext(code, context);
const run = context.module.exports;
assert.equal(run.options.scenarios.search.vus, rooms.length);
assert.equal(run.options.scenarios.quote.vus, rooms.length);
for (let iteration = 0; iteration < 4; iteration++) {
  for (let room = 0; room < rooms.length; room++) {
    context.__VU = room + 1;
    run.search();
    run.quote();
  }
}
const metrics = { checks: { values: { passes, fails } }, http_req_failed: { values: { rate: 0 } } };
for (const [key, samples] of [...values, ...tags]) metrics[key] = { values: { 'p(95)': percentile(samples) } };
const output = run.handleSummary({ metrics });
assert.equal(Object.keys(output).length, 1);
assert.ok(output['/results/raw-k6.json']);
process.stdout.write(output['/results/raw-k6.json']);
