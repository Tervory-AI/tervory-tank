"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  LIBRARY_OFF_MESSAGE,
  PLUGIN_TABS,
  STUB_FILE,
  STUB_KEY,
  STUB_LINK,
  STUB_MCP,
  VAULT_OFF_MESSAGE,
  type ConnectionMeta,
  type LibraryPanel,
  type PluginPanel,
  type PluginTab,
  type SecretMeta,
} from "./plugins";
import {
  addSkalaConnection,
  addSkalaLink,
  removeSkalaConnection,
  removeSkalaFile,
  removeSkalaLink,
  removeSkalaSecret,
  saveSkalaKey,
  uploadSkalaFiles,
} from "./plugin-actions";

const TOP_LINKS = [
  { href: "/ledger", label: "Dashboard" },
  { href: "/tasks", label: "Projects" },
  { href: "/", label: "Chats" },
] as const;

const BOTTOM_LINKS = [
  { href: "/onboarding", label: "Settings" },
  { href: "/", label: "Support" },
] as const;

type Section = "library" | "plugins";
type Turn = { who: "You" | "Skala"; text: string };

function SearchIcon() {
  return (
    <svg className="search-icon" width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <circle cx="7.5" cy="7.5" r="4.75" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M11.2 11.2 L15.5 15.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function SkalaApp({
  accountName,
  plugins,
  library,
}: {
  accountName: string | null;
  plugins: PluginPanel;
  library: LibraryPanel;
}) {
  const [section, setSection] = useState<Section>("library");
  const [tab, setTab] = useState<PluginTab>("API keys");
  const [menu, setMenu] = useState(false);
  const [query, setQuery] = useState("");
  const [askDraft, setAskDraft] = useState("");
  const [thread, setThread] = useState<Turn[]>([]);
  const searchId = useId();
  const account = accountName?.trim() || "Account name";

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setMenu(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function show(next: Section) {
    setMenu(false);
    setSection(next);
  }

  function sendAsk(event: FormEvent) {
    event.preventDefault();
    const text = askDraft.trim();
    if (!text) return;
    setAskDraft("");
    setThread((current) => [
      ...current,
      { who: "You", text },
      { who: "Skala", text: "Ask Skala is not connected from this page yet. Nothing was run." },
    ]);
  }

  const needle = query.trim().toLowerCase();
  const skills = library.enabled
    ? library.skills.filter((skill) => {
        if (!needle) return true;
        return [skill.skill_id, skill.version, skill.agent, skill.description].join(" ").toLowerCase().includes(needle);
      })
    : [];

  return (
    <div className={menu ? "skala menu-open" : "skala"}>
      <header className="sk-top">
        <img src="/brand/skala-on-dark.png" alt="Skala" width={140} height={33} />
        <button type="button" className="sk-menu" onClick={() => setMenu(true)}>Menu</button>
      </header>
      <button className="sk-dim" type="button" hidden={!menu} aria-label="Close menu" onClick={() => setMenu(false)} />
      <aside className="sk-panel" aria-label="Skala">
        <img className="sk-logo" src="/brand/skala-on-dark.png" alt="Skala" width={186} height={44} />
        <button className="sk-close" type="button" onClick={() => setMenu(false)}>Close</button>
        <nav className="sk-nav" aria-label="Account">
          <p className="sk-account">{account}</p>
          {TOP_LINKS.map((link) => (
            <a key={link.label} href={link.href}>{link.label}</a>
          ))}
        </nav>
        <div className="sk-rule" />
        <nav className="sk-nav" aria-label="Library and Plugins">
          <button type="button" className={section === "library" ? "on" : ""} onClick={() => show("library")}>Library</button>
          <button type="button" className={section === "plugins" ? "on" : ""} onClick={() => show("plugins")}>Plugins</button>
        </nav>
        <div className="sk-spacer" />
        <div className="sk-rule" />
        <div className="sk-foot">
          <img className="sk-tervory" src="/brand/tervory-logo-reversed.png" alt="Tervory" width={186} height={34} />
          <nav className="sk-nav" aria-label="Workspace">
            {BOTTOM_LINKS.map((link) => (
              <a key={link.label} href={link.href}>{link.label}</a>
            ))}
          </nav>
        </div>
      </aside>

      <div className="sk-main" data-scroll-root>
        <div className="sk-body">
          {section === "plugins" ? (
            <PluginsPanel plugins={plugins} tab={tab} onTab={setTab} />
          ) : (
            <>
              <header className="sk-header">
                <div>
                  <h1>Skala</h1>
                  <p>Search the skills library, or ask Skala a question.</p>
                </div>
                <form className="sk-search" role="search" onSubmit={(event) => event.preventDefault()}>
                  <SearchIcon />
                  <label className="sk-sr" htmlFor={searchId}>Search the library</label>
                  <input
                    id={searchId}
                    type="search"
                    value={query}
                    placeholder="Search the library"
                    onChange={(event) => setQuery(event.target.value)}
                  />
                </form>
              </header>

              <section className="sk-ask" aria-label="Ask Skala">
                <h2>Ask Skala</h2>
                {thread.length > 0 && (
                  <div className="sk-thread">
                    {thread.map((turn, index) => (
                      <div key={`${turn.who}-${index}`} className="sk-turn">
                        <p className="sk-who">{turn.who}</p>
                        <p>{turn.text}</p>
                      </div>
                    ))}
                  </div>
                )}
                <form onSubmit={sendAsk}>
                  <label className="sk-sr" htmlFor="ask-skala">Ask Skala</label>
                  <input
                    id="ask-skala"
                    value={askDraft}
                    placeholder="Ask Skala"
                    onChange={(event) => setAskDraft(event.target.value)}
                  />
                  <button type="submit" className="primary">Send</button>
                </form>
              </section>

              {library.enabled ? (
                skills.length > 0 ? (
                  <ul className="sk-skills">
                    {skills.map((skill) => (
                      <li key={`${skill.skill_id}@${skill.version}`}>
                        <strong>{skill.skill_id}</strong>
                        <span>{skill.version}</span>
                        <span>{skill.description}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="sk-off">{needle ? "Nothing in the library matches that." : "The library is empty."}</p>
                )
              ) : (
                <p className="sk-off">{library.message || LIBRARY_OFF_MESSAGE}</p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function PluginsPanel({
  plugins,
  tab,
  onTab,
}: {
  plugins: PluginPanel;
  tab: PluginTab;
  onTab: (tab: PluginTab) => void;
}) {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);

  async function finish(result: { ok: boolean; message: string }) {
    setNote(result.message);
    if (result.ok) router.refresh();
  }

  async function onSaveKey(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!plugins.enabled || busy) return;
    const form = event.currentTarget;
    const name = form.querySelector<HTMLInputElement>("input[name=key-name]")?.value ?? "";
    const purpose = form.querySelector<HTMLInputElement>("input[name=purpose]")?.value ?? "";
    const value = form.querySelector<HTMLInputElement>("input[type=password]")?.value ?? "";
    form.reset();
    if (!name.trim() || !value.trim()) {
      setNote(STUB_KEY);
      return;
    }
    setBusy(true);
    try {
      await finish(await saveSkalaKey(name, value, purpose));
    } finally {
      setBusy(false);
    }
  }

  async function onFiles(list: FileList | null) {
    if (!plugins.enabled || busy) return;
    const files = list ? Array.from(list) : [];
    if (fileRef.current) fileRef.current.value = "";
    if (!files.length) {
      setNote(STUB_FILE);
      return;
    }
    const body = new FormData();
    for (const file of files) body.append("file", file);
    setBusy(true);
    try {
      await finish(await uploadSkalaFiles(body));
    } finally {
      setBusy(false);
    }
  }

  async function onAddLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!plugins.enabled || busy) return;
    const form = event.currentTarget;
    const url = form.querySelector<HTMLInputElement>("input[name=link]")?.value.trim() ?? "";
    const label = form.querySelector<HTMLInputElement>("input[name=label]")?.value.trim() ?? "";
    form.reset();
    if (!url) {
      setNote(STUB_LINK);
      return;
    }
    setBusy(true);
    try {
      await finish(await addSkalaLink(url, label, "weekly"));
    } finally {
      setBusy(false);
    }
  }

  async function onAddConnection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!plugins.enabled || busy) return;
    const form = event.currentTarget;
    const name = form.querySelector<HTMLInputElement>("input[name=connection-name]")?.value.trim() ?? "";
    const url = form.querySelector<HTMLInputElement>("input[name=server]")?.value.trim() ?? "";
    const token = form.querySelector<HTMLInputElement>("input[type=password]")?.value ?? "";
    form.reset();
    if (!name || !url) {
      setNote(STUB_MCP);
      return;
    }
    setBusy(true);
    try {
      await finish(await addSkalaConnection(name, url, token.trim() ? "token" : "provider", token));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="sk-plugins" aria-label="Plugins">
      <header className="sk-header">
        <div>
          <h1>Plugins</h1>
          <p>API keys, files, source links, and connections.</p>
        </div>
      </header>
      <div className="sk-tabs" role="tablist">
        {PLUGIN_TABS.map((name) => (
          <button key={name} type="button" role="tab" aria-selected={name === tab} className={name === tab ? "on" : ""} onClick={() => { setNote(""); onTab(name); }}>
            {name}
          </button>
        ))}
      </div>
      {note ? <p className="sk-note">{note}</p> : null}
      {!plugins.enabled ? (
        <p className="sk-off">{plugins.message || VAULT_OFF_MESSAGE}</p>
      ) : tab === "API keys" ? (
        <div>
          <ul className="sk-plist">
            {plugins.secrets.map((row) => (
              <SecretRow key={row.name} row={row} busy={busy} onRemove={() => { setBusy(true); removeSkalaSecret(row.name).then(finish).finally(() => setBusy(false)); }} />
            ))}
          </ul>
          <form className="sk-form" onSubmit={onSaveKey}>
            <input name="key-name" aria-label="Key name" placeholder="Key name" />
            <input name="purpose" aria-label="What this key is for" placeholder="What this key is for" />
            <input type="password" aria-label="Key" placeholder="Key" autoComplete="off" />
            <button type="submit" className="primary" disabled={busy}>Save key</button>
          </form>
        </div>
      ) : tab === "Files" ? (
        <div>
          <ul className="sk-plist">
            {plugins.files.map((file) => (
              <li key={file.id}>
                <strong>{file.name}</strong>
                <span>{file.status}</span>
                <button type="button" className="text" disabled={busy} onClick={() => { setBusy(true); removeSkalaFile(file.id).then(finish).finally(() => setBusy(false)); }}>Remove</button>
              </li>
            ))}
          </ul>
          <form className="sk-form" onSubmit={(event) => { event.preventDefault(); onFiles(fileRef.current?.files ?? null); }}>
            <input ref={fileRef} type="file" name="file" accept=".csv,.xlsx,.pdf,text/csv,application/pdf" multiple aria-label="Choose files" />
            <button type="submit" className="primary" disabled={busy}>Choose files</button>
          </form>
        </div>
      ) : tab === "Source links" ? (
        <div>
          <ul className="sk-plist">
            {plugins.links.map((link) => (
              <li key={link.id}>
                <strong>{link.label}</strong>
                <span>{link.url}</span>
                <button type="button" className="text" disabled={busy} onClick={() => { setBusy(true); removeSkalaLink(link.id).then(finish).finally(() => setBusy(false)); }}>Remove</button>
              </li>
            ))}
          </ul>
          <form className="sk-form" onSubmit={onAddLink}>
            <input name="label" aria-label="Link label" placeholder="Label" />
            <input name="link" aria-label="Link" placeholder="https://" />
            <button type="submit" className="primary" disabled={busy}>Add link</button>
          </form>
        </div>
      ) : (
        <div>
          <ul className="sk-plist">
            {plugins.connections.map((item) => (
              <ConnectionRow key={item.id} item={item} busy={busy} onRemove={() => { setBusy(true); removeSkalaConnection(item.id).then(finish).finally(() => setBusy(false)); }} />
            ))}
          </ul>
          <form className="sk-form" onSubmit={onAddConnection}>
            <input name="connection-name" aria-label="Connection name" placeholder="Name" />
            <input name="server" aria-label="Server URL" placeholder="https://" />
            <input type="password" aria-label="Token" placeholder="Token, if this connection uses one" autoComplete="off" />
            <button type="submit" className="primary" disabled={busy}>Add connection</button>
          </form>
        </div>
      )}
    </section>
  );
}

function SecretRow({ row, busy, onRemove }: { row: SecretMeta; busy: boolean; onRemove: () => void }) {
  return (
    <li>
      <strong>{row.name}</strong>
      <span>{row.purpose}</span>
      <span className="sk-mask">{row.mask || "••••••••"}</span>
      <button type="button" className="text" disabled={busy} onClick={onRemove}>Remove</button>
    </li>
  );
}

function ConnectionRow({ item, busy, onRemove }: { item: ConnectionMeta; busy: boolean; onRemove: () => void }) {
  return (
    <li>
      <strong>{item.name}</strong>
      <span>{item.serverUrl}</span>
      <span>{item.hasToken ? "••••••••" : item.status}</span>
      <button type="button" className="text" disabled={busy} onClick={onRemove}>Remove</button>
    </li>
  );
}
