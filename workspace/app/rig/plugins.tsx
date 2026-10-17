"use client";

import { useState } from "react";
import { CONNECTIONS, FILES, KEYS, LINKS, MASK, PLUGIN_TABS, type KeyId, type PluginTab } from "./copy";

type Supplier = { id: string; name: string };
type ExtraFile = { name: string; type: string };
type ExtraLink = { label: string; host: string };
type ExtraConnection = { name: string; host: string; tokenSaved: boolean };

function Tag() {
  return <span className="tag">Example</span>;
}

function Pill({ children, on = true }: { children: string; on?: boolean }) {
  return (
    <span className={on ? "pill" : "pill off"}>
      <i />
      {children}
    </span>
  );
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
  if (ext === "pdf") return "PDF";
  return ext ? ext.toUpperCase() : "File";
}

export function Plugins({ onClose }: { onClose: () => void }) {
  const [tab, setTab] = useState<PluginTab>("keys");
  const [saved, setSaved] = useState<Record<KeyId, boolean>>({
    fred: true,
    census: true,
    eia: false,
    noaa: false,
    legiscan: false,
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
    if (signIn !== "token" && field) field.value = "";
    form.reset();
    if (!name || !server || !wrote) return;
    setConnections((current) => [...current, { name, host: hostOf(server), tokenSaved: signIn === "token" }]);
  }

  return (
    <div className="scrim" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="popup" role="dialog" aria-modal="true" aria-labelledby="plugins-title">
        <div className="popup-head">
          <div>
            <h2 id="plugins-title">Plugins</h2>
            <p className="sub">Everything Rig reads from. Add a key, upload a file, or paste a link.</p>
          </div>
          <button type="button" className="text close" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="tabs" role="tablist">
          {PLUGIN_TABS.map((item) => (
            <button key={item.id} type="button" role="tab" aria-selected={tab === item.id} className={tab === item.id ? "on" : ""} onClick={() => setTab(item.id)}>
              {item.label}
            </button>
          ))}
        </div>

        {tab === "keys" ? (
          <div className="part">
            <div className="part-title">
              <h3>API keys</h3>
              <Tag />
            </div>
            <p className="intro">Keys for public feeds and your suppliers. A key is write-only: once saved it is never shown again.</p>
            <div className="list">
              {KEYS.map((row) => (
                <form key={row.id} className="key-row" onSubmit={(event) => { event.preventDefault(); saveRow(row.id, event.currentTarget); }}>
                  <div>
                    <h4>{row.name}</h4>
                    <p>{row.detail}</p>
                    <span className="env-label">{row.env}</span>
                  </div>
                  <Pill on={saved[row.id]}>{saved[row.id] ? "Connected" : "Not set"}</Pill>
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
                    <p>Supplier key</p>
                  </div>
                  <Pill>Connected</Pill>
                  <div className="mask">{MASK}</div>
                  <button type="button" className="text" onClick={() => setSuppliers((current) => current.filter((item) => item.id !== row.id))}>Remove</button>
                </div>
              ))}
              <form className="add" onSubmit={(event) => { event.preventDefault(); saveSupplier(event.currentTarget); }}>
                <div className="who">
                  <h4>Add a supplier key</h4>
                  <p>For a supplier that gives you an API key.</p>
                </div>
                <label>
                  Supplier name
                  <input name="supplier" type="text" placeholder="e.g. Acme Wholesale" autoComplete="off" />
                </label>
                <label>
                  Key
                  <input type="password" aria-label="Supplier key" placeholder="Paste key (hidden once saved)" autoComplete="off" />
                </label>
                <button type="submit" className="primary">Save key</button>
              </form>
            </div>
            <p className="note">Keys are stored on the server, never in the app code.</p>
          </div>
        ) : null}

        {tab === "files" ? (
          <div className="part">
            <div className="part-title">
              <h3>Files</h3>
              <Tag />
            </div>
            <p className="intro">Upload price lists, inventory, reports or rules. CSV files can be matched to the right columns.</p>
            <div className="drop" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); addFiles(event.dataTransfer.files); }}>
              <strong>Drag CSV, XLSX or PDF files here</strong>
              <span>or</span>
              <button type="button" className="primary" onClick={() => document.getElementById("rig-files")?.click()}>Choose files</button>
              <input id="rig-files" type="file" accept=".csv,.xlsx,.xls,.pdf" multiple hidden onChange={(event) => { addFiles(event.target.files); event.target.value = ""; }} />
            </div>
            <div className="list">
              <table className="file-table">
                <thead>
                  <tr>
                    <th>File</th>
                    <th>Type</th>
                    <th>Rows / pages</th>
                    <th>Uploaded</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {FILES.map((file) => (
                    <tr key={file.name}>
                      <td className="name">{file.name}</td>
                      <td>{file.type}</td>
                      <td>{file.size}</td>
                      <td>{file.when}</td>
                      <td><Pill on={file.on}>{file.status}</Pill></td>
                      <td>{file.map ? <button type="button" className="text">Map columns</button> : null}</td>
                    </tr>
                  ))}
                  {files.map((file) => (
                    <tr key={file.name}>
                      <td className="name">{file.name}</td>
                      <td>{file.type}</td>
                      <td>—</td>
                      <td>—</td>
                      <td><Pill on={false}>Needs checking</Pill></td>
                      <td />
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}

        {tab === "links" ? (
          <div className="part">
            <div className="part-title">
              <h3>Source links</h3>
              <Tag />
            </div>
            <p className="intro">Pages Rig checks for changes, such as rule pages, season dates or port stats.</p>
            <form className="list" onSubmit={(event) => { event.preventDefault(); addLink(event.currentTarget); }}>
              <div className="stack link-add">
                <label>
                  Link
                  <input name="link" type="url" placeholder="Paste a link, e.g. https://…" autoComplete="off" />
                </label>
                <label>
                  Label (optional)
                  <input name="label" type="text" placeholder="e.g. Texas seasons" autoComplete="off" />
                </label>
                <div>
                  <span className="env-label">How often to check</span>
                  <div className="seg" role="group" aria-label="How often to check">
                    <button type="button" className={often === "Daily" ? "on" : ""} onClick={() => setOften("Daily")}>Daily</button>
                    <button type="button" className={often === "Weekly" ? "on" : ""} onClick={() => setOften("Weekly")}>Weekly</button>
                  </div>
                </div>
                <button type="submit" className="primary">Add link</button>
              </div>
            </form>
            <div className="list">
              {LINKS.map((link) => (
                <div className="link-row" key={link.host}>
                  <div>
                    <h4>{link.label}</h4>
                    <span className="host">{link.host}</span>
                  </div>
                  <span className="checked">Last checked <b>{link.checked}</b></span>
                  <Pill on={link.on}>{link.status}</Pill>
                  <button type="button" className="text">Remove</button>
                </div>
              ))}
              {links.map((link) => (
                <div className="link-row" key={`${link.host}-${link.label}`}>
                  <div>
                    <h4>{link.label}</h4>
                    <span className="host">{link.host}</span>
                  </div>
                  <span className="checked">Last checked <b>—</b></span>
                  <Pill>Watching</Pill>
                  <button type="button" className="text" onClick={() => setLinks((current) => current.filter((item) => item !== link))}>Remove</button>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {tab === "mcp" ? (
          <div className="part">
            <div className="part-title">
              <h3>MCP connections</h3>
              <Tag />
            </div>
            <p className="intro">Connections to outside tools and data servers that Rig can read from.</p>
            <div className="list">
              {CONNECTIONS.map((row) => (
                <div className="conn-row" key={row.host}>
                  <div>
                    <h4>{row.name}</h4>
                    <span className="host">{row.host}</span>
                  </div>
                  <p>{row.detail}</p>
                  <Pill on={row.on}>{row.status}</Pill>
                  <span className="checked">Last used <b>{row.used}</b></span>
                  <button type="button" className="text">Disconnect</button>
                </div>
              ))}
              {connections.map((row) => (
                <div className="conn-row" key={`${row.host}-${row.name}`}>
                  <div>
                    <h4>{row.name}</h4>
                    <span className="host">{row.host}</span>
                  </div>
                  <p>{row.tokenSaved ? MASK : "Sign in with the provider"}</p>
                  <Pill on={row.tokenSaved}>{row.tokenSaved ? "Connected" : "Needs sign-in"}</Pill>
                  <span className="checked">Last used <b>—</b></span>
                  <button type="button" className="text" onClick={() => setConnections((current) => current.filter((item) => item !== row))}>Disconnect</button>
                </div>
              ))}
            </div>
            <form className="list" onSubmit={(event) => { event.preventDefault(); addConnection(event.currentTarget); }}>
              <div className="stack">
                <h4>Add connection</h4>
                <div className="pair">
                  <label>
                    Name
                    <input name="conn-name" type="text" placeholder="e.g. Supplier catalogue" autoComplete="off" />
                  </label>
                  <label>
                    Server URL
                    <input name="server" type="url" placeholder="https://…" autoComplete="off" />
                  </label>
                </div>
                <div className="pair end">
                  <div>
                    <span className="env-label">How it signs in</span>
                    <div className="seg" role="group" aria-label="How it signs in">
                      <button type="button" className={signIn === "provider" ? "on" : ""} onClick={() => setSignIn("provider")}>Sign in with the provider</button>
                      <button type="button" className={signIn === "token" ? "on" : ""} onClick={() => setSignIn("token")}>Token</button>
                    </div>
                  </div>
                  {signIn === "token" ? (
                    <label>
                      Token
                      <input type="password" aria-label="Token" placeholder="Paste token (hidden once saved)" autoComplete="off" />
                    </label>
                  ) : null}
                  <button type="submit" className="primary">Add connection</button>
                </div>
                <p className="note">A saved token shows only as •••• saved 17 Oct, with Replace or Remove. It is never shown again.</p>
              </div>
            </form>
          </div>
        ) : null}
      </div>

      <div className="groups" role="dialog" aria-modal="true" aria-labelledby="plugins-sheet-title">
        <div className="sheet-head">
          <div>
            <h2 id="plugins-sheet-title">Plugins</h2>
            <p className="sub">Everything Rig reads from. Add a key, upload a file, or paste a link.</p>
          </div>
          <button type="button" className="text" onClick={onClose}>Close</button>
        </div>
        <section className="group">
          <h3>API keys <Tag /></h3>
          <p className="intro">Keys for public feeds and your suppliers. A key is write-only: once saved it is never shown again.</p>
          {KEYS.map((row) => (
            <form key={row.id} className="key-row" onSubmit={(event) => { event.preventDefault(); saveRow(row.id, event.currentTarget); }}>
              <div>
                <h4>{row.name}</h4>
                <p>{row.detail}</p>
                <span className="env-label">{row.env}</span>
              </div>
              <Pill on={saved[row.id]}>{saved[row.id] ? "Connected" : "Not set"}</Pill>
              {saved[row.id] ? <div className="mask">{MASK}</div> : <input type="password" aria-label={`${row.name} key`} placeholder="Paste key" autoComplete="off" />}
              {saved[row.id] ? (
                <button type="button" className="text" onClick={() => setSaved((current) => ({ ...current, [row.id]: false }))}>Replace</button>
              ) : (
                <button type="submit" className="line">Save</button>
              )}
            </form>
          ))}
          <form className="add" onSubmit={(event) => { event.preventDefault(); saveSupplier(event.currentTarget); }}>
            <div className="who">
              <h4>Add a supplier key</h4>
              <p>For a supplier that gives you an API key.</p>
            </div>
            <label>
              Supplier name
              <input name="supplier" type="text" placeholder="e.g. Acme Wholesale" autoComplete="off" />
            </label>
            <label>
              Key
              <input type="password" aria-label="Supplier key" placeholder="Paste key (hidden once saved)" autoComplete="off" />
            </label>
            <button type="submit" className="primary">Save key</button>
          </form>
          <p className="note">Keys are stored on the server, never in the app code.</p>
        </section>
        <section className="group">
          <h3>Files <Tag /></h3>
          <p className="intro">Upload price lists, inventory, reports or rules. CSV files can be matched to the right columns.</p>
          <div className="drop">
            <strong>Drag CSV, XLSX or PDF files here</strong>
            <span>or</span>
            <button type="button" className="line" onClick={() => document.getElementById("rig-files-mobile")?.click()}>Choose files</button>
            <input id="rig-files-mobile" type="file" accept=".csv,.xlsx,.xls,.pdf" multiple hidden onChange={(event) => { addFiles(event.target.files); event.target.value = ""; }} />
          </div>
          {FILES.map((file) => (
            <article className="file-card" key={file.name}>
              <h4>{file.name}</h4>
              <p>{file.type} · {file.size} · {file.when}</p>
              <Pill on={file.on}>{file.status}</Pill>
            </article>
          ))}
        </section>
        <section className="group">
          <h3>Source links <Tag /></h3>
          <p className="intro">Pages Rig checks for changes, such as rule pages, season dates or port stats.</p>
          {LINKS.map((link) => (
            <div className="link-row" key={link.host}>
              <div>
                <h4>{link.label}</h4>
                <span className="host">{link.host}</span>
              </div>
              <Pill on={link.on}>{link.status}</Pill>
              <span className="checked">Last checked {link.checked}</span>
            </div>
          ))}
        </section>
        <section className="group">
          <h3>MCP connections <Tag /></h3>
          <p className="intro">Connections to outside tools and data servers that Rig can read from.</p>
          {CONNECTIONS.map((row) => (
            <div className="conn-row" key={row.host}>
              <div>
                <h4>{row.name}</h4>
                <span className="host">{row.host}</span>
              </div>
              <p>{row.detail}</p>
              <Pill on={row.on}>{row.status}</Pill>
            </div>
          ))}
        </section>
      </div>
    </div>
  );
}
