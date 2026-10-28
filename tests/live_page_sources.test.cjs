/** Offline transport tests of the actual route components; never a live data source. */
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const { createRequire } = require('node:module');
const root = path.resolve(__dirname, '..');
const workspace = path.join(root, 'workspace');
const deps = createRequire(path.join(workspace, 'package.json'));
const ts = deps('typescript');
const React = deps('react');
const { renderToStaticMarkup } = deps('react-dom/server');
const forbidden = /Fixture|\[TEST\]|CVE-2024-0000|ThreatPayload|00000000-0000-0000-0000/;
const id = 'c634c3df-a3e3-4d25-86ea-0286d63ba4c9';
const otherId = 'b634c3df-a3e3-4d25-86ea-0286d63ba4c9';
const match = { matchId: id, published: true, title: 'Published civil appeal', fairnessReading: 'split', judgmentOrder: 'appeal_dismissed', reveal: '' };

// Compile with the workspace's installed compiler, replacing only framework/transport boundaries.
function harness(fetch) {
  const cache = new Map();
  const calls = [];
  const notFound = () => { throw new Error('NEXT_NOT_FOUND'); };
  const action = async () => null;
  function load(filename) {
    filename = path.resolve(filename);
    if (cache.has(filename)) return cache.get(filename).exports;
    const module = { exports: {} };
    cache.set(filename, module);
    const js = ts.transpileModule(fs.readFileSync(filename, 'utf8'), {
      fileName: filename,
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
    }).outputText;
    function requireSource(spec) {
      if (spec === 'server-only' || spec.endsWith('.css')) return {};
      if (spec === 'next/link') return { __esModule: true, default: ({ children, ...props }) => React.createElement('a', props, children) };
      if (spec === 'next/navigation') return { notFound };
      if (spec === '@clerk/nextjs/server') return { auth: async () => ({ userId: 'offline-founder' }) };
      if (spec === '@/lib/admin') return { isFounder: () => true };
      if (spec === './actions') return { look: action, resolve: action, shieldAction: action };
      if (spec === './quarantine-actions') return { releaseBatch: action, rejectBatch: action, removeBatch: action };
      if (spec.startsWith('.') || spec.startsWith('@/')) {
        const base = spec.startsWith('@/') ? path.join(workspace, spec.slice(2)) : path.resolve(path.dirname(filename), spec);
        const resolved = ['', '.ts', '.tsx'].map(ext => base + ext).find(p => fs.existsSync(p) && fs.statSync(p).isFile());
        if (!resolved) throw new Error(`Module not found: ${spec}`);
        return load(resolved);
      }
      return deps(spec);
    }
    new Function('require', 'module', 'exports', 'fetch', 'process', js)(requireSource, module, module.exports,
      async (url, options) => { calls.push({ url: String(url), method: options?.method }); return fetch(url, options); },
      { env: {} });
    return module.exports;
  }
  return { load: name => load(path.join(workspace, name)), calls };
}
const response = (body, status = 200) => new Response(JSON.stringify(body), { status });
const failed = () => response({}, 503);
const render = async (h, page, props) => renderToStaticMarkup(await h.load(page).default(props));

// These replace the old tests that asserted a production fixture store was public.
test('Moot index reads published room matches through Tank, with US home and no cache', async () => {
  const h = harness((url, options) => {
    assert.equal(options.cache, 'no-store');
    assert.equal(new URL(url).pathname, '/v1/zenas/moot/published');
    assert.equal(new URL(url).searchParams.get('home_region'), 'us-east');
    return response({ matches: [match, { ...match, matchId: otherId, published: false }, { ...match, title: 'Fixture appeal [TEST]' }] });
  });
  const html = await render(h, 'app/moot/page.tsx');
  assert.match(html, new RegExp(`/moot/${id}`));
  assert.doesNotMatch(html, new RegExp(otherId));
  assert.doesNotMatch(html, forbidden);
});

test('Moot uses its existing empty state for empty, malformed, and unavailable replies', async () => {
  for (const fetch of [() => response({ matches: [] }), () => response({ matches: [{}] }), failed, () => { throw new Error('offline'); }]) {
    const html = await render(harness(fetch), 'app/moot/page.tsx');
    assert.match(html, /No published matches yet\./);
    assert.doesNotMatch(html, forbidden);
  }
});

test('Moot detail calls the real reader and refuses private, fixture, missing, and invalid matches', async () => {
  const h = harness(url => {
    assert.equal(new URL(url).searchParams.get('match_id'), id);
    return response({ matches: [match] });
  });
  const html = await render(h, 'app/moot/[match]/page.tsx', { params: Promise.resolve({ match: id }) });
  assert.match(html, /Published civil appeal/);
  assert.doesNotMatch(html, forbidden);
  for (const rows of [[], [{ ...match, published: false }], [{ ...match, title: '[TEST]' }], [{ ...match, matchId: otherId }]]) {
    await assert.rejects(render(harness(() => response({ matches: rows })), 'app/moot/[match]/page.tsx', { params: Promise.resolve({ match: id }) }), /NEXT_NOT_FOUND/);
  }
  const offline = harness(() => { throw new Error('must not fetch'); });
  for (const matchId of ['fixture-published', '../private']) {
    await assert.rejects(render(offline, 'app/moot/[match]/page.tsx', { params: Promise.resolve({ match: matchId }) }), /NEXT_NOT_FOUND/);
  }
  assert.equal(offline.calls.length, 0);
});

test('public Autumbra renders product description without fixture data or internal terms', async () => {
  const html = await render(harness(() => { throw new Error('must not fetch'); }), 'app/autumbra/page.tsx');
  assert.match(html, /Watch the edge\./);
  assert.match(html, /Autumbra Watch finds availability, DNS, certificate, and header problems/);
  assert.match(html, /<article><h3>Autumbra Watch<\/h3><\/article>/);
  assert.doesNotMatch(html, forbidden);
  assert.doesNotMatch(html, /ghost\.threat\.v1|burn-on-fail|On watch|Open investigations/i);
});

test('founder Autumbra renders existing unavailable states for failed and incomplete room replies', async () => {
  for (const fetch of [failed, () => response({}), () => { throw new Error('offline'); }]) {
    const html = await render(harness(fetch), 'app/admin/autumbra/page.tsx');
    assert.match(html, /Room unavailable/);
    assert.match(html, /Shield numbers are unavailable\./);
    assert.match(html, /Investigations will appear when Autumbra’s room is connected\./);
    assert.doesNotMatch(html, forbidden);
  }
});

test('shield reads reject explicit offline boards and taps use the actual room without a fixture fallback', async () => {
  const h = harness(() => response({ fixture: true, shields: [] }));
  await assert.rejects(h.load('app/admin/autumbra/shields-data.ts').shieldBoard('offline-founder'));
  const down = harness(failed);
  await assert.rejects(down.load('app/admin/autumbra/shields-data.ts').shieldTap('offline-founder', 'a1111111-1111-4111-8111-111111111111', 'raise'));
  assert.equal(down.calls.length, 1);
  assert.equal(down.calls[0].method, 'POST');
});

test('feed review displays supplied feed and state label and never serializes the raw series id', () => {
  const h = harness(failed);
  const { quarantineFromResponse, QUARANTINE_ERROR } = h.load('app/market-lab/quarantine.ts');
  const row = { id: 'offline-batch', series_id: '00000000-0000-0000-0000-000000000001:check_counts:total:AL', series_name: 'Monthly background-check counts by state and type · Alabama', source: 'check_counts', region: 'us-east', currency: '', unit: 'checks', fetched_at: '2026-10-27T00:00:00Z', status: 'held', reason: '' };
  const loaded = quarantineFromResponse(200, { batches: [row] });
  assert.equal(loaded.error, null);
  const { QuarantinePanel } = h.load('app/market-lab/quarantine-view.tsx');
  const html = renderToStaticMarkup(React.createElement(QuarantinePanel, loaded));
  assert.match(html, /Monthly background-check counts by state and type · Alabama/);
  assert.doesNotMatch(html, forbidden);
  assert.doesNotMatch(JSON.stringify(loaded), /00000000-0000-0000-0000/);
  const missing = quarantineFromResponse(200, { batches: [{ ...row, series_name: undefined }] });
  assert.equal(missing.error, QUARANTINE_ERROR);
  assert.deepEqual(missing.batches, []);
});
