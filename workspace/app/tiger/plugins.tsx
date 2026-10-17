"use client";

import { useState } from "react";
import { CONNECTIONS, FILES, KEYS, LINKS, MASK, type KeyId } from "./copy";

type Tab = "keys" | "files" | "links" | "mcp";
type ExtraFile = { name: string; type: string };
type ExtraLink = { label: string; host: string };
type ExtraConnection = { name: string; host: string; tokenSaved: boolean };
type Supplier = { id: string; name: string };

const TABS: { id: Tab; label: string }[] = [
  { id: "keys", label: "API keys" },
  { id: "files", label: "Files" },
  { id: "links", label: "Source links" },
  { id: "mcp", label: "MCP connections" },
];

function Tag() {
  return <span className="tag">Example</span>;
}

function kept(input: HTMLInputElement | null): boolean {
  const typed = input?.value ?? "";
  if (input) input.value = "";
  return typed.trim().length > 0;
}

function hostOf(raw: string): string {
  const bare = raw.trim().split("?")[0] ?? "";
  try {
    const withScheme = bare.includes("://") ? bare : `https://${bare}`;
    return new URL(withScheme).host;
  } catch {
    return bare.replace(/^https?:\/\//, "").split("/")[0] || bare;
  }
}

function fileType(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "csv") return "CSV";
  if (ext === "xlsx" || ext === "xls") return "XLSX";
  if (ext === "zip") return "ZIP";
  if (ext === "pdf") return "PDF";
  return ext ? ext.toUpperCase() : "File";
}

export function Plugins({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<Tab>("keys");
  const [saved, setSaved] = useState<Record<KeyId, boolean>>({
    feed: true,
    catalogue: true,
    email: false,
    text: false,
    barcode: false,
  });
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [files, setFiles] = useState<ExtraFile[]>([]);
  const [links, setLinks] = useState<ExtraLink[]>([]);
  const [often, setOften] = useState<"Daily" | "Weekly">("Daily");
  const [connections, setConnections] = useState<ExtraConnection[]>([]);
  const [signIn, setSignIn] = useState<"provider" | "token">("token");

  function saveRow(id: KeyId, form: HTMLFormElement) {
    const field = form.querySelector<HTMLInputElement>("input[type=password]");
    if (!kept(field)) return;
    setSaved((current) => ({ ...current, [id]: true }));
  }

  function saveSupplier(form: HTMLFormElement) {
    const name = form.querySelector<HTMLInputElement>("input[name=supplier]")?.value.trim() ?? "";
    const field = form.querySelector<HTMLInputElement>("input[type=password]");
    const wrote = kept(field);
    form.reset();
    if (!name || !wrote) return;
    setSuppliers((current) => [...current, { id: `${current.length}-${name}`, name }]);
  }

  function addFiles(list: FileList | null) {
    if (!list?.length) return;
    const next = Array.from(list).map((file) => ({ name: file.name, type: fileType(file.name) }));
    setFiles((current) => [...current, ...next]);
  }

  function addLink(form: HTMLFormElement) {
    const link = form.querySelector<HTMLInputElement>("input[name=link]")?.value.trim() ?? "";
    const label = form.querySelector<HTMLInputElement>("input[name=label]")?.value.trim() ?? "";
    form.reset();
    if (!link) return;
    setLinks((current) => [...current, { label: label || hostOf(link), host: hostOf(link) }]);
  }

  function addConnection(form: HTMLFormElement) {
    const name = form.querySelector<HTMLInputElement>("input[name=conn-name]")?.value.trim() ?? "";
    const server = form.querySelector<HTMLInputElement>("input[name=server]")?.value.trim() ?? "";
    const field = form.querySelector<HTMLInputElement>("input[type=password]");
    const wrote = signIn === "token" ? kept(field) : true;
    if (field) field.value = "";
    form.reset();
    if (!name || !server || !wrote) return;
    setConnections((current) => [...current, { name, host: hostOf(server), tokenSaved: signIn === "token" }]);
  }

  return (
    <div className="scrim" role="presentation" onClick={onClose}>
      <div className="popup" role="dialog" aria-modal="true" aria-labelledby="plugins-title" onClick={(event) => event.stopPropagation()}>
        <div className="popup-head">
          <div>
            <h2 id="plugins-title">Plugins</h2>
            <p className="sub">Everything Tiger connects to. Add a key, upload a file, or paste a link.</p>
          </div>
          <button type="button" className="text" onClick={onClose}>Close</button>
        </div>
        <div className="tabs" role="tablist" aria-label="Plugins">
          {TABS.map((item) => (
            <button key={item.id} type="button" role="tab" aria-selected={tab === item.id} className={tab === item.id ? "on" : ""} onClick={() => setTab(item.id)}>
              {item.label}
            </button>
          ))}
        </div>

        {tab === "keys" ? (
          <div className="part" role="tabpanel">
            <div className="part-title"><h3>API keys</h3><Tag /></div>
            <p className="intro">Keys for price feeds and alert services. A key is write-only: once saved it is never shown again.</p>
            <div className="list">
              {KEYS.map((row) => (
                <form key={row.id} className="key-row" onSubmit={(event) => { event.preventDefault(); saveRow(row.id, event.currentTarget); }}>
                  <div>
                    <h4>{row.name}</h4>
                    <p>{row.detail}</p>
                    <span className="env-label">{row.env}</span>
                  </div>
                  {saved[row.id] ? <span className="pill"><i />Connected</span> : <span className="pill off"><i />Not set</span>}
                  {saved[row.id] ? (
                    <div className="mask">{MASK}</div>
                  ) : (
                    <input type="password" aria-label={`${row.name} key`} placeholder="Paste key" autoComplete="off" />
                  )}
                  {saved[row.id] ? (
                    <div className="row-actions">
                      <button type="button" className="text" onClick={() => setSaved((current) => ({ ...current, [row.id]: false }))}>Replace</button>
                      <button type="button" className="text" onClick={() => setSaved((current) => ({ ...current, [row.id]: false }))}>Remove</button>
                    </div>
                  ) : (
                    <button type="submit" className="line">Save</button>
                  )}
                </form>
              ))}
              {suppliers.map((row) => (
                <div className="key-row" key={row.id}>
                  <div>
                    <h4>{row.name}</h4>
                    <p>Store feed key</p>
                  </div>
                  <span className="pill"><i />Connected</span>
                  <div className="mask">{MASK}</div>
                  <button type="button" className="text" onClick={() => setSuppliers((current) => current.filter((item) => item.id !== row.id))}>Remove</button>
                </div>
              ))}
              <form className="add" onSubmit={(event) => { event.preventDefault(); saveSupplier(event.currentTarget); }}>
                <div className="who">
                  <h4>Add a store feed key</h4>
                  <p>For a store or supplier that gives you a price feed key.</p>
                </div>
                <label>
                  Store or supplier name
                  <input name="supplier" type="text" placeholder="e.g. Store A (Example)" autoComplete="off" />
                </label>
                <label>
                  Key
                  <input type="password" aria-label="Store feed key" placeholder="Paste key (hidden once saved)" autoComplete="off" />
                </label>
                <button type="submit" className="primary">Save key</button>
              </form>
            </div>
            <p className="note">These rows are an Example. A typed key is cleared and is not kept.</p>
          </div>
        ) : null}

        {tab === "files" ? (
          <div className="part" role="tabpanel">
            <div className="part-title"><h3>Files</h3><Tag /></div>
            <p className="intro">Upload saved product pages, watch lists or price lists. CSV files can be matched to the right columns.</p>
            <div className="drop" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); addFiles(event.dataTransfer.files); }}>
              <strong>Drag CSV, XLSX or ZIP files of saved pages here</strong>
              <span>or</span>
              <button type="button" className="primary" onClick={() => document.getElementById("tiger-files")?.click()}>Choose files</button>
              <input id="tiger-files" type="file" accept=".csv,.xlsx,.xls,.zip,.pdf" multiple hidden onChange={(event) => { addFiles(event.target.files); event.target.value = ""; }} />
            </div>
            <table className="file-table">
              <thead>
                <tr><th>File</th><th>Type</th><th>Rows / pages</th><th>Uploaded</th><th>Status</th><th /></tr>
              </thead>
              <tbody>
                {FILES.map((file) => (
                  <tr key={file.name}>
                    <td className="name">{file.name}</td>
                    <td>{file.type}</td>
                    <td>{file.size}</td>
                    <td>{file.when}</td>
                    <td className={file.status === "Processed" ? "status-on" : "status-off"}>{file.status}</td>
                    <td>{file.map ? <button type="button" className="text">Map columns</button> : null}</td>
                  </tr>
                ))}
                {files.map((file) => (
                  <tr key={file.name}>
                    <td className="name">{file.name}</td>
                    <td>{file.type}</td>
                    <td>—</td>
                    <td>Just now</td>
                    <td className="status-off">Needs checking</td>
                    <td />
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : null}

        {tab === "links" ? (
          <div className="part" role="tabpanel">
            <div className="part-title"><h3>Source links</h3><Tag /></div>
            <p className="intro">Product pages Tiger reads for price and stock. Public pages only.</p>
            <form className="link-form" onSubmit={(event) => { event.preventDefault(); addLink(event.currentTarget); }}>
              <label>
                Link
                <input name="link" type="url" placeholder="Paste a link, e.g. https://store-a.example/…" autoComplete="off" />
              </label>
              <label>
                Label (optional)
                <input name="label" type="text" placeholder="e.g. Trail running shoe" autoComplete="off" />
              </label>
              <div>
                <span className="field-label">How often to check</span>
                <div className="seg">
                  <button type="button" className={often === "Daily" ? "on" : ""} onClick={() => setOften("Daily")}>Daily</button>
                  <button type="button" className={often === "Weekly" ? "on" : ""} onClick={() => setOften("Weekly")}>Weekly</button>
                </div>
              </div>
              <button type="submit" className="primary">Add link</button>
            </form>
            <div className="list">
              {LINKS.map((link) => (
                <div className="link-row" key={link.host}>
                  <div>
                    <h4>{link.label}</h4>
                    <span className="host">{link.host}</span>
                  </div>
                  <div>
                    <span className="field-label">Last checked</span>
                    <span>{link.checked}</span>
                  </div>
                  <span className={link.status === "Read" ? "pill" : "pill off"}><i />{link.status}</span>
                  <button type="button" className="text">Remove</button>
                </div>
              ))}
              {links.map((link) => (
                <div className="link-row" key={`${link.host}-${link.label}`}>
                  <div>
                    <h4>{link.label}</h4>
                    <span className="host">{link.host}</span>
                  </div>
                  <span>Not checked yet</span>
                  <span className="pill off"><i />Example</span>
                  <button type="button" className="text" onClick={() => setLinks((current) => current.filter((item) => item !== link))}>Remove</button>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {tab === "mcp" ? (
          <div className="part" role="tabpanel">
            <div className="part-title"><h3>MCP connections</h3><Tag /></div>
            <p className="intro">Connections to outside tools Tiger can use, such as a store catalogue or an alert sender.</p>
            <div className="list">
              {CONNECTIONS.map((row) => (
                <div className="conn-row" key={row.host}>
                  <div>
                    <h4>{row.name}</h4>
                    <span className="host">{row.host}</span>
                  </div>
                  <p>{row.detail}</p>
                  <span className={row.status === "Connected" ? "pill" : "pill off"}><i />{row.status}</span>
                  <div>
                    <span className="field-label">Last used</span>
                    <span>{row.used}</span>
                  </div>
                  <button type="button" className="text">Disconnect</button>
                </div>
              ))}
              {connections.map((row) => (
                <div className="conn-row" key={`${row.host}-${row.name}`}>
                  <div>
                    <h4>{row.name}</h4>
                    <span className="host">{row.host}</span>
                  </div>
                  <p>{row.tokenSaved ? MASK : "Signed in with the provider"}</p>
                  <span className="pill"><i />Connected</span>
                  <span>Just now</span>
                  <button type="button" className="text" onClick={() => setConnections((current) => current.filter((item) => item !== row))}>Disconnect</button>
                </div>
              ))}
            </div>
            <form className="conn-form" onSubmit={(event) => { event.preventDefault(); addConnection(event.currentTarget); }}>
              <h4>Add connection</h4>
              <div className="pair">
                <label>
                  Name
                  <input name="conn-name" type="text" placeholder="e.g. Store catalogue" autoComplete="off" />
                </label>
                <label>
                  Server URL
                  <input name="server" type="url" placeholder="https://…" autoComplete="off" />
                </label>
              </div>
              <div className="pair end">
                <div>
                  <span className="field-label">How it signs in</span>
                  <div className="seg">
                    <button type="button" className={signIn === "provider" ? "on" : ""} onClick={() => setSignIn("provider")}>Sign in with the provider</button>
                    <button type="button" className={signIn === "token" ? "on" : ""} onClick={() => setSignIn("token")}>Token</button>
                  </div>
                </div>
                {signIn === "token" ? (
                  <label>
                    Token
                    <input type="password" aria-label="Token" placeholder="Paste token (hidden once saved)" autoComplete="off" />
                  </label>
                ) : <span />}
                <button type="submit" className="primary">Add connection</button>
              </div>
              <p className="note">A saved token shows only as •••• saved 17 Oct, with Replace or Remove. It is never shown again.</p>
            </form>
          </div>
        ) : null}
      </div>
    </div>
  );
}
