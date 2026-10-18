"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { DeadlinesPanel } from "./deadlines-panel";
import { AREAS, COURTS, DEADLINE_ROWS, MATTER_ROWS, REVIEW_ROWS, SEARCH_KINDS, hitsFor, type SearchKind } from "./frame";
import { MOOT_LABEL } from "./moot";
import { MootCourt } from "./moot-court";
import { PluginsDialog } from "./plugins-dialog";
import { PLUGIN_TABS, SEARCH_PLACEHOLDER, type PluginPanel, type PluginTab } from "./plugins";

const TOP_LINKS = [
  { href: "/ledger", label: "Dashboard" },
  { href: "/tasks", label: "Projects" },
] as const;

const PAGE_LINKS = [
  { href: "/matters", label: "Matters" },
  { href: "/review", label: "Review" },
] as const;

const PLACE_LINKS = ["Draft", "Court bundles"] as const;
const PLACE_TAIL = ["Library"] as const;

const BOTTOM_LINKS = [
  { href: "/onboarding", label: "Settings" },
  { href: "/", label: "Support" },
] as const;

function Bars({ widths }: { widths: string[] }) {
  return (
    <span className="zn-bars" aria-hidden="true">
      {widths.map((width, index) => (
        <span key={`${width}-${index}`} className="zn-bar" style={{ width }} />
      ))}
    </span>
  );
}

function Cite({ children }: { children: string }) {
  return <span className="zn-cite">↗ {children}</span>;
}

function Issue({ n }: { n: 1 | 2 }) {
  return (
    <article className="zn-issue">
      <h4>Issue {n}</h4>
      <div className="zn-ira">
        <span>Rule</span>
        <div>
          <Bars widths={["100%", "63%"]} />
          <Cite>Act name No __ of ____, s __</Cite>
        </div>
      </div>
      <div className="zn-ira">
        <span>Application</span>
        <div>
          <Bars widths={["100%", "63%"]} />
          <Cite>[____] ZA____ __ at para __</Cite>
        </div>
      </div>
      <div className="zn-ira">
        <span>Conclusion</span>
        <Bars widths={["100%"]} />
      </div>
    </article>
  );
}

function RiskRow() {
  return (
    <div className="zn-risk-row">
      <Bars widths={["76%"]} />
      <span className="zn-chip">Level</span>
      <span className="zn-chip">Level</span>
      <Bars widths={["79%"]} />
    </div>
  );
}

export function ZenasView({ plugins, workspaceName }: { plugins: PluginPanel; workspaceName: string | null }) {
  const accountName = workspaceName?.trim() || "Account name";
  const initial = accountName.slice(0, 1).toUpperCase();
  const searchRef = useRef<HTMLInputElement>(null);
  const askRef = useRef<HTMLTextAreaElement>(null);
  const listId = useId();
  const [menu, setMenu] = useState(false);
  const [pluginsOpen, setPluginsOpen] = useState(false);
  const [tab, setTab] = useState<PluginTab>(PLUGIN_TABS[0]);
  const [areasOpen, setAreasOpen] = useState(false);
  const [areasPos, setAreasPos] = useState({ top: 8, left: 248 });
  const [areaPick, setAreaPick] = useState("All areas (civil)");
  const areasRef = useRef<HTMLButtonElement>(null);
  const areasMenuRef = useRef<HTMLDivElement>(null);
  const areasMenuId = useId();
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<SearchKind>("All");
  const [cursor, setCursor] = useState(0);
  const [civil, setCivil] = useState(false);
  const [southAfrica, setSouthAfrica] = useState(false);
  const [area, setArea] = useState("Any");
  const [court, setCourt] = useState("Any");
  const [matter, setMatter] = useState("None");
  const [reasoning, setReasoning] = useState<"Auto" | "High">("Auto");
  const [asked, setAsked] = useState<string | null>(null);
  const [messages, setMessages] = useState(0);
  const [attached, setAttached] = useState<string | null>(null);
  const [actionNote, setActionNote] = useState("");
  const [section, setSection] = useState<"chats" | "moot" | "deadlines">("chats");
  const bodyRef = useRef<HTMLDivElement>(null);

  const hits = hitsFor(kind, query);
  const showFrame = query.trim().length === 0;

  useEffect(() => {
    function onKey(event: globalThis.KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen(true);
        searchRef.current?.focus();
      }
      if (event.key === "Escape") {
        setSearchOpen(false);
        setPluginsOpen(false);
        setMenu(false);
        setAreasOpen(false);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!areasOpen) return;
    function onPointer(event: PointerEvent) {
      const target = event.target as Node;
      if (areasRef.current?.contains(target) || areasMenuRef.current?.contains(target)) return;
      setAreasOpen(false);
    }
    window.addEventListener("pointerdown", onPointer);
    return () => window.removeEventListener("pointerdown", onPointer);
  }, [areasOpen]);

  function openPlugins() {
    setMenu(false);
    setSearchOpen(false);
    setAreasOpen(false);
    setPluginsOpen(true);
  }

  function showChats() {
    setSection("chats");
    setPluginsOpen(false);
    setAreasOpen(false);
    setMenu(false);
    bodyRef.current?.scrollTo(0, 0);
  }

  function showMoot() {
    setSection("moot");
    setPluginsOpen(false);
    setSearchOpen(false);
    setAreasOpen(false);
    setMenu(false);
    bodyRef.current?.scrollTo(0, 0);
  }

  function showDeadlines() {
    setSection("deadlines");
    setPluginsOpen(false);
    setSearchOpen(false);
    setAreasOpen(false);
    setMenu(false);
    bodyRef.current?.scrollTo(0, 0);
  }

  function toggleAreas() {
    if (areasOpen) {
      setAreasOpen(false);
      return;
    }
    const rect = areasRef.current?.getBoundingClientRect();
    if (rect) {
      const menuWidth = 260;
      const left = rect.right + 8 + menuWidth > window.innerWidth
        ? Math.max(8, window.innerWidth - menuWidth - 8)
        : rect.right + 8;
      setAreasPos({ top: Math.max(8, rect.top), left });
    }
    setAreasOpen(true);
  }

  function closePlugins() {
    setPluginsOpen(false);
  }

  function onSearchKey(event: ReactKeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setSearchOpen(true);
      setCursor((value) => Math.min(value + 1, Math.max(hits.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setCursor((value) => Math.max(value - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      setKind("All");
      setSearchOpen(true);
    }
  }

  function onAsk(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = askRef.current?.value.trim() ?? "";
    if (!text) {
      setActionNote("Type a question first. Nothing was sent.");
      return;
    }
    setAsked(text);
    setMessages((count) => count + 1);
    setActionNote("");
    if (askRef.current) askRef.current.value = "";
  }

  return (
    <div className="zn">
      <button className="zn-menu" type="button" onClick={() => setMenu(true)}>
        Menu
      </button>
      <button className="zn-dim" type="button" hidden={!menu} aria-label="Close menu" onClick={() => setMenu(false)} />
      <aside className={menu ? "zn-panel open" : "zn-panel"}>
        <div className="zn-panel-main">
        <div className="zn-brand">
          <img className="zn-zenas-logo" src="/brand/zenas-on-dark.png" alt="Zenas" width={150} height={53} />
        </div>
        <button className="zn-close" type="button" onClick={() => setMenu(false)}>
          Close
        </button>
        <nav className="zn-nav" aria-label="Account">
          <p className="zn-account">
            <span className="zn-avatar" aria-hidden="true">{initial}</span>
            {accountName}
          </p>
          {TOP_LINKS.map((link) => (
            <Link key={link.label} href={link.href} onClick={() => setMenu(false)}>
              {link.label}
            </Link>
          ))}
          <button className={!pluginsOpen && section === "chats" ? "active" : ""} type="button" onClick={showChats}>
            Chats
          </button>
        </nav>
        <div className="zn-rule" />
        <nav className="zn-nav" aria-label="Zenas">
          <p className="zn-kicker">ZENAS · CIVIL · SOUTH AFRICA</p>
          {PAGE_LINKS.map((link) => (
            <Link key={link.label} href={link.href} onClick={() => setMenu(false)}>
              {link.label}
            </Link>
          ))}
          <button
            className={!pluginsOpen && section === "moot" ? "active" : ""}
            type="button"
            aria-current={!pluginsOpen && section === "moot" ? "page" : undefined}
            onClick={showMoot}
          >
            {MOOT_LABEL}
          </button>
          <button className={pluginsOpen ? "active" : ""} type="button" onClick={openPlugins}>
            Plugins
          </button>
          {PLACE_LINKS.map((label) => (
            <button key={label} type="button" onClick={() => setMenu(false)}>
              {label}
            </button>
          ))}
          <button
            className={!pluginsOpen && section === "deadlines" ? "active" : ""}
            type="button"
            aria-current={!pluginsOpen && section === "deadlines" ? "page" : undefined}
            onClick={showDeadlines}
          >
            Deadlines
          </button>
          {PLACE_TAIL.map((label) => (
            <button key={label} type="button" onClick={() => setMenu(false)}>
              {label}
            </button>
          ))}
        </nav>
        <button
          ref={areasRef}
          className={areasOpen ? "zn-areas-row open" : "zn-areas-row"}
          type="button"
          aria-expanded={areasOpen}
          aria-controls={areasMenuId}
          onClick={toggleAreas}
        >
          <span>Areas of law</span>
          <span>{areaPick === AREAS[0] ? AREAS.length : areaPick}</span>
        </button>
        <section className="zn-side" aria-label="Diary">
          <div className="zn-side-head">
            <p className="zn-kicker">DIARY</p>
            <button type="button">View all</button>
          </div>
          <div className="zn-skel-row" aria-hidden="true">
            <span />
            <span><i /><i /></span>
          </div>
        </section>
        <section className="zn-side" aria-label="Upcoming court dates">
          <div className="zn-side-head">
            <p className="zn-kicker">UPCOMING COURT DATES</p>
            <button type="button">View all</button>
          </div>
          <div className="zn-skel-row" aria-hidden="true">
            <span />
            <span><i /><i /></span>
          </div>
          <div className="zn-skel-row" aria-hidden="true">
            <span />
            <span><i /><i /></span>
          </div>
        </section>
        <div className="zn-spacer" />
        </div>
        <div className="zn-panel-foot">
        <div className="zn-rule" />
        <img className="zn-foot-logo" src="/brand/tervory-logo-reversed.png" alt="Tervory" width={186} height={34} />
        <nav className="zn-nav" aria-label="Account settings">
          {BOTTOM_LINKS.map((link) => (
            <Link key={link.label} href={link.href} onClick={() => setMenu(false)}>
              {link.label}
            </Link>
          ))}
        </nav>
        </div>
      </aside>
      <div ref={bodyRef} className={pluginsOpen ? "zn-body dimmed" : "zn-body"} data-scroll-root>
        {section === "moot" ? <MootCourt /> : null}
        {section === "deadlines" ? <DeadlinesPanel /> : null}
        {section === "chats" ? (
        <>
        <header className="zn-head">
          <div>
            <h1>Zenas</h1>
            <p>Civil law, South Africa. Search your own records, or ask Zenas a legal question.</p>
          </div>
          <div className="zn-search">
            <label className="zn-sr" htmlFor="zenas-search">Search</label>
            <svg className="zn-search-icon" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
              <circle cx="7" cy="7" r="4.25" fill="none" stroke="#6b7590" strokeWidth="1.4" />
              <path d="M10.2 10.2 L14 14" fill="none" stroke="#6b7590" strokeWidth="1.4" strokeLinecap="round" />
            </svg>
            <input
              id="zenas-search"
              ref={searchRef}
              value={query}
              placeholder={SEARCH_PLACEHOLDER}
              role="combobox"
              aria-expanded={searchOpen}
              aria-controls={listId}
              aria-autocomplete="list"
              onChange={(event) => {
                setQuery(event.target.value);
                setSearchOpen(true);
                setCursor(0);
              }}
              onFocus={() => setSearchOpen(true)}
              onKeyDown={onSearchKey}
            />
            <button className="zn-kbd" type="button" onClick={() => { setSearchOpen(true); searchRef.current?.focus(); }}>
              ⌘K
            </button>
            {searchOpen ? (
              <div className="zn-results" id={listId} role="listbox" aria-label="Search results">
                <div className="zn-results-head">
                  <strong>Results in your records · {showFrame ? "__" : hits.length}</strong>
                  <button type="button" onClick={() => setSearchOpen(false)}>Esc to close</button>
                </div>
                <div className="zn-result-filters">
                  {SEARCH_KINDS.map((name) => (
                    <button key={name} className={kind === name ? "zn-chip zn-chip-fill" : "zn-chip"} type="button" onClick={() => { setKind(name); setCursor(0); }}>
                      {name}
                    </button>
                  ))}
                </div>
                {SEARCH_KINDS.filter((name) => name !== "All").map((group) => {
                  const rows = hits.filter((hit) => hit.kind === group);
                  if (!rows.length) return null;
                  return (
                    <section key={group}>
                      <h2>{group.toUpperCase()}</h2>
                      {rows.map((hit, index) => {
                        const flat = hits.indexOf(hit);
                        return (
                          <div className={flat === cursor ? "zn-hit on" : "zn-hit"} key={`${hit.kind}-${index}`} role="option" aria-selected={flat === cursor}>
                            <span className="zn-hit-mark" aria-hidden="true" />
                            <span>
                              <strong>{hit.title}</strong>
                              <em>{hit.meta}</em>
                              <i />
                            </span>
                            {hit.status ? <span className="zn-chip">{hit.status}</span> : null}
                          </div>
                        );
                      })}
                    </section>
                  );
                })}
                {hits.length === 0 ? <p className="zn-empty">No records match that search.</p> : null}
                <p className="zn-results-foot">
                  Enter to see all {showFrame ? "__" : hits.length} results · ↑↓ to move · Searches matters, drafts, documents, citations and review in Zenas only.
                </p>
              </div>
            ) : null}
          </div>
        </header>
        <div className="zn-filters">
          <span>Optional</span>
          <button className={civil ? "zn-chip zn-chip-fill" : "zn-chip"} type="button" onClick={() => setCivil((value) => !value)}>Civil only</button>
          <button className={southAfrica ? "zn-chip zn-chip-fill" : "zn-chip"} type="button" onClick={() => setSouthAfrica((value) => !value)}>South Africa</button>
          <label className="zn-select">
            <span className="zn-sr">Area</span>
            <select value={area} onChange={(event) => setArea(event.target.value)} aria-label="Area">
              <option value="Any">Area: Any</option>
              {AREAS.map((name) => (
                <option key={name} value={name}>Area: {name}</option>
              ))}
            </select>
          </label>
          <label className="zn-select">
            <span className="zn-sr">Court</span>
            <select value={court} onChange={(event) => setCourt(event.target.value)} aria-label="Court">
              {COURTS.map((name) => (
                <option key={name} value={name}>{name === "Any" ? "Court: Any" : `Court: ${name}`}</option>
              ))}
            </select>
          </label>
          <label className="zn-select">
            <span className="zn-sr">Matter</span>
            <select value={matter} onChange={(event) => setMatter(event.target.value)} aria-label="Matter">
              <option value="None">Matter: None</option>
            </select>
          </label>
        </div>
        <section className="zn-ask" aria-label="Ask Zenas">
          <div className="zn-ask-head">
            <h2>Ask Zenas</h2>
            <p>Thread · {messages === 0 ? "__" : messages} {messages === 1 ? "message" : "messages"}</p>
          </div>
          <div className="zn-thread">
            <article className="zn-you">
              <h3>You</h3>
              {asked ? <p>{asked}</p> : <Bars widths={["100%", "63%"]} />}
            </article>
            <article className="zn-answer" aria-label="Answer">
              <header>
                <span className="zn-mark" aria-hidden="true">Z</span>
                <strong>Zenas</strong>
                <span className="zn-chip">Reasoning: {reasoning}</span>
                <time>__ / __ / ____ __:__</time>
              </header>
              <section>
                <h3>Brief Summary</h3>
                <Bars widths={["100%", "96%", "63%"]} />
                <Cite>[____] ZA____ __ at para __</Cite>
              </section>
              <section>
                <h3>Factual Background</h3>
                <ol>
                  <li><Bars widths={["100%", "63%"]} /></li>
                  <li><Bars widths={["100%", "63%"]} /></li>
                  <li>
                    <Bars widths={["100%"]} />
                    <Cite>Annexure FA __</Cite>
                  </li>
                </ol>
              </section>
              <section>
                <h3>Legal Analysis</h3>
                <Issue n={1} />
                <Issue n={2} />
              </section>
              <section>
                <h3>Risk Analysis</h3>
                <div className="zn-risk" role="table" aria-label="Risk analysis">
                  <div className="zn-risk-head" role="row">
                    <span role="columnheader">Risk</span>
                    <span role="columnheader">Likelihood</span>
                    <span role="columnheader">Impact</span>
                    <span role="columnheader">Mitigation</span>
                  </div>
                  <RiskRow />
                  <RiskRow />
                  <RiskRow />
                </div>
              </section>
              <section>
                <h3>Citations</h3>
                <ul className="zn-citations">
                  <li><span>[1]</span><Cite>[____] ZA____ __ at para __</Cite><span className="zn-verified">✓ Verified against stored paragraph</span></li>
                  <li><span>[2]</span><Cite>Case name v Case name ____ (_) SA ___ (_)</Cite><span className="zn-verified">✓ Verified against stored paragraph</span></li>
                  <li><span>[3]</span><Cite>Act name No __ of ____, s __</Cite><span className="zn-verified">✓ Verified against stored paragraph</span></li>
                  <li><span>[4]</span><Cite>Rule __(_)(_)</Cite><span className="zn-verified">✓ Verified against stored paragraph</span></li>
                </ul>
              </section>
              <section className="zn-sources" aria-label="Sources">
                <header>
                  <h3>Sources</h3>
                  <p>Information and references returned with this answer.</p>
                </header>
                <div className="zn-source-cols">
                  <article>
                    <h4>Statute</h4>
                    <p><strong>Act name No __ of ____</strong><span>Sections: s __, s __(_), s __(_)(_)</span></p>
                    <p><strong>Act name No __ of ____</strong><span>Sections: s __, s __(_), s __(_)(_)</span></p>
                    <p><strong>Act name No __ of ____</strong><span>Sections: s __, s __(_), s __(_)(_)</span></p>
                  </article>
                  <article>
                    <h4>Case Law</h4>
                    <p className="zn-weight">BINDING</p>
                    <p><strong>Case name v Case name</strong><span>[____] ZA____ __ · Court · para __</span></p>
                    <p><strong>Case name v Case name</strong><span>[____] ZA____ __ · Court · para __</span></p>
                    <p className="zn-weight">PERSUASIVE</p>
                    <p><strong>Case name v Case name</strong><span>[____] ZA____ __ · Court · para __</span></p>
                    <p><strong>Case name v Case name</strong><span>[____] ZA____ __ · Court · para __</span></p>
                  </article>
                  <article>
                    <h4>Full List of Authorities</h4>
                    <ol>
                      <li>Act name No __ of ____, s __</li>
                      <li>Act name No __ of ____, s __</li>
                      <li>Rule __(_)</li>
                      <li>Case name v Case name [____] ZA____ __</li>
                      <li>Case name v Case name ____ (_) SA ___ (_)</li>
                      <li>Case name v Case name [____] ZA____ __</li>
                      <li>Case name v Case name [____] ZA____ __</li>
                    </ol>
                  </article>
                </div>
              </section>
              <div className="zn-answer-actions">
                <button className="zn-outline" type="button" onClick={() => setActionNote("Nothing was sent.")}>Send to Email</button>
                <button className="zn-outline" type="button" onClick={() => setActionNote("Nothing was sent.")}>Send WhatsApp</button>
                <button className="zn-outline" type="button" onClick={() => setActionNote("Nothing was filed. A lawyer reviews before anything is filed.")}>Proceed to Legal Draft</button>
              </div>
            </article>
          </div>
          <form className="zn-composer" onSubmit={onAsk}>
            <label className="zn-sr" htmlFor="zenas-ask">Ask Zenas</label>
            <textarea id="zenas-ask" ref={askRef} rows={3} placeholder="Ask Zenas a civil legal question" />
            <div className="zn-composer-actions">
              <div>
                <label className="zn-outline zn-attach">
                  ＋ Attach
                  <input
                    className="zn-sr"
                    type="file"
                    onChange={(event) => setAttached(event.target.files?.[0]?.name ?? null)}
                  />
                </label>
                {attached ? <span className="zn-attached">{attached}</span> : null}
                <span className="zn-chip">Matter: {matter}</span>
              </div>
              <div className="zn-send-row">
                <span>Reasoning</span>
                <div className="zn-segment" role="group" aria-label="Reasoning">
                  <button className={reasoning === "Auto" ? "on" : ""} type="button" onClick={() => setReasoning("Auto")}>Auto</button>
                  <button className={reasoning === "High" ? "on" : ""} type="button" onClick={() => setReasoning("High")}>High</button>
                </div>
                <button className="zn-primary" type="submit">Send</button>
              </div>
            </div>
          </form>
          <p className="zn-disclaimer">Zenas provides legal information, not legal advice. A lawyer reviews before anything is filed.</p>
          {actionNote ? <p className="zn-note-line">{actionNote}</p> : null}
        </section>
        <section className="zn-work" aria-label="Your work">
          <article className="zn-card">
            <header>
              <h2>Recent matters</h2>
              <Link href="/matters">View all</Link>
            </header>
            <div className="zn-table" role="table">
              <div className="zn-tr head" role="row">
                <span role="columnheader">Matter</span>
                <span role="columnheader">Area</span>
                <span role="columnheader">Court</span>
                <span role="columnheader">Next date</span>
                <span role="columnheader">Status</span>
              </div>
              {Array.from({ length: MATTER_ROWS }, (_, index) => (
                <div className="zn-tr" role="row" key={index}>
                  <span>Case name v Case name</span>
                  <span>Area</span>
                  <span>Court</span>
                  <span>__ / __ / ____</span>
                  <span><i className="zn-chip">Status</i></span>
                </div>
              ))}
            </div>
          </article>
          <div className="zn-work-side">
            <article className="zn-card">
              <header>
                <h2>Review</h2>
                <Link href="/review">View all</Link>
              </header>
              {Array.from({ length: REVIEW_ROWS }, (_, index) => (
                <div className="zn-line" key={index}>
                  <span>
                    <strong>Item name</strong>
                    <em>Reviewer · __ / __ / ____</em>
                  </span>
                  <i className="zn-chip">Status</i>
                </div>
              ))}
            </article>
            <article className="zn-card">
              <header>
                <h2>Deadlines</h2>
                <button type="button">View all</button>
              </header>
              {DEADLINE_ROWS.map((row, index) => (
                <div className="zn-line" key={`${row.title}-${index}`}>
                  <span>
                    <strong>{row.title}</strong>
                    <em>{row.meta}</em>
                  </span>
                </div>
              ))}
            </article>
          </div>
        </section>
        </>
        ) : null}
      </div>
      {section === "chats" ? (
      <button className="zn-bot" type="button" onClick={() => askRef.current?.focus()}>
        Chat bot, to be named
      </button>
      ) : null}
      {areasOpen ? (
        <div
          ref={areasMenuRef}
          id={areasMenuId}
          className="zn-areas-menu"
          role="menu"
          aria-label="Areas of law"
          style={{ top: areasPos.top, left: areasPos.left }}
        >
          {AREAS.map((name) => (
            <button
              className={areaPick === name ? "on" : ""}
              key={name}
              type="button"
              role="menuitem"
              onClick={() => {
                setAreaPick(name);
                setAreasOpen(false);
              }}
            >
              {name}
            </button>
          ))}
        </div>
      ) : null}
      <PluginsDialog open={pluginsOpen} tab={tab} plugins={plugins} onTab={setTab} onClose={closePlugins} />
    </div>
  );
}
