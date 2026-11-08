const $ = id => document.getElementById(id);
const wall = location.pathname.replace(/\/$/, '') === '/3d/wall';
document.body.classList.toggle('wall', wall); $('wall-builds').hidden = !wall;
const motion = matchMedia('(prefers-reduced-motion: reduce)');
let key = '', current = null, selected = '', stage = null, loading = 0, assetAbort, streamAbort;
let lastTouch = Date.now(), lastCycle = 0, stopped = false, reconnects = 0, retryTimer;
let history = [], historyNext = null, historyLoading = false, historyIdentity = '';
const safeMessage = 'The product service is not connected.';
const touch = () => { lastTouch = Date.now(); document.body.dataset.attract = 'false'; };
for (const type of ['pointerdown', 'keydown']) document.addEventListener(type, touch, {passive: true});

function clearModel() {
  loading++; assetAbort?.abort(); stage?.dispose(); stage = null; selected = '';
  $('model').hidden = true; $('controls').hidden = true; $('intro').hidden = false;
  $('product-name').textContent = ''; $('product-price').textContent = '';
}
function unavailable(message = safeMessage) {
  clearModel(); current = null;
  $('connection').textContent = message; $('message').textContent = message;
  $('receipt').hidden = true; $('completed').replaceChildren();
  $('today-count').textContent = '—'; $('active-count').textContent = '—';
  showProgress(null); $('retry').hidden = false;
  history = []; historyNext = null; historyIdentity = ''; $('more-builds').hidden = true;
}
function money(value) {
  if (!value || value.amount == null) return '—';
  return new Intl.NumberFormat('en', {style: 'currency', currency: value.currency}).format(Number(value.amount));
}
function progressBuild(selectedBuild) {
  return current?.live || (current?.latest?.status === 'failed' ? current.latest : selectedBuild || current?.latest);
}
function showProgress(build) {
  $('live-name').textContent = build?.name || '3D product view';
  for (const element of document.querySelectorAll('[data-stage]')) {
    const events = (build?.events || []).filter(event => event.stage === element.dataset.stage);
    const event = events.at(-1);
    element.dataset.outcome = event?.outcome || '';
    element.querySelector('time').textContent = event ? (event.elapsed_ms / 1000).toFixed(1) + 's' : '—';
    element.querySelector('time').dateTime = event?.at || '';
  }
  const cost = build?.cost;
  $('cost').firstChild.textContent = cost?.basis === 'upper_bound' ? 'Reserved cost ' : 'Cost ';
  $('cost').querySelector('strong').textContent = money({amount: cost?.amount_usd, currency: 'USD'});
  $('build-status').textContent = build?.status === 'draft' ? 'Review scale, appearance and attachment points before approval.'
    : build?.status === 'failed' ? 'The model conversion failed.' : '';
  const receipt = build?.receipt;
  $('receipt').hidden = !receipt;
  $('receipt-date').textContent = receipt ? new Date(receipt.approved_at).toISOString() : '';
  $('receipt-id').textContent = receipt?.job_id || '';
  $('receipt-hash').textContent = receipt?.sha256 || '';
  $('receipt-entries').replaceChildren(...(receipt?.receipt_ids || []).map(id => {
    const item = document.createElement('li'); item.textContent = id; return item;
  }));
}

async function select(build) {
  if (!build?.model || selected === build.id) return;
  clearModel(); selected = build.id;
  const generation = loading, controller = new AbortController(); assetAbort = controller;
  const timeout = setTimeout(() => controller.abort(), 30000);
  $('message').textContent = 'Connecting…';
  try {
    const model = build.model;
    if (model.url !== '/v1/rig/3d/assets/' + build.id || model.size_bytes > 5_000_000) throw Error('Invalid asset');
    const response = await fetch(model.url, {headers: {'X-Rig-Key': key}, cache: 'no-store', signal: controller.signal});
    if (!response.ok) throw Error('Unavailable');
    const bytes = await response.arrayBuffer();
    if (bytes.byteLength !== model.size_bytes) throw Error('Invalid size');
    const digest = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(n => n.toString(16).padStart(2, '0')).join('');
    if (digest !== model.sha256) throw Error('Invalid checksum');
    if (generation !== loading || stopped) return;
    $('model').hidden = false;
    const {createStage} = await import('./terminal-runtime.js');
    const result = await createStage($('model'), bytes, motion.matches);
    if (generation !== loading || stopped) { result.dispose(); return; }
    stage = result; $('intro').hidden = true; $('controls').hidden = false;
    $('product-name').textContent = build.name; $('product-price').textContent = money(build.price);
    $('message').textContent = ''; $('retry').hidden = true;
    showProgress(progressBuild(build));
  } catch {
    if (generation === loading && !stopped) { clearModel(); $('message').textContent = 'The product file could not be read.'; $('retry').hidden = false; }
  } finally { clearTimeout(timeout); }
}

function update(data) {
  if (!Array.isArray(data.approved) || !data.counts) throw Error('Invalid stream');
  const completedLive = data.approved.find(build => build.id === current?.live?.id);
  current = data; reconnects = 0;
  $('connection').textContent = '3D product view';
  $('today-count').textContent = String(data.counts.today); $('active-count').textContent = String(data.counts.active);
  const completed = data.approved.filter(build => build.today);
  const signature = completed.map(build => build.id + build.name).join('|');
  if ($('completed').dataset.signature !== signature) {
    $('completed').dataset.signature = signature;
    $('completed').replaceChildren(...completed.map(build => {
      const item = document.createElement('li'), button = document.createElement('button');
      button.textContent = build.name; button.addEventListener('click', () => select(build)); item.append(button); return item;
    }));
  }
  const identity = data.date + ':' + data.counts.approved + ':' + data.approved.map(build => build.id).join(',');
  if (identity !== historyIdentity) {
    historyIdentity = identity; history = []; historyNext = null;
    if (wall && data.counts.today > completed.length) void loadHistory(true);
  }
  // Revoke stale assets immediately, including a tenant losing its entitlement.
  if (selected && ![...data.approved, ...history].some(build => build.id === selected)) clearModel();
  const chosen = [...data.approved, ...history].find(build => build.id === selected);
  showProgress(progressBuild(completedLive || chosen));
  if (completedLive) void select(completedLive);
  else if (!selected && data.approved.length) void select(data.approved[0]);
  if (!data.approved.length) { clearModel(); $('message').textContent = ''; $('retry').hidden = true; }
}

async function connect() {
  streamAbort?.abort(); clearTimeout(retryTimer);
  const controller = new AbortController(); streamAbort = controller;
  let heartbeat;
  const resetTimeout = () => { clearTimeout(heartbeat); heartbeat = setTimeout(() => controller.abort(), 45000); };
  try {
    resetTimeout();
    if (!key) {
      const response = await fetch('/3d/config', {cache: 'no-store', signal: controller.signal});
      if (!response.ok) throw Error('Configuration');
      const config = await response.json(); key = config.publishable_key;
      if (config.configured === false && key === '') {
        update({date: new Date().toISOString().slice(0, 10), counts: {approved: 0, today: 0, active: 0},
          approved: [], live: null, latest: null});
        // Recheck configuration without polling authenticated data or faking a
        // build. The terminal picks up the first administrator save itself.
        retryTimer = setTimeout(connect, 30000);
        return;
      }
      if (!/^rk_pub_[A-Za-z0-9_-]+$/.test(key || '')) throw Error('Configuration');
    }
    const response = await fetch('/v1/rig/3d/terminal/events', {headers: {'X-Rig-Key': key, Accept: 'text/event-stream'},
      cache: 'no-store', signal: controller.signal});
    if (!response.ok || !response.body) throw Error('Unavailable');
    const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = '';
    try {
      while (!stopped) {
        const {value, done} = await reader.read();
        if (done) throw Error('Disconnected');
        resetTimeout(); buffer += decoder.decode(value, {stream: true});
        if (buffer.length > 2_000_000) throw Error('Invalid stream');
        let end;
        while ((end = buffer.indexOf('\n\n')) >= 0) {
          const packet = buffer.slice(0, end); buffer = buffer.slice(end + 2);
          const type = packet.split('\n').find(line => line.startsWith('event: '))?.slice(7);
          const line = packet.split('\n').find(line => line.startsWith('data: '));
          if (type === 'unavailable') throw Error('Unavailable');
          if (type === 'build' && line) update(JSON.parse(line.slice(6)));
        }
      }
    } finally { await reader.cancel().catch(() => {}); }
  } catch {
    if (streamAbort !== controller || stopped) return;
    unavailable(key ? safeMessage : 'The 3D test page is not configured.');
    // Bounded automatic retry. A touch can explicitly reconnect after that.
    if (reconnects++ < 3) retryTimer = setTimeout(connect, 1000 * 2 ** reconnects);
  } finally { clearTimeout(heartbeat); }
}
function next() {
  const builds = [...new Map([...(current?.approved || []), ...history].map(build => [build.id, build])).values()];
  if (!builds.length) return;
  const index = builds.findIndex(build => build.id === selected);
  if (index === builds.length - 1 && current.counts.approved > builds.length && (!history.length || historyNext)) {
    void loadHistory(false).then(async () => {
      let extended = [...new Map([...builds, ...history].map(build => [build.id, build])).values()];
      if (extended.length === builds.length && historyNext) {
        await loadHistory(false);
        extended = [...new Map([...builds, ...history].map(build => [build.id, build])).values()];
      }
      void select(extended[(index + 1) % extended.length]);
    });
  } else void select(builds[(index + 1) % builds.length]);
}
async function loadHistory(today) {
  if (historyLoading) return;
  historyLoading = true; const identity = historyIdentity;
  try {
    const params = new URLSearchParams({today: String(today)});
    if (historyNext) params.set('before', historyNext);
    const response = await fetch('/v1/rig/3d/terminal/completed?' + params, {
      headers: {'X-Rig-Key': key}, cache: 'no-store', signal: AbortSignal.timeout(30000)});
    if (!response.ok) throw Error('Unavailable');
    const value = await response.json();
    if (identity !== historyIdentity || !current) return;
    history = [...new Map([...history, ...value.builds].map(build => [build.id, build])).values()];
    historyNext = value.next;
    if (wall) {
      $('completed').replaceChildren(...history.filter(build => build.today).map(build => {
        const item = document.createElement('li'), button = document.createElement('button');
        button.textContent = build.name; button.onclick = () => select(build); item.append(button); return item;
      }));
      $('more-builds').hidden = !historyNext;
    }
  } catch { $('message').textContent = safeMessage; $('retry').hidden = false; }
  finally { historyLoading = false; }
}
$('more-builds').onclick = () => loadHistory(true);
$('rotate-left').onclick = () => stage?.rotate(-.3);
$('rotate-right').onclick = () => stage?.rotate(.3);
$('zoom-in').onclick = () => stage?.zoom(.85);
$('zoom-out').onclick = () => stage?.zoom(1.18);
$('next').onclick = next;
$('retry').onclick = () => { reconnects = 0; key = ''; void connect(); };
$('reset').onclick = () => { touch(); clearModel(); if (current) update(current); };
$('fullscreen').onclick = () => document.documentElement.requestFullscreen?.().catch(() => { $('message').textContent = 'Full screen is not available.'; });
motion.addEventListener('change', event => stage?.reduced(event.matches));
const idle = setInterval(() => {
  const now = Date.now();
  if (now - lastTouch >= 60000) {
    document.body.dataset.attract = 'true';
    if (now - lastCycle >= 8000 && !document.hidden) { lastCycle = now; next(); }
  }
}, 1000);
window.addEventListener('pagehide', () => {
  stopped = true; streamAbort?.abort(); clearTimeout(retryTimer); clearInterval(idle); clearModel();
});
void connect();
