const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { createRequire } = require('node:module');
const { test } = require('node:test');

const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const root = process.cwd();
const realRequire = createRequire(path.join(root, 'workspace/package.json'));
const ts = realRequire('typescript');
const React = realRequire('react');
const { renderToStaticMarkup: render } = realRequire('react-dom/server');

function loader(settings = {}, overrides = {}, globals = {}) {
  const cache = new Map();
  function load(filename) {
    filename = path.resolve(filename);
    if (cache.has(filename)) return cache.get(filename).exports;
    const source = input[filename] ?? fs.readFileSync(filename, 'utf8');
    const module = { exports: {} };
    cache.set(filename, module);
    function requireLocal(name) {
      if (Object.hasOwn(overrides, name)) return overrides[name];
      if (name === '../squad-links') return { SquadLinks: () => null };
      if (name === 'server-only' || name.endsWith('.css')) return {};
      if (!name.startsWith('.') && !name.startsWith('@/')) return realRequire(name);
      const base = name.startsWith('@/') ? path.join(root, 'workspace', name.slice(2)) : path.resolve(path.dirname(filename), name);
      const resolved = ['', '.ts', '.tsx', '.js'].map(suffix => base + suffix)
        .find(candidate => Object.hasOwn(input, candidate) || fs.existsSync(candidate));
      assert.ok(resolved, 'Module exists: ' + name);
      return load(resolved);
    }
    const output = ts.transpileModule(source, { fileName: filename, compilerOptions: {
      target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX,
    }}).outputText;
    const wrapper = vm.runInNewContext('(function(exports, require, module){' + output + '\n})', {
      process: { env: settings }, console, URL, URLSearchParams, AbortController, AbortSignal, Response, setTimeout, clearTimeout,
      fetch: () => { throw new Error('Rendering must not make a network request'); },
      ...globals,
    }, { filename });
    wrapper(module.exports, requireLocal, module);
    return module.exports;
  }
  return name => load(path.join(root, 'workspace/app/skala', name));
}

// Run the client effects with fake responses, then render the resulting tree.
async function goldClient(props, response) {
  const slots = [], requests = [];
  let cursor = 0, dirty = true, element;
  const effects = [];
  const hooks = { ...React,
    useState(initial) {
      const index = cursor++;
      if (!(index in slots)) slots[index] = typeof initial === 'function' ? initial() : initial;
      return [slots[index], value => {
        const next = typeof value === 'function' ? value(slots[index]) : value;
        if (!Object.is(next, slots[index])) { slots[index] = next; dirty = true; }
      }];
    },
    useRef(initial) { const index = cursor++; return slots[index] ??= { current: initial }; },
    useCallback(value, deps) {
      const index = cursor++;
      if (!slots[index] || deps.some((value, i) => !Object.is(value, slots[index].deps[i]))) slots[index] = { value, deps };
      return slots[index].value;
    },
    useEffect(effect, deps) {
      const index = cursor++;
      if (!slots[index] || deps.some((value, i) => !Object.is(value, slots[index].deps[i]))) {
        const previous = slots[index];
        slots[index] = { deps };
        effects.push(() => { previous?.cleanup?.(); slots[index].cleanup = effect(); });
      }
    },
  };
  const { GoldView } = loader({}, { react: hooks }, {
    window: { addEventListener() {}, removeEventListener() {} },
    fetch: async url => { requests.push(url); const value = await response(url); return value instanceof Response ? value : Response.json(await value.json(), {status: value.ok ? 200 : 502}); },
  })('gold/view.tsx');
  async function settle() {
    for (let turn = 0; turn < 20; turn++) {
      if (dirty) {
        dirty = false; cursor = 0; element = GoldView(props);
        while (effects.length) effects.shift()();
      }
      await new Promise(resolve => setImmediate(resolve));
      if (!dirty) return render(element);
    }
    throw new Error('Client did not settle');
  }
  function find(predicate, node = element) {
    if (!node || typeof node !== 'object') return undefined;
    if (predicate(node)) return node;
    for (const child of React.Children.toArray(node.props?.children)) {
      const result = find(predicate, child);
      if (result) return result;
    }
  }
  return { settle, find, requests };
}

test('empty library names its first action and cannot bulk-approve', () => {
  const { SkalaApp } = loader()('view.tsx');
  const html = render(React.createElement(SkalaApp, { skills: [], accountName: null, loadError: null }));
  assert.match(html, /No skills yet\./);
  assert.match(html, /Add a skill package to fill this library\./);
  assert.match(html, /<button[^>]*disabled=""[^>]*>Approve all ready<\/button>/);
  assert.match(html, /Run evals to prepare a version for approval\./);
  assert.match(html, /<button[^>]*disabled=""[^>]*>Confirm listed approvals<\/button>/);
  assert.doesNotMatch(html, /[0-9]+(?:\.[0-9]+)?%|\$[0-9]/);
});

test('first evaluation has no invented score, price or receipt', () => {
  const { SkalaApp } = loader()('view.tsx');
  const row = { id: 'base.offline', version: '1.0.0', agent: 'base', rung: 1, task_type: 'base.offline',
    description: '', state: 'candidate', last_eval_score: null, last_eval_at: null, present: true,
    calls_30d: 0, avg_cost_usd: null };
  const html = render(React.createElement(SkalaApp, { skills: [row], accountName: null, loadError: null }));
  assert.match(html, /—/);
  assert.match(html, /Run evals to record the first score and case results\./);
  assert.match(html, /uses a model · no calls yet/);
  assert.doesNotMatch(html, /[0-9]+(?:\.[0-9]+)?%|\$[0-9]|class="sk-cases"/);
  const { costLabel } = loader()('library.ts');
  assert.equal(costLabel({ ...row, calls_30d: 5 }), 'uses a model · —/call (30 days)');
  const observed = render(React.createElement(SkalaApp, { skills: [{ ...row, last_eval_score: 0,
    last_eval_at: '2026-11-07T00:00:00Z', calls_30d: 5, avg_cost_usd: 0 }], accountName: null, loadError: null }));
  assert.match(observed, />0%<\/span>/);
  assert.match(observed, /\$0\.0000\/call/);
});

test('training cards retain their shape with actual zeroes and the first action', () => {
  const { TrainingSummary } = loader()('gold/view.tsx');
  const html = render(React.createElement(TrainingSummary, { founder: true,
    summary: { skills: [], pairs: {}, region: 'us-east' } }));
  assert.equal((html.match(/class="gold-card"/g) ?? []).length, 8);
  assert.equal((html.match(/class="gold-count">0/g) ?? []).length, 8);
  assert.equal((html.match(/Training pairs<\/dt><dd>0/g) ?? []).length, 8);
  assert.equal((html.match(/Held back<\/dt><dd>0/g) ?? []).length, 8);
  assert.equal((html.match(/Check the first example to fill this training summary\./g) ?? []).length, 8);
  assert.doesNotMatch(html, /100|[1-9][0-9]*%|NaN|undefined/);
});

test('unavailable training data stays unknown rather than becoming zero', () => {
  const { TrainingSummary } = loader()('gold/view.tsx');
  const html = render(React.createElement(TrainingSummary, { founder: true, summary: null }));
  assert.equal((html.match(/class="gold-card"/g) ?? []).length, 8);
  assert.equal((html.match(/class="gold-count">—/g) ?? []).length, 8);
  assert.doesNotMatch(html, /<dd>0|100|class="gold-count">0/);
});

test('empty review queues name the first action for each scope', async () => {
  const client = await goldClient({ founder: true }, () => ({ ok: true,
    json: async () => ({ skills: [], pairs: {}, region: 'us-east' }) }));
  assert.match(await client.settle(), /Add a skill package to create the first examples\./);
  client.find(node => node.type === 'select' && node.props.value === 'platform').props.onChange({ target: { value: 'tenant' } });
  const tenant = await client.settle();
  assert.match(tenant, /Accept a result in this workspace to start its training collection\./);
  assert.match(tenant, /Training pairs<\/dt><dd>0/);
  assert.deepEqual(client.requests, ['/api/skala/gold?scope=platform', '/api/skala/gold?scope=tenant']);
});

test('unconfigured client effects perform no requests', async () => {
  const client = await goldClient({ founder: true, configurationError: 'Missing setting: TANK_API_KEY.' },
    () => { throw new Error('An unconfigured client must not request data'); });
  const html = await client.settle();
  assert.match(html, /Missing setting: TANK_API_KEY\./);
  assert.doesNotMatch(html, /No examples waiting|<dd>0/);
  assert.deepEqual(client.requests, []);
});

test('recorded zero scores and trends remain visible', () => {
  const { TrainingSummary } = loader()('gold/view.tsx');
  const html = render(React.createElement(TrainingSummary, { founder: false, summary: {
    region: 'za', pairs: { zenas: 2 }, skills: [{ agent: 'zenas', skill_id: 'zenas.offline', checked: 3,
      target: 100, holdout: 1, candidates: 0, last_score: 0, trend: 0, ran_at: '2026-11-07T00:00:00Z' }],
  }}));
  assert.match(html, /Latest skill score<\/dt><dd>0\.0%/);
  assert.match(html, /Change<\/dt><dd>0\.0 points/);
  assert.match(html, /Training pairs<\/dt><dd>2/);
  assert.match(html, /Held back<\/dt><dd>1/);
});

test('missing Workspace key is named before any Tank request', async () => {
  let requests = 0;
  const common = { 'next/navigation': { notFound() { throw new Error('Not found'); } },
    '@/app/review/access': { rejectUnlessFounder: async () => null },
    '@/lib/tenant': { activeTenant: async () => null },
    '@/lib/tank': { listSkills: async () => { requests++; return []; }, skillApprovalStatus: async () => { requests++; return []; } },
    './access': { goldIdentity: async () => ({ role: 'founder' }) },
  };
  const load = loader({}, common);
  const html = render(await load('page.tsx').default());
  assert.match(html, /Missing setting: TANK_API_KEY\./);
  assert.equal(requests, 0);
  const gold = render(await load('gold/page.tsx').default());
  assert.match(gold, /Missing setting: TANK_API_KEY\./);
  assert.doesNotMatch(gold, /<dd>0|No examples waiting|>Right /);
  const denied = loader({}, { ...common, '@/app/review/access': { rejectUnlessFounder: async () => true } });
  await assert.rejects(denied('page.tsx').default(), /Not found/);
});
