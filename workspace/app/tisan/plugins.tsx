"use client";

import { useState } from "react";
import {
  CONNECTIONS,
  FILES,
  KEYS,
  LINKS,
  MASK,
  PLUGIN_TABS,
  type KeyId,
  type PluginTab,
} from "./copy";

type Supplier = { id: string; name: string };
type ExtraFile = { name: string; type: string };
type ExtraLink = { label: string; host: string };
type ExtraConnection = { name: string; host: string; tokenSaved: boolean };

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
  if (ext === "pdf") return "PDF";
  return ext ? ext.toUpperCase() : "File";
}

function btn(primary: boolean): string {
  return primary ? "primary" : "line";
}

export function Plugins({
  onClose,
  tab,
  setTab,
  desktopAction,
}: {
  onClose: () => void;
  tab: PluginTab;
  setTab: (tab: PluginTab) => void;
  desktopAction: string;
}) {
  const [saved, setSaved] = useState<Record<KeyId, boolean>>({
    github: true,
    packages: true,
    coolify: false,
    radix: false,
    preview: false,
  });
  const [suppliers, setSuppliers] = useState<Supplier[]>([]);
  const [files, setFiles] = useState<ExtraFile[]>([]);
  const [links, setLinks] = useState<ExtraLink[]>([]);
  const [often, setOften] = useState<"Daily" | "Weekly">("Daily");
  const [connections, setConnections] = useState<ExtraConnection[]>([]);
  const [signIn, setSignIn] = useState<"provider" | "token">("token");
  const [open, setOpen] = useState({ keys: true, files: true, links: true, mcp: true });

  function saveRow(id: KeyId, form: HTMLFormElement) {
    const field = form.querySelector<HTMLInputElement>("input[type=password]");
    if (!kept(field)) return;
    setSaved((current) => ({ ...current, [id]: true }));
  }

  function saveTool(form: HTMLFormElement) {
    const name = form.querySelector<HTMLInputElement>("input[name=tool]")?.value.trim() ?? "";
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

  const connected = KEYS.filter((row) => row.saved).length;
  const checking = FILES.filter((row) => row.status !== "Processed").length;
  const changed = LINKS.filter((row) => row.status === "Changed").length;
  const live = CONNECTIONS.filter((row) => row.status === "Connected").length;


  // Save key is the red button on the keys tab, and the only red button on the phone sheet.
  const saveKeyClass = (compact: boolean) => (compact || desktopAction === "save-key" ? "primary" : "line");

  return (
    <div className="scrim" role="presentation">
      <div className="popup" role="dialog" aria-modal="true" aria-labelledby="plugins-title">
        <div className="popup-head">
          <div>
            <h2 id="plugins-title">Plugins</h2>
            <p className="sub">Everything Tisan reads from. Add a key, upload a file, or paste a link.</p>
          </div>
          <button type="button" className="text" onClick={onClose}>Close</button>
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
            <div className="part-title"><h3>API keys</h3><Tag /></div>
            <p className="intro">Keys for tools Tisan may use. A key is write-only: once saved it is never shown again.</p>
            <div className="list">
              {KEYS.map((row) => (
                <form key={row.id} className="key-row" onSubmit={(event) => { event.preventDefault(); saveRow(row.id, event.currentTarget); }}>
                  <div>
                    <h4>{row.name}</h4>
                    <p>{row.detail}</p>
                    <span className="env-label">{row.env}</span>
                  </div>
                  {saved[row.id] ? <span className="pill solid"><i />Connected</span> : <span className="pill quiet"><i />Not set</span>}
                  {saved[row.id] ? <div className="mask">{MASK}</div> : <input type="password" aria-label={`${row.name} key`} placeholder="Paste key" autoComplete="off" />}
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
                    <p>Tool key · Example</p>
                  </div>
                  <span className="pill solid"><i />Connected</span>
                  <div className="mask">{MASK}</div>
                  <button type="button" className="text" onClick={() => setSuppliers((current) => current.filter((item) => item.id !== row.id))}>Remove</button>
                </div>
              ))}
              <form className="add" onSubmit={(event) => { event.preventDefault(); saveTool(event.currentTarget); }}>
                <div className="who">
                  <h4>Add a tool key</h4>
                  <p>For a host or tool that gives you a key.</p>
                </div>
                <label>
                  Tool name
                  <input name="tool" type="text" placeholder="e.g. Font host" autoComplete="off" />
                </label>
                <label>
                  Key
                  <input type="password" aria-label="Tool key" placeholder="Paste key (hidden once saved)" autoComplete="off" />
                </label>
                <button type="submit" className={saveKeyClass(false)}>Save key</button>
              </form>
            </div>
            <p className="note">Keys are stored on the server, never in the app code.</p>
          </div>
        ) : null}

        {tab === "files" ? (
          <div className="part">
            <div className="part-title"><h3>Files</h3><Tag /></div>
            <p className="intro">Upload copy, briefs or lists for the site. CSV files can be matched to the right columns.</p>
            <div className="drop" onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); addFiles(event.dataTransfer.files); }}>
              <strong>Drag CSV, XLSX or PDF files here</strong>
              <span>or</span>
              <button type="button" className={btn(desktopAction === "choose-files")} onClick={() => document.getElementById("tisan-files")?.click()}>Choose files</button>
              <input id="tisan-files" type="file" accept=".csv,.xlsx,.xls,.pdf" multiple hidden onChange={(event) => { addFiles(event.target.files); event.target.value = ""; }} />
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
                      <td><span className={file.status === "Processed" ? "pill solid" : "pill quiet"}><i />{file.status}</span></td>
                      <td>{file.map ? <button type="button" className="text">Map columns</button> : null}</td>
                    </tr>
                  ))}
                  {files.map((file) => (
                    <tr key={file.name}>
                      <td className="name">{file.name}</td>
                      <td>{file.type}</td>
                      <td>—</td>
                      <td>—</td>
                      <td><span className="pill quiet"><i />Needs checking</span></td>
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
            <div className="part-title"><h3>Source links</h3><Tag /></div>
            <p className="intro">Pages Tisan checks for changes, such as the live site or a page named in the brief.</p>
            <form className="list link-add" onSubmit={(event) => { event.preventDefault(); addLink(event.currentTarget); }}>
              <label>
                Link
                <input name="link" type="url" placeholder="Paste a link, e.g. https://…" autoComplete="off" />
              </label>
              <label>
                Label (optional)
                <input name="label" type="text" placeholder="e.g. Contact page" autoComplete="off" />
              </label>
              <div>
                <span className="env-label">How often to check</span>
                <div className="seg" role="group" aria-label="How often to check">
                  <button type="button" className={often === "Daily" ? "on" : ""} onClick={() => setOften("Daily")}>Daily</button>
                  <button type="button" className={often === "Weekly" ? "on" : ""} onClick={() => setOften("Weekly")}>Weekly</button>
                </div>
              </div>
              <button type="submit" className={btn(desktopAction === "add-link")}>Add link</button>
            </form>
            <div className="list">
              {LINKS.map((link) => (
                <div className="link-row" key={link.host}>
                  <div>
                    <h4>{link.label}</h4>
                    <span className="host">{link.host}</span>
                  </div>
                  <span>Last checked <b>{link.checked}</b></span>
                  <span className={link.status === "Watching" ? "pill solid" : "pill quiet"}><i />{link.status}</span>
                  <button type="button" className="text">Remove</button>
                </div>
              ))}
              {links.map((link) => (
                <div className="link-row" key={`${link.host}-${link.label}`}>
                  <div>
                    <h4>{link.label}</h4>
                    <span className="host">{link.host}</span>
                  </div>
                  <span>Last checked <b>—</b></span>
                  <span className="pill solid"><i />Watching</span>
                  <button type="button" className="text" onClick={() => setLinks((current) => current.filter((item) => item !== link))}>Remove</button>
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {tab === "mcp" ? (
          <div className="part">
            <div className="part-title"><h3>MCP connections</h3><Tag /></div>
            <p className="intro">Connections to outside tools that Tisan can read from.</p>
            <div className="list">
              {CONNECTIONS.map((row) => (
                <div className="conn-row" key={row.host}>
                  <div>
                    <h4>{row.name}</h4>
                    <span className="host">{row.host}</span>
                  </div>
                  <p>{row.detail}</p>
                  <span className={row.status === "Connected" ? "pill solid" : "pill quiet"}><i />{row.status}</span>
                  <span>Last used <b>{row.used}</b></span>
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
                  <span className={row.tokenSaved ? "pill solid" : "pill quiet"}><i />{row.tokenSaved ? "Connected" : "Needs sign-in"}</span>
                  <span>Last used <b>—</b></span>
                  <button type="button" className="text" onClick={() => setConnections((current) => current.filter((item) => item !== row))}>Disconnect</button>
                </div>
              ))}
            </div>
            <form className="list conn-add" onSubmit={(event) => { event.preventDefault(); addConnection(event.currentTarget); }}>
              <h4>Add connection</h4>
              <div className="pair">
                <label>
                  Name
                  <input name="conn-name" type="text" placeholder="e.g. Saved design" autoComplete="off" />
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
                ) : <span />}
                <button type="submit" className={btn(desktopAction === "add-connection")}>Add connection</button>
              </div>
              <p className="note">A saved token shows only as {MASK}, with Replace or Remove. It is never shown again.</p>
            </form>
          </div>
        ) : null}
      </div>

      <div className="groups" role="dialog" aria-modal="true" aria-labelledby="plugins-sheet-title">
        <div className="sheet-head">
          <div>
            <h2 id="plugins-sheet-title">Plugins</h2>
            <p className="sub">Everything Tisan reads from. Add a key, upload a file, or paste a link.</p>
          </div>
          <button type="button" className="text" onClick={onClose}>Close</button>
        </div>

        <section className="group">
          <button type="button" className="text group-toggle" aria-expanded={open.keys} onClick={() => setOpen((current) => ({ ...current, keys: !current.keys }))}>
            <h3>API keys</h3>
          </button>
          <p className="countline">{KEYS.length} keys · {connected} connected · Example</p>
          {open.keys ? (
            <>
              <p className="intro">Keys for tools Tisan may use. A key is write-only: once saved it is never shown again.</p>
              <div className="list">
                {KEYS.map((row) => (
                  <form key={row.id} className="key-row" onSubmit={(event) => { event.preventDefault(); saveRow(row.id, event.currentTarget); }}>
                    <div>
                      <h4>{row.name}</h4>
                      <p>{row.detail}</p>
                      <span className="env-label">{row.env}</span>
                    </div>
                    {saved[row.id] ? <span className="pill solid"><i />Connected</span> : <span className="pill quiet"><i />Not set</span>}
                    {saved[row.id] ? <div className="mask">{MASK}</div> : <input type="password" aria-label={`${row.name} key`} placeholder="Paste key" autoComplete="off" />}
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
                <form className="add" onSubmit={(event) => { event.preventDefault(); saveTool(event.currentTarget); }}>
                  <div className="who">
                    <h4>Add a tool key</h4>
                    <p>For a host or tool that gives you a key.</p>
                  </div>
                  <label>
                    Tool name
                    <input name="tool" type="text" placeholder="e.g. Font host" autoComplete="off" />
                  </label>
                  <label>
                    Key
                    <input type="password" aria-label="Tool key" placeholder="Paste key (hidden once saved)" autoComplete="off" />
                  </label>
                  <button type="submit" className="primary">Save key</button>
                </form>
              </div>
              <p className="note">Keys are stored on the server, never in the app code.</p>
            </>
          ) : null}
        </section>

        <section className="group">
          <button type="button" className="text group-toggle" aria-expanded={open.files} onClick={() => setOpen((current) => ({ ...current, files: !current.files }))}>
            <h3>Files</h3>
          </button>
          <p className="countline">{FILES.length} files · {checking} need checking · Example</p>
          {open.files ? (
            <>
              <p className="intro">Upload copy, briefs or lists for the site. CSV files can be matched to the right columns.</p>
              <div className="drop">
                <strong>Drag CSV, XLSX or PDF files here</strong>
                <span>or</span>
                <button type="button" className="line" onClick={() => document.getElementById("tisan-files-mobile")?.click()}>Choose files</button>
                <input id="tisan-files-mobile" type="file" accept=".csv,.xlsx,.xls,.pdf" multiple hidden onChange={(event) => { addFiles(event.target.files); event.target.value = ""; }} />
              </div>
              <div className="file-cards">
                {FILES.map((file) => (
                  <article className="file-card" key={file.name}>
                    <h4>{file.name}</h4>
                    <p>{file.type} · {file.size}</p>
                    <p>{file.when} · {file.status}</p>
                    {file.map ? <button type="button" className="text">Map columns</button> : null}
                  </article>
                ))}
              </div>
            </>
          ) : null}
        </section>

        <section className="group">
          <button type="button" className="text group-toggle" aria-expanded={open.links} onClick={() => setOpen((current) => ({ ...current, links: !current.links }))}>
            <h3>Source links</h3>
          </button>
          <p className="countline">{LINKS.length} links · {changed} changed · Example</p>
          {open.links ? (
            <>
              <p className="intro">Pages Tisan checks for changes, such as the live site or a page named in the brief.</p>
              <form className="list" onSubmit={(event) => { event.preventDefault(); addLink(event.currentTarget); }}>
                <div className="stack">
                  <label>
                    Link
                    <input name="link" type="url" placeholder="Paste a link, e.g. https://…" autoComplete="off" />
                  </label>
                  <label>
                    Label (optional)
                    <input name="label" type="text" placeholder="e.g. Contact page" autoComplete="off" />
                  </label>
                  <div className="seg">
                    <button type="button" className={often === "Daily" ? "on" : ""} onClick={() => setOften("Daily")}>Daily</button>
                    <button type="button" className={often === "Weekly" ? "on" : ""} onClick={() => setOften("Weekly")}>Weekly</button>
                  </div>
                  <button type="submit" className="line">Add link</button>
                </div>
              </form>
              <div className="list">
                {LINKS.map((link) => (
                  <div className="link-row" key={link.host}>
                    <div>
                      <h4>{link.label}</h4>
                      <span className="host">{link.host}</span>
                    </div>
                    <span className={link.status === "Watching" ? "pill solid" : "pill quiet"}><i />{link.status}</span>
                    <span>Last checked {link.checked}</span>
                  </div>
                ))}
              </div>
            </>
          ) : null}
        </section>

        <section className="group">
          <button type="button" className="text group-toggle" aria-expanded={open.mcp} onClick={() => setOpen((current) => ({ ...current, mcp: !current.mcp }))}>
            <h3>MCP connections</h3>
          </button>
          <p className="countline">{CONNECTIONS.length} connections · {live} connected · Example</p>
          {open.mcp ? (
            <>
              <p className="intro">Connections to outside tools that Tisan can read from.</p>
              <div className="list">
                {CONNECTIONS.map((row) => (
                  <div className="conn-row" key={row.host}>
                    <div>
                      <h4>{row.name}</h4>
                      <span className="host">{row.host}</span>
                    </div>
                    <p>{row.detail}</p>
                    <span className={row.status === "Connected" ? "pill solid" : "pill quiet"}><i />{row.status}</span>
                    <span>Last used {row.used}</span>
                  </div>
                ))}
              </div>
              <form className="list" onSubmit={(event) => { event.preventDefault(); addConnection(event.currentTarget); }}>
                <div className="stack">
                  <h4>Add connection</h4>
                  <label>
                    Name
                    <input name="conn-name" type="text" placeholder="e.g. Saved design" autoComplete="off" />
                  </label>
                  <label>
                    Server URL
                    <input name="server" type="url" placeholder="https://…" autoComplete="off" />
                  </label>
                  <div className="seg">
                    <button type="button" className={signIn === "provider" ? "on" : ""} onClick={() => setSignIn("provider")}>Sign in with the provider</button>
                    <button type="button" className={signIn === "token" ? "on" : ""} onClick={() => setSignIn("token")}>Token</button>
                  </div>
                  {signIn === "token" ? (
                    <label>
                      Token
                      <input type="password" aria-label="Token" placeholder="Paste token (hidden once saved)" autoComplete="off" />
                    </label>
                  ) : null}
                  <button type="submit" className="line">Add connection</button>
                  <p className="note">A saved token shows only as {MASK}, with Replace or Remove. It is never shown again.</p>
                </div>
              </form>
            </>
          ) : null}
        </section>
      </div>
    </div>
  );
}
