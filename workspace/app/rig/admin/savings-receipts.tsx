import type { SavingsReceipt } from './types';

const dollars = (value: string | null) => value === null || !Number.isFinite(Number(value)) ? '—'
  : new Intl.NumberFormat('en', {style: 'currency', currency: 'USD', maximumFractionDigits: 8}).format(Number(value));
const names: Record<string, string> = {'rig.search': 'Search', 'rig.ask': 'Ask', 'rig.quote': 'Quote',
  'rig.import_file': 'Import', 'rig.compare': 'Compare', 'rig.setups': 'Explore this setup',
  'rig.3d.submit': '3D product view', 'rig.3d.approve': 'Approve'};

export function SavingsReceipts({receipts}: {receipts: SavingsReceipt[]}) {
  return <section className="retailer-card retailer-wide" aria-label="Receipts">
    <div className="retailer-section-heading"><span>07</span><h2>Receipts</h2></div>
    {receipts.length ? <div className="retailer-history">{receipts.map(row => <article key={row.id}>
      <div><strong>{names[row.action] || 'Receipt'}</strong><small>{new Date(row.created_at).toLocaleString()}</small><small>{row.id}</small></div>
      <dl><dt>{row.cost_status === 'upper_bound' ? 'Reserved cost' : 'Cost'}</dt><dd>{dollars(['recorded', 'upper_bound'].includes(row.cost_status) ? row.cost : null)}</dd>
        <dt>Would have cost</dt><dd>{dollars(row.would_have_cost)}</dd></dl>
    </article>)}</div> : <div><dl><dt>Cost</dt><dd>—</dd><dt>Would have cost</dt><dd>—</dd></dl>
      <p className="retailer-empty">Run a search to see receipts here.</p><a href="/rig">Search</a></div>}
  </section>;
}
