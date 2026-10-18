"use client";

import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { AGENT_LABEL, Registry } from "./registry";
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

const REGISTRY_TABS = [
  { id: "skills", label: "Skills" },
  { id: "tier0", label: AGENT_LABEL.tier0 },
  { id: "base", label: AGENT_LABEL.base },
  { id: "orchestrator", label: AGENT_LABEL.orchestrator },
  { id: "archive", label: "Archive" },
] as const;

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
  const [section, setSection] = useState<string>("skills");
  const [pluginsOpen, setPluginsOpen] = useState(false);
  const [tab, setTab] = useState<PluginTab>("API keys");
  const [menu, setMenu] = useState(false);
  const [query, setQuery] = useState("");
  const [askDraft, setAskDraft] = useState("");
  const [thread, setThread] = useState<Turn[]>([]);
  const [botOpen, setBotOpen] = useState(false);
  const searchId = useId();
  const account = accountName?.trim() || "Account name";

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setPluginsOpen(false);
      setMenu(false);
      setBotOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function show(next: string) {
    setMenu(false);
    setPluginsOpen(false);
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

  return (
    <div className={menu ? "skala menu-open" : "skala"}>
      <header className="sk-top">
        <img src="/brand/tervory-logo-reversed.png" alt="Tervory" width={148} height={28} />
        <button type="button" className="sk-menu" onClick={() => setMenu(true)}>Menu</button>
      </header>
      <button className="sk-dim" type="button" hidden={!menu} aria-label="Close menu" onClick={() => setMenu(false)} />
      <aside className="sk-panel" aria-label="Skala">
        <div className="sk-brand">
          <img className="sk-logo" src="/brand/tervory-logo-reversed.png" alt="Tervory" width={186} height={34} />
          <img className="sk-word" src="/brand/skala-on-dark.png" alt="Skala" />
        </div>
        <button className="sk-close" type="button" onClick={() => setMenu(false)}>Close</button>
        <nav className="sk-nav" aria-label="Account">
          <p className="sk-account">{account}</p>
          {TOP_LINKS.map((link) => (
            <a key={link.label} href={link.href}>{link.label}</a>
          ))}
        </nav>
        <nav className="sk-own" aria-label="Skala registry">
          {REGISTRY_TABS.map((item) => (
            <button key={item.id} type="button" className={!pluginsOpen && section === item.id ? "on" : ""} onClick={() => show(item.id)}>
              {item.label}
            </button>
          ))}
          <button type="button" className={pluginsOpen ? "on" : ""} onClick={() => { setMenu(false); setPluginsOpen(true); }}>
            Plugins
          </button>
        </nav>
        <div className="sk-spacer" />
        <nav className="sk-nav" aria-label="Workspace">
          {BOTTOM_LINKS.map((link) => (
            <a key={link.label} href={link.href}>{link.label}</a>
          ))}
        </nav>
      </aside>

      <div className="sk-main" data-scroll-root>
        <div className="sk-body">
          <header className="sk-head">
            <img className="sk-word-light" src="/brand/skala-on-light.png" alt="" />
            <div>
              <h1>Skala</h1>
              <p>The skills registry. Search the packages, or ask a question. Only approved versions run for clients.</p>
            </div>
          </header>

          <form className="sk-search" role="search" onSubmit={(event) => event.preventDefault()}>
            <SearchIcon />
            <label className="sk-sr" htmlFor={searchId}>Search skills</label>
            <input
              id={searchId}
              type="search"
              value={query}
              placeholder="Search skills"
              onChange={(event) => setQuery(event.target.value)}
            />
          </form>

          <p className="sk-library">{library.enabled ? `${library.skills.length} approved skills are in the library.` : library.message || LIBRARY_OFF_MESSAGE}</p>

          {pluginsOpen ? (
            <PluginsPanel plugins={plugins} tab={tab} onTab={setTab} onClose={() => setPluginsOpen(false)} />
          ) : (
            <Registry query={query} section={section} />
          )}

          <section className="sk-ask" aria-label="Ask Skala">
            <h2>Ask Skala</h2>
            {thread.length > 0 && (
              <div className="sk-thread">
                {thread.map((turn, index) => (
                  <div key={`${turn.who}-${index}`} className={turn.who === "You" ? "sk-turn you" : "sk-turn"}>
                    <p className="sk-who">{turn.who}</p>
                    <p>{turn.text}</p>
                  </div>
                ))}
              </div>
            )}
            <form onSubmit={sendAsk}>
              <label className="sk-sr" htmlFor="ask-skala">Ask Skala</label>
              <textarea
                id="ask-skala"
                rows={3}
                value={askDraft}
                placeholder="Ask about a skill"
                onChange={(event) => setAskDraft(event.target.value)}
              />
              <button type="submit" className="primary">Send</button>
            </form>
          </section>
        </div>
      </div>

      <div className="sk-bot">
        {botOpen && (
          <div className="sk-bot-card" role="dialog" aria-label="Chat bot, to be named">
            <p>Chat bot, to be named</p>
            <p>This bot is not connected. Nothing was sent.</p>
            <button type="button" onClick={() => setBotOpen(false)}>Close</button>
          </div>
        )}
        <button type="button" className="sk-bot-btn" onClick={() => setBotOpen((open) => !open)}>
          Chat bot, to be named
        </button>
      </div>
    </div>
  );
}

function PluginsPanel({
  plugins,
  tab,
  onTab,
  onClose,
}: {
  plugins: PluginPanel;
  tab: PluginTab;
  onTab: (tab: PluginTab) => void;
  onClose: () => void;
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
      <div className="sk-plugins-head">
        <h2>Plugins</h2>
        <button type="button" className="text" onClick={onClose}>Close</button>
      </div>
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
