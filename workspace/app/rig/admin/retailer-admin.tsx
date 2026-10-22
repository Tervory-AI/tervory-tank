"use client";

import { useState, type FormEvent } from "react";
import type { AdminOperation, AdminResult, FitReview, RetailerPanel } from "./types";

const PROVIDERS = [["shopify", "Shopify"], ["woocommerce", "WooCommerce"], ["google", "Google Merchant"], ["zanders", "Zanders"], ["sports_south", "Sports South"], ["rsr", "RSR"], ["jerrys", "Jerry’s"]];
const providerName = (id: string) => PROVIDERS.find(([key]) => key === id)?.[1] ?? id;
const fields = (form: HTMLFormElement) => Object.fromEntries(new FormData(form).entries());

async function sendRetailer(operation: AdminOperation, data: Record<string, unknown>): Promise<AdminResult> {
  const response = await fetch("/rig/admin/api", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ operation, data }) });
  if (!response.ok) throw new Error("The retailer request was not confirmed.");
  return response.json() as Promise<AdminResult>;
}

export function RetailerAdmin({ initial, act = sendRetailer }: { initial: RetailerPanel; act?: (operation: AdminOperation, data: Record<string, unknown>) => Promise<AdminResult> }) {
  const [panel, setPanel] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState(false);
  const [provider, setProvider] = useState("shopify");
  const [mode, setMode] = useState("file");
  const [authMode, setAuthMode] = useState("none");
  const run = async (operation: AdminOperation, data: Record<string, unknown>) => {
    setBusy(true); setNotice("");
    try {
      const result = await act(operation, data);
      setNotice(result.message); setError(!result.ok);
      if (result.panel) setPanel(result.panel);
      return result.ok;
    } catch { setNotice("The operation was not confirmed. Check the import history before retrying."); setError(true); return false; }
    finally { setBusy(false); }
  };
  const submitFeed = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = event.currentTarget;
    const values = fields(form);
    let columns: Record<string, string> = {};
    try { columns = JSON.parse(String(values.columns || "{}")); }
    catch { setNotice("Column mapping must be a JSON object."); setError(true); return; }
    const format = provider === "google" ? "xml" : ["shopify", "woocommerce"].includes(provider) ? "json" : String(values.format);
    const data: Record<string, unknown> = { distributor: provider, site: String(values.site).trim(), currency: String(values.currency).toUpperCase(), format, columns };
    if (mode === "file") {
      const file = values.file;
      if (!(file instanceof File) || !file.size || file.size > 8_000_000) { setNotice("Choose a feed file smaller than 8 MB."); setError(true); return; }
      data.contents = await file.text(); data.source = "ftp_export";
    } else {
      data.endpoint = String(values.endpoint).trim();
      data.auth_mode = authMode;
      for (const field of ["token", "username", "password"]) data[field] = String(values[field] || "");
      data.official_read_only = values.official === "on";
    }
    const ok = await run(mode === "file" ? "import" : "connect", data);
    if (ok) form.reset();
  };
  const submitRule = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); const form = event.currentTarget;
    if (await run("price-rule", fields(form))) form.reset();
  };
  const decide = (operation: "approve" | "reject", fit: FitReview) => run(operation, { part_sku: fit.part_sku, fits_sku: fit.fits_sku, fits_family: fit.fits_family });
  return <main className="retailer-admin">
    <header className="retailer-header"><div><a href="/rig">← Back to Rig</a><p className="retailer-eyebrow">YOUR CATALOGUE</p><h1>Retailer settings</h1><p>Keep your catalogue current. Review what belongs together.</p></div><span className="retailer-count">{panel.products} products · {panel.currency}</span></header>
    {notice && <p className={`retailer-notice ${error ? "is-error" : ""}`} role={error ? "alert" : "status"}>{notice}</p>}
    <div className="retailer-grid">
      <section className="retailer-card"><div className="retailer-section-heading"><span>01</span><h2>Feeds</h2></div><p>Import a sample file or connect an official feed. Connected feeds refresh nightly at 03:00 UTC.</p>
        {panel.feeds.map(feed => <div className="retailer-feed" key={feed.provider + feed.site}><div><strong>{providerName(feed.provider)}</strong><small>{feed.site}</small></div><button disabled={busy} onClick={() => run("refresh", { distributor: feed.provider, site: feed.site })}>Refresh now</button></div>)}
        {!panel.feeds.length && <p className="retailer-empty">No feed connected yet. Start with a sample file.</p>}
        <form onSubmit={submitFeed}><fieldset disabled={busy}><legend className="retailer-sr">Feed settings</legend>
          <div className="retailer-fields"><label>Source<select name="provider" value={provider} onChange={e => setProvider(e.target.value)}>{PROVIDERS.map(([key, name]) => <option key={key} value={key}>{name}</option>)}</select></label><label>Add by<select value={mode} onChange={e => setMode(e.target.value)}><option value="file">Import file</option><option value="connection">Connect feed</option></select></label></div>
          <label>Supplier website<input name="site" type="url" required placeholder="https://supplier.example" /></label>
          <div className="retailer-fields"><label>Supplier currency<input name="currency" required pattern="[A-Za-z]{3}" maxLength={3} placeholder="USD" /></label>{!["shopify", "woocommerce", "google"].includes(provider) && <label>File format<select name="format"><option value="csv">CSV</option><option value="tsv">TSV</option><option value="json">JSON</option></select></label>}</div>
          {mode === "file" ? <label>Sample or supplier file<input name="file" type="file" required accept=".json,.xml,.csv,.tsv" /></label> : <><label>Read-only feed address<input name="endpoint" type="url" required /></label><label>Authentication<select value={authMode} onChange={e => setAuthMode(e.target.value)}><option value="none">Public feed</option><option value="bearer">Bearer token</option><option value="shopify">Shopify access token</option><option value="basic">Username and password / WooCommerce keys</option></select></label>{authMode === "basic" ? <><label>Username or consumer key<input name="username" type="password" autoComplete="new-password" required /></label><label>Password or consumer secret<input name="password" type="password" autoComplete="new-password" required /></label></> : authMode !== "none" && <label>Access token<input name="token" type="password" autoComplete="new-password" required /></label>}<label className="retailer-check"><input name="official" type="checkbox" required />This is an official, read-only feed.</label></>}
          <details><summary>Column mapping</summary><label>Field names as JSON<textarea name="columns" rows={3} placeholder={'{"name":"Description","brand":"Manufacturer"}'} /></label></details>
          <button className="retailer-primary" type="submit">{mode === "file" ? "Import file" : "Connect feed"}</button>
        </fieldset></form>
      </section>
      <section className="retailer-card"><div className="retailer-section-heading"><span>02</span><h2>Indicative prices</h2></div><p>One price in ZAR for shoppers. Your rule and supplier amounts stay private.</p><span className="retailer-tag">{panel.price_configured ? "Price rule saved" : "Price rule needed"}</span>
        <form onSubmit={submitRule}><fieldset disabled={busy}><legend className="retailer-sr">Replace the private price rule</legend><label>Freight per item, in supplier currency<input name="freight" type="number" min="0" max="1000000000" step="0.01" required /></label><div className="retailer-fields"><label>Duty (%)<input name="duty_percent" type="number" min="0" max="1000" step="0.01" required /></label><label>Gross margin (%)<input name="margin_percent" type="number" min="0" max="99.99" step="0.01" required /></label></div><p className="retailer-hint">Enter all three fields to replace the rule. Saved values are never sent back to this page. Existing feed products are repriced together.</p><button type="submit">Save price rule</button></fieldset></form>
        {panel.can_set_exchange_rate ? <form onSubmit={async e => { e.preventDefault(); const form = e.currentTarget; if (await run("exchange-rate", fields(form))) form.reset(); }}><fieldset disabled={busy}><legend>Exchange rate · founder only</legend><div className="retailer-fields"><label>Source currency<input name="currency" pattern="[A-Za-z]{3}" maxLength={3} required /></label><label>ZAR per unit<input name="rate" type="number" min="0.000001" max="1000000" step="any" required /></label></div><button type="submit">Set exchange rate</button></fieldset></form> : <p className="retailer-hint">The founder sets the exchange rate to ZAR. Imports wait until that rate is available.</p>}
      </section>
      <section className="retailer-card retailer-wide"><div className="retailer-section-heading"><span>03</span><h2>Fit approval queue</h2><span className="retailer-tag">{panel.fits.length} to review</span></div><p>Suggested combinations stay hidden from shoppers until you approve them.</p>
        {!panel.fits.length && <p className="retailer-empty">Nothing waiting for review.</p>}
        {panel.fits.map(fit => <article className="retailer-fit" key={`${fit.part_sku}:${fit.fits_sku || fit.fits_family}`}><div><h3>{fit.part_name} <span>with</span> {fit.fits_with}</h3><p>{fit.note || "No supplier evidence was provided. Verify this combination before approving."}</p><small>{fit.part_sku} · {fit.fits_sku || fit.fits_family}</small></div><div className="retailer-actions"><button disabled={busy} onClick={() => decide("reject", fit)}>Reject</button><button disabled={busy} onClick={() => decide("approve", fit)}>Approve</button></div></article>)}
        <button disabled={busy} onClick={() => run("suggest", {})}>Find fit suggestions</button>
      </section>
      <section className="retailer-card"><div className="retailer-section-heading"><span>04</span><h2>Setup templates</h2></div><p>Choose the product categories that make a complete setup. Only approved combinations are shown.</p>
        {Object.entries(panel.templates).map(([category, roles]) => <div className="retailer-template" key={category}><strong>{category}</strong><small>{Object.entries(roles).map(([role, target]) => `${role}: ${target}`).join(" · ")}</small></div>)}
        <form onSubmit={async e => { e.preventDefault(); const form = e.currentTarget; const data = fields(form); const roles = String(data.roles).split(",").map(s => s.trim()).filter(Boolean); if (!roles.length) return; if (await run("templates", { [String(data.category).trim()]: Object.fromEntries(roles.map(role => [role, role])) })) form.reset(); }}><fieldset disabled={busy}><legend className="retailer-sr">Save a category template</legend><label>Product category<input name="category" required maxLength={80} /></label><label>Included categories, separated by commas<input name="roles" required placeholder="shade, stand" /></label><button type="submit">Save template</button></fieldset></form>
      </section>
      <section className="retailer-card"><div className="retailer-section-heading"><span>05</span><h2>What shoppers couldn’t find</h2></div><p>Search counts for your catalogue. No shopper identities.</p>{panel.missed_searches.length ? <ul className="retailer-searches">{panel.missed_searches.map(row => <li key={row.query}><span>{row.query}</span><strong>{row.count}</strong></li>)}</ul> : <p className="retailer-empty">No unmatched searches in the last 90 days.</p>}</section>
      <section className="retailer-card retailer-wide"><div className="retailer-section-heading"><span>06</span><h2>Import history</h2></div><p>Each file is applied in full, or nothing changes.</p>{panel.receipts.length ? <div className="retailer-history">{panel.receipts.map(row => <article key={row.id}><div><strong>{providerName(row.provider)}</strong><small>{row.site}</small><small>{new Date(row.created_at).toLocaleString()}</small></div><p><b>{row.added}</b> added · <b>{row.updated}</b> updated · <b>{row.rejected}</b> rejected</p></article>)}</div> : <p className="retailer-empty">Import a file to see the result here.</p>}</section>
    </div>
  </main>;
}
