// Pinned local k6 only; no cloud output and no real stores, models or email.
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';
const rooms = JSON.parse(open('/results/rooms.json'));
const searchTime = new Trend('rig_search_ms', true);
const quoteTime = new Trend('rig_quote_ms', true);
const perRoom = {};
for (const room of rooms) {
  perRoom[`rig_search_ms{room:${room.room}}`] = ['max>=0'];
  perRoom[`rig_quote_ms{room:${room.room}}`] = ['max>=0'];
}
export const options = {
  scenarios: {
    search: { executor: 'constant-vus', vus: rooms.length, duration: __ENV.DURATION || '60s', exec: 'search' },
    quote: { executor: 'constant-vus', vus: rooms.length, duration: __ENV.DURATION || '60s', exec: 'quote' },
  },
  thresholds: { checks: ['rate==1'], http_req_failed: ['rate==0'], ...perRoom },
  summaryTrendStats: ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)'],
};
function current() { return rooms[(__VU - 1) % rooms.length]; }
function parameters(room) {
  return { headers: { 'X-Rig-Key': room.key, Origin: 'http://rig-load.fixture', 'Content-Type': 'application/json' }, tags: { room: String(room.room) } };
}
export function search() {
  const room = current();
  const result = http.get(room.url + '/v1/rig/search?q=Core', parameters(room));
  searchTime.add(result.timings.duration, { room: String(room.room) });
  check(result, { 'store search succeeds': r => r.status === 200 && Array.isArray(r.json('results')) && r.json('results').length === 3 });
  sleep(1.1); // Respect the production per-client browse budget.
}
export function quote() {
  const room = current();
  const result = http.post(room.url + '/v1/rig/quote', JSON.stringify({ product_id: 'CORE-1', contact: { name: 'Load fixture', email: 'load@example.test' } }), parameters(room));
  quoteTime.add(result.timings.duration, { room: String(room.room) });
  check(result, { 'store quote is retained': r => r.status === 200 && /^req_/.test(r.json('request_id')) });
  sleep(16); // Keep below five quotes/minute/client; no abuse-control bypass.
}
export function handleSummary(data) { return { '/results/raw-k6.json': JSON.stringify(data, null, 2) }; }
