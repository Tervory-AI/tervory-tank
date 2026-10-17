"use client";

/*
 * Plugins tab: API keys, Files, Source links and MCP connections. It uses the approved Market Lab pop-up design
 * (Figma 63:97, 63:239, 63:367, 63:475, 63:601), with copy for Base. "Sources" is not used here: on this page
 * Sources only means the references that come back with an answer. Rows are design examples and are labelled Example.
 * Nothing here is wired to a server yet: no key, file, link or token leaves the browser.
 * A saved key or token only ever shows as dots.
 */

import { useEffect, useRef, useState, type FormEvent } from "react";

export type PluginsTab = "keys" | "files" | "links" | "mcp";

const TABS: { id: PluginsTab; label: string }[] = [
  { id: "keys", label: "API keys" },
  { id: "files", label: "Files" },
  { id: "links", label: "Source links" },
  { id: "mcp", label: "MCP connections" },
];

const NOT_CONNECTED = "Not connected yet. Nothing was saved or sent.";

type KeyRow = { name: string; unlocks: string; env: string; saved: string | null };
const KEY_ROWS: KeyRow[] = [
  { name: "Licence list supplier", unlocks: "Monthly licence list from your supplier", env: "LICENCE_LIST_KEY", saved: "17 Oct" },
  { name: "Business data supplier", unlocks: "Company size and staff counts", env: "BUSINESS_DATA_KEY", saved: "17 Oct" },
  { name: "Maps lookup", unlocks: "Checks a street address", env: "MAPS_API_KEY", saved: null },
  { name: "Email checker", unlocks: "Checks an email can receive mail", env: "EMAIL_CHECK_KEY", saved: null },
  { name: "Phone checker", unlocks: "Checks a phone number is in service", env: "PHONE_CHECK_KEY", saved: null },
];

type FileRow = { name: string; type: string; size: string; uploaded: string; processed: boolean; map: boolean };
const FILE_ROWS: FileRow[] = [
  { name: "atf-ffl-list-sep-2026-nv.csv", type: "CSV", size: "1,240 rows", uploaded: "16 Oct", processed: true, map: true },
  { name: "dealer-list.xlsx", type: "XLSX", size: "3,880 rows", uploaded: "15 Oct", processed: false, map: false },
  { name: "licence-notes.pdf", type: "PDF", size: "42 pages", uploaded: "12 Oct", processed: true, map: false },
  { name: "retail-shops-oct.csv", type: "CSV", size: "610 rows", uploaded: "10 Oct", processed: false, map: true },
];

type LinkRow = { label: string; host: string; checked: string; state: "Watching" | "Changed" | "Couldn't reach" };
const LINK_ROWS: LinkRow[] = [
  { label: "ATF licence list", host: "atf.gov", checked: "Today, 7:00 AM", state: "Watching" },
  { label: "Dealer list (shared file)", host: "drive.google.com", checked: "Yesterday", state: "Changed" },
  { label: "State licence records", host: "example-state.gov", checked: "16 Oct", state: "Couldn't reach" },
];

type McpRow = { name: string; host: string; gives: string; state: "Connected" | "Needs sign-in" | "Error"; used: string };
const MCP_ROWS: McpRow[] = [
  { name: "Customer records", host: "crm.example-company.com", gives: "Shops you already sell to", state: "Connected", used: "Today, 7:10 AM" },
  { name: "Licence lookup", host: "mcp.example-licence.com", gives: "Checks a licence number", state: "Needs sign-in", used: "Never" },
  { name: "News monitor", host: "news.example-mcp.org", gives: "News that mentions a shop", state: "Error", used: "14 Oct" },
];

function Example() {
  return <span className="bcp-example">Example</span>;
}

function Pill({ label, on }: { label: string; on: boolean }) {
  return (
    <span className={on ? "bcp-pill on" : "bcp-pill"}>
      <i aria-hidden="true" />
      {label}
    </span>
  );
}

function Notice({ text }: { text: string | null }) {
  return (
    <p className="bcp-notice" role="status" aria-live="polite">
      {text ?? ""}
    </p>
  );
}

function useNotice(): [string | null, (event?: FormEvent) => void] {
  const [text, setText] = useState<string | null>(null);
  return [
    text,
    (event?: FormEvent) => {
      event?.preventDefault();
      setText(NOT_CONNECTED);
    },
  ];
}

function PartHead({ title, copy }: { title: string; copy: string }) {
  return (
    <div className="bcp-part-head">
      <div className="bcp-part-title">
        <h3>{title}</h3>
        <Example />
      </div>
      <p>{copy}</p>
    </div>
  );
}

function KeysTab() {
  const [notice, stop] = useNotice();
  return (
    <>
      <PartHead
        title="API keys"
        copy="Keys for the services and suppliers Base checks with. A key is write-only: once saved it is never shown again."
      />
      <div className="bcp-list">
        {KEY_ROWS.map((row) => (
          <form key={row.env} className="bcp-key-row" onSubmit={stop}>
            <div className="bcp-key-what">
              <p className="bcp-row-title">{row.name}</p>
              <p className="bcp-row-copy">{row.unlocks}</p>
              <p className="bcp-env">{row.env}</p>
            </div>
            <div>
              <Pill label={row.saved ? "Connected" : "Not set"} on={Boolean(row.saved)} />
            </div>
            {row.saved ? (
              <>
                <p className="bcp-input bcp-saved" aria-label={`${row.name} key, saved`}>
                  <span aria-hidden="true">••••</span> saved {row.saved}
                </p>
                <div className="bcp-actions">
                  <button type="button" className="bcp-text-btn" onClick={() => stop()}>
                    Replace
                  </button>
                  <button type="button" className="bcp-text-btn" onClick={() => stop()}>
                    Remove
                  </button>
                </div>
              </>
            ) : (
              <>
                <input
                  className="bcp-input"
                  type="password"
                  autoComplete="off"
                  spellCheck={false}
                  placeholder="Paste key"
                  aria-label={`${row.name} key`}
                />
                <div className="bcp-actions">
                  <button type="submit" className="bcp-secondary">
                    Save
                  </button>
                </div>
              </>
            )}
          </form>
        ))}
        <form className="bcp-key-row bcp-add" onSubmit={stop}>
          <div className="bcp-key-what">
            <p className="bcp-row-title">Add a supplier key</p>
            <p className="bcp-row-copy">For a supplier that gives you an API key.</p>
          </div>
          <label className="bcp-field">
            <span>Supplier name</span>
            <input className="bcp-input" type="text" placeholder="e.g. Acme Wholesale" autoComplete="off" />
          </label>
          <label className="bcp-field">
            <span>Key</span>
            <input className="bcp-input" type="password" placeholder="Paste key (hidden once saved)" autoComplete="off" spellCheck={false} />
          </label>
          <div className="bcp-actions">
            <button type="submit" className="bcp-primary">
              Save key
            </button>
          </div>
        </form>
      </div>
      <Notice text={notice} />
      <p className="bcp-fine">Keys are stored on the server, never in the app code.</p>
    </>
  );
}

function FilesTab() {
  const [notice, stop] = useNotice();
  const input = useRef<HTMLInputElement>(null);
  return (
    <>
      <PartHead
        title="Files"
        copy="Upload a list of businesses for Base to fill in, such as a licence list. CSV files can be matched to the right columns."
      />
      <div className="bcp-drop">
        <p className="bcp-row-title">Drag CSV, XLSX or PDF files here</p>
        <p className="bcp-row-copy">or</p>
        <button type="button" className="bcp-primary" onClick={() => input.current?.click()}>
          Choose files
        </button>
        <input
          ref={input}
          type="file"
          hidden
          accept=".csv,.xlsx,.pdf"
          onChange={(event) => {
            event.currentTarget.value = "";
            stop();
          }}
        />
      </div>
      <div className="bcp-table" role="table" aria-label="Files">
        <div className="bcp-tr bcp-th bcp-file-cols" role="row">
          <span role="columnheader">File</span>
          <span role="columnheader">Type</span>
          <span role="columnheader">Rows / pages</span>
          <span role="columnheader">Uploaded</span>
          <span role="columnheader">Status</span>
          <span role="columnheader" className="bcp-sr">Action</span>
        </div>
        {FILE_ROWS.map((row) => (
          <div key={row.name} className="bcp-tr bcp-file-cols" role="row">
            <span role="cell" className="bcp-name">{row.name}</span>
            <span role="cell" data-label="Type">{row.type}</span>
            <span role="cell" data-label="Rows / pages">{row.size}</span>
            <span role="cell" data-label="Uploaded">{row.uploaded}</span>
            <span role="cell" data-label="Status">
              <Pill label={row.processed ? "Processed" : "Needs checking"} on={row.processed} />
            </span>
            <span role="cell">
              {row.map ? (
                <button type="button" className="bcp-text-btn" onClick={() => stop()}>
                  Map columns
                </button>
              ) : null}
            </span>
          </div>
        ))}
      </div>
      <Notice text={notice} />
    </>
  );
}

function LinksTab() {
  const [notice, stop] = useNotice();
  const [often, setOften] = useState<"daily" | "weekly">("daily");
  return (
    <>
      <PartHead title="Source links" copy="Lists Base can import from a link, such as a shared Drive file or a public licence list." />
      <form className="bcp-box bcp-link-form" onSubmit={stop}>
        <label className="bcp-field bcp-grow">
          <span>Link</span>
          <input className="bcp-input" type="url" placeholder="Paste a link, e.g. https://…" autoComplete="off" />
        </label>
        <label className="bcp-field">
          <span>Label (optional)</span>
          <input className="bcp-input" type="text" placeholder="e.g. ATF licence list" autoComplete="off" />
        </label>
        <div className="bcp-field">
          <span>How often to check</span>
          <div className="bcp-toggle" role="group" aria-label="How often to check">
            <button type="button" aria-pressed={often === "daily"} onClick={() => setOften("daily")}>
              Daily
            </button>
            <button type="button" aria-pressed={often === "weekly"} onClick={() => setOften("weekly")}>
              Weekly
            </button>
          </div>
        </div>
        <div className="bcp-actions">
          <button type="submit" className="bcp-primary">
            Add link
          </button>
        </div>
      </form>
      <div className="bcp-list">
        {LINK_ROWS.map((row) => (
          <div key={row.host} className="bcp-link-row">
            <div>
              <p className="bcp-row-title">{row.label}</p>
              <p className="bcp-env">{row.host}</p>
            </div>
            <div>
              <p className="bcp-env">Last checked</p>
              <p className="bcp-row-copy">{row.checked}</p>
            </div>
            <Pill label={row.state} on={row.state === "Watching"} />
            <button type="button" className="bcp-text-btn" onClick={() => stop()}>
              Remove
            </button>
          </div>
        ))}
      </div>
      <Notice text={notice} />
    </>
  );
}

function McpTab() {
  const [notice, stop] = useNotice();
  const [how, setHow] = useState<"provider" | "token">("token");
  return (
    <>
      <PartHead title="MCP connections" copy="Connections to outside tools and data servers that Base can read from." />
      <div className="bcp-list">
        {MCP_ROWS.map((row) => (
          <div key={row.host} className="bcp-mcp-row">
            <div>
              <p className="bcp-row-title">{row.name}</p>
              <p className="bcp-env">{row.host}</p>
            </div>
            <p className="bcp-row-copy">{row.gives}</p>
            <Pill label={row.state} on={row.state === "Connected"} />
            <div>
              <p className="bcp-env">Last used</p>
              <p className="bcp-row-copy">{row.used}</p>
            </div>
            <button type="button" className="bcp-text-btn" onClick={() => stop()}>
              Disconnect
            </button>
          </div>
        ))}
      </div>
      <form className="bcp-box bcp-mcp-form" onSubmit={stop}>
        <p className="bcp-row-title">Add connection</p>
        <div className="bcp-mcp-grid">
          <label className="bcp-field">
            <span>Name</span>
            <input className="bcp-input" type="text" placeholder="e.g. Customer records" autoComplete="off" />
          </label>
          <label className="bcp-field">
            <span>Server URL</span>
            <input className="bcp-input" type="url" placeholder="https://…" autoComplete="off" />
          </label>
          <div className="bcp-field">
            <span>How it signs in</span>
            <div className="bcp-toggle" role="group" aria-label="How it signs in">
              <button type="button" aria-pressed={how === "provider"} onClick={() => setHow("provider")}>
                Sign in with the provider
              </button>
              <button type="button" aria-pressed={how === "token"} onClick={() => setHow("token")}>
                Token
              </button>
            </div>
          </div>
          <div className="bcp-token-row">
            <label className="bcp-field bcp-grow">
              <span>Token</span>
              <input
                className="bcp-input"
                type="password"
                placeholder="Paste token (hidden once saved)"
                autoComplete="off"
                spellCheck={false}
                disabled={how !== "token"}
              />
            </label>
            <div className="bcp-actions">
              <button type="submit" className="bcp-primary">
                Add connection
              </button>
            </div>
          </div>
        </div>
        <p className="bcp-fine">A saved token shows only as •••• saved 17 Oct, with Replace or Remove. It is never shown again.</p>
      </form>
      <Notice text={notice} />
    </>
  );
}

function TabBody({ id }: { id: PluginsTab }) {
  if (id === "keys") return <KeysTab />;
  if (id === "files") return <FilesTab />;
  if (id === "links") return <LinksTab />;
  return <McpTab />;
}

export function PluginsDialog({
  tab,
  onTab,
  onClose,
}: {
  tab: PluginsTab;
  onTab: (tab: PluginsTab) => void;
  onClose: () => void;
}) {
  const close = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    close.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="bcp-modal">
      <button type="button" className="bcp-modal-dim" aria-label="Close Plugins" tabIndex={-1} onClick={onClose} />
      <div className="bcp-popup" role="dialog" aria-modal="true" aria-labelledby="bcp-plugins-title">
        <span className="bcp-handle" aria-hidden="true" />
        <div className="bcp-popup-head">
          <div>
            <h2 id="bcp-plugins-title">Plugins</h2>
            <p>What Base connects to. Add a key, upload a list, paste a link, or connect an MCP server.</p>
          </div>
          <button ref={close} type="button" className="bcp-text-btn" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="bcp-tabs" role="tablist" aria-label="Plugins">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              id={`bcp-tab-${item.id}`}
              aria-selected={tab === item.id}
              aria-controls={`bcp-panel-${item.id}`}
              className={tab === item.id ? "bcp-tab active" : "bcp-tab"}
              onClick={() => onTab(item.id)}
            >
              {item.label}
            </button>
          ))}
        </div>
        {TABS.map((item) => (
          <section
            key={item.id}
            className={tab === item.id ? "bcp-group open" : "bcp-group"}
            id={`bcp-panel-${item.id}`}
            role="tabpanel"
            aria-labelledby={`bcp-tab-${item.id}`}
          >
            <button type="button" className="bcp-group-head" aria-expanded={tab === item.id} onClick={() => onTab(item.id)}>
              <span>{item.label}</span>
              <span aria-hidden="true">{tab === item.id ? "−" : "+"}</span>
            </button>
            {tab === item.id ? (
              <div className="bcp-group-body">
                <TabBody id={item.id} />
              </div>
            ) : null}
          </section>
        ))}
      </div>
    </div>
  );
}
