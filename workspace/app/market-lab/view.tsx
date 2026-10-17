"use client";

import { useEffect, useId, useRef, useState, type DragEvent, type FormEvent } from "react";
import { useFormStatus } from "react-dom";
import { headerLinks } from "../product-nav";
import { MARKET_LAB_LOGO_SRC } from "./catalog";
import type { LinkGroupView, OnCard, PageModel } from "./model";
import {
  PLUGIN_TABS,
  POPUP_TITLE,
  REFERENCE_LABEL,
  STUB_FILE,
  STUB_KEY,
  STUB_LINK,
  STUB_MCP,
  type AnswerSource,
  type PluginTab,
  clientPluginState,
  searchMarketLab,
} from "./plugins";

const SECTIONS = [
  { id: "overview", label: "Overview" },
  { id: "on", label: "On" },
  { id: "off", label: "Off (needs a key)" },
  { id: "linked", label: "Linked pages" },
] as const;

const KEYED_ON = new Set(["eia_diesel", "fred", "census_population", "census_trade", "noaa_climate", "legiscan"]);

type Turn = { role: "user" | "assistant"; content: string; sources?: AnswerSource[]; error?: boolean };

function RefreshButton() {
  const { pending } = useFormStatus();
  return (
    <button className="ml-refresh" type="submit" disabled={pending}>
      {pending ? "Refreshing…" : "Refresh feeds"}
    </button>
  );
}

function SearchIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
      <circle cx="7.5" cy="7.5" r="4.75" fill="none" stroke="#6b7590" strokeWidth="1.5" />
      <path d="M11.2 11.2 L15.5 15.5" fill="none" stroke="#6b7590" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function scrollToSection(id: string) {
  const root = document.querySelector<HTMLElement>("[data-scroll-root]");
  const target = document.getElementById(id);
  if (!root || !target) return;
  const top = target.getBoundingClientRect().top - root.getBoundingClientRect().top + root.scrollTop;
  root.scrollTo({ top, behavior: "smooth" });
}

function linkLabel(href: string): string {
  try {
    const url = new URL(href);
    return `${url.host}${url.pathname === "/" ? "" : url.pathname}`;
  } catch {
    return href;
  }
}

function OnCardView({ card }: { card: OnCard }) {
  const bare = !card.headline && card.lines.length === 0 && card.notices.length === 0 && !card.problem;
  const meta = [card.cadence, card.asOf ? `Updated ${card.asOf}` : null, card.sourceLabel].filter(Boolean).join(" · ");
  return (
    <article className="ml-card">
      <div className="ml-card-top">
        <h3>{card.title}</h3>
        <span className="ml-chip">
          <span className="ml-dot" aria-hidden="true" />
          On
        </span>
      </div>
      <p className="ml-summary">{card.summary}</p>
      {card.headline ? <p className="ml-value">{card.headline}</p> : null}
      {card.detail ? <p className="ml-detail">{card.detail}</p> : null}
      {card.lines.length ? (
        <ul className="ml-lines">
          {card.lines.map((line) => (
            <li key={`${line.label}-${line.value}`}>
              <span>{line.label}</span>
              <strong>{line.value}</strong>
            </li>
          ))}
        </ul>
      ) : null}
      {card.notices.length ? (
        <ul className="ml-notices">
          {card.notices.slice(0, 3).map((notice) => (
            <li key={notice.title}>{notice.title}</li>
          ))}
        </ul>
      ) : null}
      {bare ? <p className="ml-value ml-empty-value">No reading yet</p> : null}
      {card.problem ? <p className="ml-problem">{card.problem}</p> : null}
      <p className="ml-card-meta">{meta}</p>
    </article>
  );
}

function ChatBox() {
  const [draft, setDraft] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [sending, setSending] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text || sending) return;
    const next: Turn[] = [...turns, { role: "user", content: text }];
    setTurns(next);
    setDraft("");
    setSending(true);
    try {
      const res = await fetch("/api/market-lab/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ messages: next.map(({ role, content }) => ({ role, content })) }),
      });
      const data = (await res.json().catch(() => null)) as { content?: string; error?: string; sources?: AnswerSource[] } | null;
      if (!res.ok || !data?.content) {
        setTurns([...next, { role: "assistant", content: data?.error || "Market Lab could not answer.", error: true, sources: [] }]);
      } else {
        setTurns([...next, { role: "assistant", content: data.content, sources: data.sources ?? [] }]);
      }
    } catch {
      setTurns([...next, { role: "assistant", content: "Market Lab could not answer. Nothing was changed.", error: true, sources: [] }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="ml-chat" aria-label="Ask Market Lab">
      <h2>Ask Market Lab</h2>
      {turns.length ? (
        <div className="ml-thread">
          {turns.map((turn, index) =>
            turn.role === "user" ? (
              <div className="ml-bubble ml-you" key={`you-${index}`}>
                <p className="ml-who">You</p>
                <p className="ml-said">{turn.content}</p>
              </div>
            ) : (
              <div className="ml-bubble ml-answer" key={`lab-${index}`}>
                <p className="ml-who">Market Lab</p>
                <p className="ml-said">{turn.content}</p>
                {turn.sources && turn.sources.length ? (
                  <div className="ml-refs">
                    <p className="ml-refs-label">{REFERENCE_LABEL}</p>
                    {turn.sources.map((source) => (
                      <div className="ml-ref" key={`${source.name}-${source.href ?? ""}`}>
                        <span className="ml-ref-name">{source.name}</span>
                        {source.href ? (
                          <a className="ml-ref-link" href={source.href}>
                            {linkLabel(source.href)}
                          </a>
                        ) : (
                          <span />
                        )}
                        {source.date ? <span className="ml-ref-date">{source.date}</span> : null}
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            ),
          )}
        </div>
      ) : null}
      <form className="ml-composer" onSubmit={onSubmit}>
        <label className="ml-sr" htmlFor="ml-ask">
          Ask Market Lab
        </label>
        <input
          id="ml-ask"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Ask Market Lab about your market…"
          disabled={sending}
        />
        <button className="ml-send" type="submit" disabled={sending || !draft.trim()}>
          {sending ? "Sending…" : "Send"}
        </button>
      </form>
    </section>
  );
}

function PluginsDialog({
  open,
  tab,
  flags,
  onTab,
  onClose,
}: {
  open: boolean;
  tab: PluginTab;
  flags: ReturnType<typeof clientPluginState>;
  onTab: (tab: PluginTab) => void;
  onClose: () => void;
}) {
  const titleId = useId();
  const fileRef = useRef<HTMLInputElement>(null);
  const [note, setNote] = useState("");
  const [cadence, setCadence] = useState<"Daily" | "Weekly">("Daily");
  const [signIn, setSignIn] = useState<"provider" | "token">("token");

  useEffect(() => {
    if (!open) setNote("");
  }, [open]);

  if (!open) return null;

  function refuseKey(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const field = form.querySelector<HTMLInputElement>("input[type=password]");
    const value = field?.value.trim() ?? "";
    form.reset();
    setNote(value ? STUB_KEY : "Add a key first. Nothing was stored.");
  }

  function refuseFile() {
    const count = fileRef.current?.files?.length ?? 0;
    if (fileRef.current) fileRef.current.value = "";
    if (count > 0) setNote(STUB_FILE);
  }

  function refuseLink(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const url = form.querySelector<HTMLInputElement>("input[name=link]")?.value.trim() ?? "";
    form.reset();
    setCadence("Daily");
    setNote(url ? STUB_LINK : "Add a link first. Nothing was saved.");
  }

  function refuseConnection(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const name = form.querySelector<HTMLInputElement>("input[name=connection-name]")?.value.trim() ?? "";
    const url = form.querySelector<HTMLInputElement>("input[name=server]")?.value.trim() ?? "";
    form.reset();
    setNote(name && url ? STUB_MCP : "Add a name and a server URL first. Nothing was saved.");
  }

  return (
    <div className="ml-shade" onClick={onClose}>
      <div
        className="ml-plugins"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="ml-sheet-handle" aria-hidden="true" />
        <div className="ml-plugins-head">
          <div>
            <h2 id={titleId}>{POPUP_TITLE}</h2>
            <p>Everything Market Lab reads from. Add a key, upload a file, paste a link, or connect a tool.</p>
          </div>
          <button className="ml-text" type="button" onClick={onClose}>
            Close
          </button>
        </div>
        <div className="ml-tabs" role="tablist">
          {PLUGIN_TABS.map((name) => (
            <button
              key={name}
              className={name === tab ? "ml-tab active" : "ml-tab"}
              type="button"
              role="tab"
              aria-selected={name === tab}
              onClick={() => {
                setNote("");
                onTab(name);
              }}
            >
              {name}
            </button>
          ))}
        </div>
        {note ? <p className="ml-stub">{note}</p> : null}
        {tab === "API keys" ? (
          <div className="ml-tab-body">
            <p className="ml-lead">Keys for public feeds and your suppliers. A key is write-only: once saved it is never shown again.</p>
            <div className="ml-plist">
              {flags.keys.map((row) => (
                <form className="ml-prow" key={row.name} onSubmit={refuseKey}>
                  <div className="ml-prow-top">
                    <h3>{row.title}</h3>
                    <span className={row.connected ? "ml-chip" : "ml-chip ml-chip-off"}>
                      <span className="ml-dot" aria-hidden="true" />
                      {row.connected ? "Connected" : "Not set"}
                    </span>
                  </div>
                  <p>{row.summary}</p>
                  {row.connected ? (
                    <p className="ml-secret">•••• set in the environment</p>
                  ) : (
                    <div className="ml-keyline">
                      <label className="ml-sr" htmlFor={`key-${row.name}`}>
                        {row.title} key
                      </label>
                      <input id={`key-${row.name}`} type="password" autoComplete="off" placeholder="Paste key" />
                      <button className="ml-outline" type="submit">
                        Save
                      </button>
                    </div>
                  )}
                </form>
              ))}
            </div>
            <form className="ml-supplier" onSubmit={refuseKey}>
              <h3>Add a supplier key</h3>
              <p>For a supplier that gives you an API key.</p>
              <div className="ml-keyline">
                <label>
                  Supplier name
                  <input name="supplier" type="text" autoComplete="off" placeholder="Supplier name" />
                </label>
                <label>
                  Key
                  <input type="password" autoComplete="off" placeholder="Paste key (hidden once saved)" />
                </label>
                <button className="ml-primary" type="submit">
                  Save key
                </button>
              </div>
            </form>
            <p className="ml-fine">Keys are stored on the server, never in the app code.</p>
          </div>
        ) : null}
        {tab === "Files" ? (
          <div className="ml-tab-body">
            <h3 className="ml-subhead">Files</h3>
            <p className="ml-lead">Upload price lists, inventory, reports or rules. CSV files can be matched to the right columns.</p>
            <div
              className="ml-drop"
              onDragOver={(event: DragEvent) => event.preventDefault()}
              onDrop={(event: DragEvent) => {
                event.preventDefault();
                if (event.dataTransfer.files.length > 0) setNote(STUB_FILE);
              }}
            >
              <p className="ml-drop-title">Drag CSV, XLSX or PDF files here</p>
              <p className="ml-or">or</p>
              <button className="ml-primary" type="button" onClick={() => fileRef.current?.click()}>
                Choose files
              </button>
              <input
                ref={fileRef}
                className="ml-sr"
                type="file"
                accept=".csv,.xlsx,.pdf,text/csv,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                multiple
                onChange={refuseFile}
              />
            </div>
            <p className="ml-fine">No files stored.</p>
          </div>
        ) : null}
        {tab === "Source links" ? (
          <div className="ml-tab-body">
            <h3 className="ml-subhead">Source links</h3>
            <p className="ml-lead">Pages Market Lab checks for changes, such as rule pages, season dates or port stats.</p>
            <form className="ml-linkform" onSubmit={refuseLink}>
              <label>
                Link
                <input name="link" type="url" placeholder="Paste a link, e.g. https://…" />
              </label>
              <label>
                Label (optional)
                <input name="label" type="text" placeholder="e.g. Texas seasons" />
              </label>
              <div>
                <p className="ml-field-label">How often to check</p>
                <div className="ml-choice">
                  <button className={cadence === "Daily" ? "active" : ""} type="button" onClick={() => setCadence("Daily")}>
                    Daily
                  </button>
                  <button className={cadence === "Weekly" ? "active" : ""} type="button" onClick={() => setCadence("Weekly")}>
                    Weekly
                  </button>
                </div>
              </div>
              <button className="ml-primary" type="submit">
                Add link
              </button>
            </form>
            <p className="ml-fine">No links stored.</p>
          </div>
        ) : null}
        {tab === "MCP connections" ? (
          <div className="ml-tab-body">
            <h3 className="ml-subhead">MCP connections</h3>
            <p className="ml-lead">Connections to outside tools and data servers that Market Lab can read from.</p>
            <p className="ml-fine">No connections stored.</p>
            <form className="ml-mcp" onSubmit={refuseConnection}>
              <h3>Add connection</h3>
              <div className="ml-mcp-row">
                <label>
                  Name
                  <input name="connection-name" type="text" placeholder="e.g. Supplier catalogue" />
                </label>
                <label>
                  Server URL
                  <input name="server" type="url" placeholder="https://…" />
                </label>
              </div>
              <div className="ml-mcp-row">
                <div>
                  <p className="ml-field-label">How it signs in</p>
                  <div className="ml-choice">
                    <button className={signIn === "provider" ? "active" : ""} type="button" onClick={() => setSignIn("provider")}>
                      Sign in with the provider
                    </button>
                    <button className={signIn === "token" ? "active" : ""} type="button" onClick={() => setSignIn("token")}>
                      Token
                    </button>
                  </div>
                </div>
                {signIn === "token" ? (
                  <label>
                    Token
                    <input type="password" autoComplete="off" placeholder="Paste token (hidden once saved)" />
                  </label>
                ) : null}
                <button className="ml-primary" type="submit">
                  Add connection
                </button>
              </div>
              <p className="ml-fine">A saved token is shown only as dots, and is never shown again.</p>
            </form>
          </div>
        ) : null}
      </div>
    </div>
  );
}

export function MarketLabView({
  model,
  refresh,
  founder,
  workspaceName,
}: {
  model: PageModel;
  refresh: () => Promise<void>;
  founder: boolean;
  workspaceName: string | null;
}) {
  const [menu, setMenu] = useState(false);
  const [active, setActive] = useState("overview");
  const [pluginsOpen, setPluginsOpen] = useState(false);
  const [tab, setTab] = useState<PluginTab>("API keys");
  const [query, setQuery] = useState("");
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  const searchId = useId();
  const pluginState = clientPluginState({
    CENSUS_API_KEY: censusOn(model),
    LEGISCAN_API_KEY: keyedOn(model, "legiscan"),
    EIA_API_KEY: keyedOn(model, "eia_diesel"),
    NOAA_TOKEN: keyedOn(model, "noaa_climate"),
    FRED_API_KEY: keyedOn(model, "fred"),
  });

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setMenu(false);
      setPluginsOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    const root = document.querySelector<HTMLElement>("[data-scroll-root]");
    if (!root) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible?.target.id) setActive(visible.target.id);
      },
      { root, rootMargin: "-15% 0px -55% 0px", threshold: [0.15, 0.4] },
    );
    for (const section of SECTIONS) {
      const el = document.getElementById(section.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, []);

  const scope = searchMarketLab(model, query);
  const onCards = [...model.featured, ...model.cards].filter((card) => scope.onIds.includes(card.id));
  const offRows = model.off.filter((row) => scope.offIds.includes(row.id));
  const groups = model.groups
    .map((group) => ({ ...group, pages: group.pages.filter((page) => scope.linkIds.includes(page.id)) }))
    .filter((group) => group.pages.length > 0);
  const searching = query.trim().length > 0;
  const noHits = searching && onCards.length === 0 && offRows.length === 0 && groups.length === 0;
  const anyKeyedOn = [...model.featured, ...model.cards].some((card) => KEYED_ON.has(card.id));
  const links = headerLinks(founder).map((link) => (link.href === "/skala" ? { ...link, label: "Skills" } : link));

  function openSection(id: string) {
    setMenu(false);
    setPluginsOpen(false);
    setActive(id);
    scrollToSection(id);
  }

  return (
    <div className="ml">
      <header className="ml-top">
        <img src="/brand/tervory-logo-reversed.png" alt="Tervory" width={186} height={34} />
        <button className="ml-menu" type="button" onClick={() => setMenu(true)}>
          Menu
        </button>
      </header>
      <button className="ml-dim" type="button" hidden={!menu} aria-label="Close menu" onClick={() => setMenu(false)} />
      <aside className={menu ? "ml-panel open" : "ml-panel"}>
        <div className="ml-brand">
          <img className="ml-logo" src="/brand/tervory-logo-reversed.png" alt="Tervory" width={186} height={34} />
          <div className="ml-slot">
            {MARKET_LAB_LOGO_SRC ? (
              <img src={MARKET_LAB_LOGO_SRC} alt="Market Lab" />
            ) : (
              <span>Market Lab logo, added later</span>
            )}
          </div>
        </div>
        <button className="ml-close" type="button" onClick={() => setMenu(false)}>
          Close
        </button>
        <nav className="ml-nav" aria-label="Workspace">
          <p className="ml-kicker">Workspace</p>
          {links.map((link) => (
            <a key={link.href} className="ml-link" href={link.href} onClick={() => setMenu(false)}>
              {link.label}
            </a>
          ))}
        </nav>
        <div className="ml-rule" />
        <nav className="ml-nav" aria-label="Market Lab">
          <p className="ml-kicker">Market Lab</p>
          {SECTIONS.map((section) => (
            <button
              key={section.id}
              className={!pluginsOpen && active === section.id ? "ml-navbtn active" : "ml-navbtn"}
              type="button"
              onClick={() => openSection(section.id)}
            >
              {section.label}
            </button>
          ))}
          <button
            className={pluginsOpen ? "ml-navbtn active" : "ml-navbtn"}
            type="button"
            onClick={() => {
              setMenu(false);
              setPluginsOpen(true);
            }}
          >
            Plugins
          </button>
        </nav>
        <div className="ml-spacer" />
        {workspaceName ? (
          <>
            <div className="ml-rule" />
            <p className="ml-org">{workspaceName}</p>
          </>
        ) : null}
      </aside>
      <div className="ml-main" data-scroll-root>
        <div className="ml-body">
          <header className="ml-header" id="overview">
            <div>
              <h1>Market Lab</h1>
              <p className="ml-intro">Public data feeds that show how your market is moving. Search what Market Lab has, or ask it a question.</p>
            </div>
            <div className="ml-search">
              <SearchIcon />
              <label className="ml-sr" htmlFor={searchId}>
                Search Market Lab
              </label>
              <input
                id={searchId}
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search feeds, signals, files, links, predictions"
              />
            </div>
          </header>
          <ChatBox />
          <div className="ml-counts">
            <article>
              <p className="ml-count">{model.onCount}</p>
              <p>On</p>
            </article>
            <article>
              <p className="ml-count">{model.offCount}</p>
              <p>Off</p>
            </article>
            <article>
              <p className="ml-count">{model.linkedCount}</p>
              <p>Linked pages</p>
            </article>
          </div>
          {model.loadError ? (
            <section className="ml-note">
              <h2>Feeds could not load</h2>
              <p>We could not read the feed status. Nothing has changed. Try Refresh feeds, or check back in a few minutes.</p>
            </section>
          ) : null}
          {noHits ? <p className="ml-none">Nothing in Market Lab matches that.</p> : null}
          <section id="on" className="ml-section">
            <h2>On</h2>
            <p className="ml-lead">
              {anyKeyedOn
                ? "These feeds are on. Each shows its latest value."
                : "These feeds need no key. They read public data and show their latest value."}
            </p>
            {model.onEmpty && !searching ? (
              <div className="ml-note">
                <h3>No feed data yet</h3>
                <p>The feeds have not run yet. Their data shows here after the first refresh.</p>
              </div>
            ) : onCards.length ? (
              <div className="ml-grid">
                {onCards.map((card) => (
                  <OnCardView key={card.id} card={card} />
                ))}
              </div>
            ) : null}
          </section>
          <section id="off" className="ml-section">
            <h2>Off (needs a key)</h2>
            <p className="ml-lead">These feeds stay off until a key is added in Plugins. They are not called.</p>
            {offRows.length ? (
              <ul className="ml-off">
                {offRows.map((row) => (
                  <li key={row.id}>
                    <span className="ml-off-name">{row.title}</span>
                    <span>Off. Needs a key.</span>
                    <span className="ml-keychip">{row.keyName}</span>
                    <span className="ml-off-quiet">Not called</span>
                  </li>
                ))}
              </ul>
            ) : searching ? null : (
              <p className="ml-lead">Every keyed feed is on.</p>
            )}
          </section>
          <section id="linked" className="ml-section">
            <h2>Linked pages</h2>
            <p className="ml-lead">Other pages that use these feeds.</p>
            <div className="ml-links">
              {groups.map((group) => (
                <GroupCard
                  key={group.id}
                  group={group}
                  open={Boolean(openGroups[group.id])}
                  onToggle={() => setOpenGroups((current) => ({ ...current, [group.id]: !current[group.id] }))}
                />
              ))}
            </div>
          </section>
          <footer className="ml-foot">
            <p>
              Public data only. FRED data is read live and never stored.{" "}
              {model.refreshedLabel === "Not refreshed yet" ? "Not refreshed yet." : `Last refreshed ${model.refreshedLabel}.`}
            </p>
            <form action={refresh}>
              <RefreshButton />
            </form>
          </footer>
        </div>
      </div>
      <PluginsDialog open={pluginsOpen} tab={tab} flags={pluginState} onTab={setTab} onClose={() => setPluginsOpen(false)} />
    </div>
  );
}

function censusOn(model: PageModel): boolean {
  return keyedOn(model, "census_population") || keyedOn(model, "census_trade");
}

function keyedOn(model: PageModel, id: string): boolean {
  return [...model.featured, ...model.cards].some((card) => card.id === id);
}

function GroupCard({ group, open, onToggle }: { group: LinkGroupView; open: boolean; onToggle: () => void }) {
  return (
    <article className="ml-linkcard">
      <h3>{group.title}</h3>
      <p>{group.lead}</p>
      <button className="ml-expand" type="button" onClick={onToggle} aria-expanded={open}>
        Open page →
      </button>
      {open ? (
        <ul>
          {group.pages.map((page) => (
            <li key={page.id}>
              <a href={page.href}>{page.label}</a>
              <span>{page.note}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </article>
  );
}
