export type SavingsReceipt = {id:string;action:string;cost:number|null;"would have cost":number|null;baseline_model:string|null;created_at:string};
const money=(value:number|null)=>value===null?"—":`$${value.toFixed(8)}`;
const actionName=(action:string)=>action.startsWith('/answers')?'Ask Zenas':action.startsWith('/drafts')?'Templates':
  action.startsWith('/contract-reviews')?'Review':action.startsWith('/matters')?'Matters':'Zenas';

export function Receipts({receipts:all}:{receipts:SavingsReceipt[]}) {
  const receipts=all.filter(row=>row.action!=="/moot"&&!row.action.startsWith("/moot/"));
  return <section className="zn-card" aria-label="Receipts" tabIndex={0}
    style={{maxHeight:"calc(100dvh - 100px)",overflow:"auto",boxSizing:"border-box"}}><h2>Receipts</h2>
    <table><thead><tr><th scope="col">Run</th><th scope="col">Cost</th><th scope="col">Would have cost</th></tr></thead>
      <tbody>{receipts.map(receipt=><tr key={receipt.id}><th scope="row">{actionName(receipt.action)}</th>
        <td>{money(receipt.cost)}</td><td>{money(receipt["would have cost"])}{receipt.baseline_model&&<> · {receipt.baseline_model}</>}</td></tr>)}
      {receipts.length===0&&<tr><th scope="row">—</th><td>—</td><td>—</td></tr>}</tbody></table>
    {receipts.length===0&&<p>Ask Zenas</p>}
  </section>;
}
