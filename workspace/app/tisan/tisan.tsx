"use client";

import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { SquadLinks } from "../squad-links";
import {
  ALL_BUILDS,
  CHECKS,
  COLOURS,
  COMPONENTS,
  FILTERS,
  GAPS,
  OPENING_THREAD,
  PAGE_NAV,
  RECENT,
  RULES,
  SCORES,
  SPACING,
  STEPS,
  groupMeta,
  primaryAction,
  replyTo,
  resultSummary,
  searchRecords,
  showsChat,
  showsResults,
  toneFor,
  type Citation,
  type Dialog,
  type Filter,
  type Kind,
  type PluginTab,
  type View,
} from "./copy";
import { Plugins } from "./plugins";
import type { PluginPanel } from "./vault-model";

function Pill({ tone, children }: { tone: "solid" | "quiet"; children: ReactNode }) {
  return <span className={tone === "solid" ? "pill solid" : "pill quiet"}><i />{children}</span>;
}

function Tag() {
  return <span className="tag">Example</span>;
}

function Foot({ lines }: { lines: string[] }) {
  return (
    <footer className="foot">
      {lines.map((line, index) => <p key={line} className={index === lines.length - 1 ? "small" : undefined}>{line}</p>)}
    </footer>
  );
}

const GROUP_ORDER: Kind[] = ["Build", "Page", "Test"];

export function Tisan({ plugins }: { plugins: PluginPanel }) {
  const [view, setView] = useState<View>("overview");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<Filter>("all");
  const [dialog, setDialog] = useState<Dialog>("none");
  const [pluginTab, setPluginTab] = useState<PluginTab>("keys");
  const [menuOpen, setMenuOpen] = useState(false);
  const [mobile, setMobile] = useState(false);
  const [thread, setThread] = useState(OPENING_THREAD);
  const [draft, setDraft] = useState("");

  useEffect(() => {
    const media = window.matchMedia("(max-width: 800px)");
    const apply = () => setMobile(media.matches);
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, []);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setDialog("none");
      setMenuOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const action = primaryAction({ view, query, filter, dialog, pluginTab, mobile });
  const chat = showsChat(view, query, filter);
  const results = showsResults(view, query, filter);

  function show(next: View) {
    setDialog("none");
    setMenuOpen(false);
    setQuery("");
    setFilter("all");
    setView(next);
    document.querySelector(".body")?.scrollTo(0, 0);
  }

  function openPlugins() {
    setMenuOpen(false);
    setDialog("plugins");
  }

  function send(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    const reply = replyTo(text);
    setThread((current) => [...current, { role: "user", text }, { role: "assistant", text: reply.text, when: reply.when, sources: reply.sources }]);
    setDraft("");
  }

  const tabs: { id: View | "plugins"; label: string }[] = [
    ...PAGE_NAV.filter((item) => item.id !== "settings"),
    { id: "plugins", label: "Plugins" },
  ];

  const rootClass = ["tisan", dialog !== "none" ? "dialog-open" : "", menuOpen ? "menu-open" : ""].filter(Boolean).join(" ");
  const hits = searchRecords(query, filter);

  return (
    <div className={rootClass}>
      <header className="topbar">
        <img src="/brand/tervory-logo-reversed.png" alt="Tervory" />
        <button type="button" className="menu" aria-expanded={menuOpen} aria-controls="tisan-panel" onClick={() => setMenuOpen((open) => !open)}>
          {menuOpen ? "Close" : "Menu"}
        </button>
      </header>

      <aside id="tisan-panel" className="panel" aria-label="Tisan">
        <img className="panel-mark" src="/brand/tisan-on-dark.png" alt="Tisan" width={2806} height={701} />
        <div className="panel-top">
          <p className="account"><span>Account name</span> <Tag /></p>
          <nav aria-label="Workspace">
            <a className="nav" href="/ledger">Dashboard</a>
            <a className="nav" href="/tasks">Projects</a>
            <a className="nav" href="/">Chats</a>
          </nav>
          <SquadLinks className="squad-nav" linkClassName="nav" />
        </div>
        <div className="panel-own">
          <p className="agent">Tisan</p>
          <p className="role">Build agent</p>
          <nav aria-label="Tisan">
            {tabs.map((item) => {
              const id = item.id;
              const selected = id === "plugins" ? dialog === "plugins" : dialog !== "plugins" && view === id;
              if (id === "plugins") {
                return (
                  <button key={id} type="button" className={selected ? "nav on" : "nav"} aria-current={selected ? "page" : undefined} onClick={openPlugins}>
                    {item.label}
                  </button>
                );
              }
              return (
                <button key={id} type="button" className={selected ? "nav on" : "nav"} aria-current={selected ? "page" : undefined} onClick={() => show(id)}>
                  {item.label}
                </button>
              );
            })}
          </nav>
        </div>
        <div className="panel-bottom">
          <img className="panel-sign" src="/brand/tervory-logo-reversed.png" alt="Tervory" />
          <button type="button" className={view === "settings" && dialog !== "plugins" ? "nav on" : "nav"} aria-current={view === "settings" && dialog !== "plugins" ? "page" : undefined} onClick={() => show("settings")}>Settings</button>
          <a className="nav" href="/">Support</a>
        </div>
      </aside>

      <div className="body">
        {view === "overview" ? (
          <Overview
            startPrimary={action === "start"}
            sendPrimary={action === "send"}
            query={query}
            filter={filter}
            hits={hits}
            results={results}
            chat={chat}
            thread={thread}
            draft={draft}
            onQuery={setQuery}
            onFilter={setFilter}
            onStart={() => { setMenuOpen(false); setDialog("build"); }}
            onOpen={show}
            onDraft={setDraft}
            onSend={send}
          />
        ) : null}
        {view === "builds" ? <Builds startPrimary={action === "start"} onStart={() => setDialog("build")} /> : null}
        {view === "design" ? <Design startPrimary={action === "start"} onStart={() => setDialog("build")} /> : null}
        {view === "tests" ? <Tests startPrimary={action === "start"} onStart={() => setDialog("build")} /> : null}
        {view === "settings" ? <Settings startPrimary={action === "start"} onStart={() => setDialog("build")} /> : null}
      </div>

      {dialog === "plugins" ? (
        <Plugins onClose={() => setDialog("none")} tab={pluginTab} setTab={setPluginTab} desktopAction={action} plugins={plugins} />
      ) : null}
      {dialog === "build" ? <StartBuild onClose={() => setDialog("none")} /> : null}
    </div>
  );
}

function StartButton({ primary, onClick }: { primary: boolean; onClick: () => void }) {
  return (
    <button type="button" className={primary ? "primary page-primary" : "line page-primary"} data-primary={primary ? "true" : undefined} onClick={onClick}>
      Start build
    </button>
  );
}

function PageHead({ title, lede, primary, onStart }: { title: string; lede: string; primary: boolean; onStart: () => void }) {
  return (
    <header className="head">
      <div>
        <h1>{title}</h1>
        <p className="lede">{lede}</p>
      </div>
      <StartButton primary={primary} onClick={onStart} />
    </header>
  );
}

function Overview({
  startPrimary,
  sendPrimary,
  query,
  filter,
  hits,
  results,
  chat,
  thread,
  draft,
  onQuery,
  onFilter,
  onStart,
  onOpen,
  onDraft,
  onSend,
}: {
  startPrimary: boolean;
  sendPrimary: boolean;
  query: string;
  filter: Filter;
  hits: { id: string; kind: Kind; title: string; detail: string; view: View }[];
  results: boolean;
  chat: boolean;
  thread: { role: "user" | "assistant"; text: string; when?: string; sources?: Citation[] }[];
  draft: string;
  onQuery: (value: string) => void;
  onFilter: (value: Filter) => void;
  onStart: () => void;
  onOpen: (view: View) => void;
  onDraft: (value: string) => void;
  onSend: (event: FormEvent) => void;
}) {
  return (
    <>
      <PageHead
        title="Tisan"
        lede="Builds a website from a locked Figma page, tests it, and deploys it only when every check passes."
        primary={startPrimary}
        onStart={onStart}
      />
      <Search query={query} filter={filter} onQuery={onQuery} onFilter={onFilter} />
      {results ? <Results query={query} hits={hits} onOpen={onOpen} /> : null}
      {chat ? (
        <>
          <Stats />
          <Chat thread={thread} draft={draft} sendPrimary={sendPrimary} onDraft={onDraft} onSend={onSend} onOpen={onOpen} />
          <Current onOpen={() => onOpen("builds")} />
          <Recent onOpen={() => onOpen("builds")} />
          <Rules />
          <Foot lines={["Keys and tokens are stored on the server, never in the app code.", "Rows marked Example are samples, not a live build."]} />
        </>
      ) : null}
    </>
  );
}

function Search({ query, filter, onQuery, onFilter }: { query: string; filter: Filter; onQuery: (value: string) => void; onFilter: (value: Filter) => void }) {
  return (
    <form className="search" role="search" onSubmit={(event) => event.preventDefault()}>
      <label className="search-field">
        <span className="glass" aria-hidden="true">
          <svg viewBox="0 0 20 20" width="18" height="18"><circle cx="8.5" cy="8.5" r="5.5" fill="none" stroke="currentColor" strokeWidth="1.6" /><path d="M13 13.5L17 17.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" /></svg>
        </span>
        <span className="sr">Search builds, pages and tests</span>
        <input type="search" value={query} placeholder="Search builds, pages and tests" onChange={(event) => onQuery(event.target.value)} />
      </label>
      <div className="filters" role="group" aria-label="Record type">
        {FILTERS.map((item) => (
          <button key={item.id} type="button" className={filter === item.id ? "chip on" : "chip"} aria-pressed={filter === item.id} onClick={() => onFilter(item.id)}>
            {item.label}
          </button>
        ))}
        <p>Finds Tisan's own records only.</p>
      </div>
    </form>
  );
}

function Results({ query, hits, onOpen }: { query: string; hits: { id: string; kind: Kind; title: string; detail: string; view: View }[]; onOpen: (view: View) => void }) {
  return (
    <div className="results">
      <p className="result-count">{resultSummary(query, hits.length)}</p>
      {hits.length === 0 ? <p className="empty">Nothing in the example matches that.</p> : null}
      {GROUP_ORDER.map((kind) => {
        const rows = hits.filter((hit) => hit.kind === kind);
        if (rows.length === 0) return null;
        const meta = groupMeta(kind, rows.length);
        return (
          <section key={kind} className="result-group">
            <h2>{meta.heading}</h2>
            <p className="countline">{meta.countLabel}</p>
            <div className="result-card">
              {rows.map((row) => (
                <button key={row.id} type="button" className="result-row" onClick={() => onOpen(row.view)}>
                  <span className="pill quiet"><i />{row.kind}</span>
                  <span className="result-copy">
                    <strong>{row.title}</strong>
                    <span>{row.detail}</span>
                  </span>
                  <span className="open">Open →</span>
                </button>
              ))}
            </div>
          </section>
        );
      })}
      <Foot lines={["Search looks only at Tisan's own builds, pages and tests.", "Rows marked Example are samples, not a live build."]} />
    </div>
  );
}

function Stats() {
  return (
    <section className="counts" aria-label="Counts">
      <article className="count">
        <div className="stat-top"><b>2</b><Tag /></div>
        <strong className="desk">Waiting for your review</strong>
        <strong className="phone">Waiting for review</strong>
        <p className="fine">Draft pull requests Tisan opened.</p>
      </article>
      <article className="count">
        <div className="stat-top"><b className="desk">6 of 6</b><b className="phone">6/6</b><Tag /></div>
        <strong>Tests passing</strong>
        <p className="fine">On the last build.</p>
      </article>
      <article className="count">
        <div className="stat-top"><b>Off</b><Tag /></div>
        <strong>Deploy</strong>
        <p className="fine">Waits for the Radix scan.</p>
      </article>
    </section>
  );
}

function Chat({
  thread,
  draft,
  sendPrimary,
  onDraft,
  onSend,
  onOpen,
}: {
  thread: { role: "user" | "assistant"; text: string; when?: string; sources?: Citation[] }[];
  draft: string;
  sendPrimary: boolean;
  onDraft: (value: string) => void;
  onSend: (event: FormEvent) => void;
  onOpen: (view: View) => void;
}) {
  return (
    <section className="ask" aria-label="Chat">
      <h2>Ask Tisan</h2>
      <p className="intro">Type a request in plain English. The thread shows above the box, and each answer lists its sources.</p>
      <div className="thread">
        {thread.map((message, index) => (
          <article key={`${message.role}-${index}`} className={message.role === "user" ? "bubble you" : "bubble"}>
            <p className="who">{message.role === "user" ? "You" : "Tisan"}{message.role === "assistant" ? <> <Tag /></> : null}</p>
            <p>{message.text}</p>
            {message.when ? <p className="when">{message.when}</p> : null}
            {message.sources && message.sources.length > 0 ? (
              <div className="citations">
                <h3>Sources</h3>
                <ol>
                  {message.sources.map((source, sourceIndex) => (
                    <li key={source.title}>
                      <span className="cite-no">{sourceIndex + 1}</span>
                      <span>
                        <strong>{source.title}</strong>
                        <span>{source.detail}</span>
                      </span>
                      <button type="button" className="text" onClick={() => onOpen(source.view)}>Open →</button>
                    </li>
                  ))}
                </ol>
              </div>
            ) : null}
          </article>
        ))}
      </div>
      <form className="composer" onSubmit={onSend}>
        <label>
          <span className="sr">Request</span>
          <textarea
            value={draft}
            placeholder="Ask Tisan to build or change something…"
            rows={2}
            onChange={(event) => onDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                event.currentTarget.form?.requestSubmit();
              }
            }}
          />
        </label>
        <button type="submit" className={sendPrimary ? "primary send" : "line send"} data-primary={sendPrimary ? "true" : undefined}>
          Send
        </button>
      </form>
    </section>
  );
}

function Current({ onOpen }: { onOpen: () => void }) {
  return (
    <section className="block">
      <h2>Current build</h2>
      <p className="intro">Where the build is now. Each step must finish before the next one starts.</p>
      <div className="panel-card">
        <div className="card-head">
          <div>
            <h3>Tervory landing page <Tag /></h3>
            <p>Draft pull request #98 · Branch tisan/landing · Started 7:12 AM PT</p>
          </div>
          <button type="button" className="text" onClick={onOpen}>Open pull request →</button>
        </div>
        <div className="steps">
          {STEPS.map((step) => (
            <article key={step.n}>
              <p className="kicker">Step {step.n}</p>
              <h4>{step.title}</h4>
              <Pill tone={step.tone}>{step.state}</Pill>
              <p>{step.detail}</p>
            </article>
          ))}
        </div>
        <ol className="step-list">
          {STEPS.map((step) => (
            <li key={step.n}>
              <span>{step.n}</span>
              <strong>{step.title}</strong>
              <Pill tone={step.tone}>{step.state}</Pill>
            </li>
          ))}
        </ol>
        <p className="card-note desk">Tisan deploys only when every test passes and the scan comes back clean. It never merges on its own.</p>
        <p className="card-note phone">Deploy waits for a clean Radix scan. Tisan never merges on its own.</p>
        <button type="button" className="text phone-link" onClick={onOpen}>Open pull request →</button>
      </div>
    </section>
  );
}

function Recent({ onOpen }: { onOpen: () => void }) {
  return (
    <section className="block">
      <h2>Recent builds</h2>
      <p className="intro">The last builds and how they did.</p>
      <div className="table-wrap">
        <table className="recent">
          <thead>
            <tr>
              <th>Build</th>
              <th className="mid">Tests</th>
              <th className="mid">Scan</th>
              <th className="mid">Deploy</th>
              <th className="end">When</th>
            </tr>
          </thead>
          <tbody>
            {RECENT.map((row) => (
              <tr key={row.detail}>
                <td>
                  <strong>{row.title}</strong>
                  <span>{row.detail}</span>
                </td>
                <td className="mid"><Pill tone="solid">{row.tests}</Pill></td>
                <td className="mid"><Pill tone="quiet">{row.scan}</Pill></td>
                <td className="mid"><Pill tone="quiet">{row.deploy}</Pill></td>
                <td className="end">{row.when}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="recent-cards">
        {RECENT.map((row) => (
          <article key={row.detail}>
            <h3>{row.title}</h3>
            <p>{row.detail}</p>
            <p className="chips"><span>Tests <Pill tone="solid">{row.tests}</Pill></span><span>Deploy <Pill tone="quiet">{row.deploy}</Pill></span></p>
          </article>
        ))}
      </div>
      <button type="button" className="text see" onClick={onOpen}>See all builds →</button>
    </section>
  );
}

function Rules() {
  return (
    <section className="block">
      <h2>How Tisan works</h2>
      <p className="intro">Rules Tisan follows on every build.</p>
      <div className="rules">
        {RULES.map((rule) => (
          <article key={rule.title}>
            <h3>{rule.title}</h3>
            <p>{rule.detail}</p>
          </article>
        ))}
      </div>
    </section>
  );
}

function Builds({ startPrimary, onStart }: { startPrimary: boolean; onStart: () => void }) {
  return (
    <>
      <PageHead title="Builds" lede="Every build Tisan has run, and how it did on the test gate." primary={startPrimary} onStart={onStart} />
      <section className="block tight">
        <h2>All builds</h2>
        <p className="intro">A build can deploy only when every check passes and the scan is clean.</p>
        <div className="table-wrap">
          <table className="builds">
            <colgroup>
              <col className="c-name" />
              <col className="c-pill" />
              <col className="c-pill" />
              <col className="c-pill" />
              <col className="c-score" />
              <col className="c-pill" />
              <col className="c-pill" />
            </colgroup>
            <thead>
              <tr>
                <th>Build</th>
                <th className="mid">Code checks</th>
                <th className="mid">Screens</th>
                <th className="mid">Accessibility</th>
                <th className="mid">Lighthouse</th>
                <th className="mid">Scan</th>
                <th className="mid">Deploy</th>
              </tr>
            </thead>
            <tbody>
              {ALL_BUILDS.map((row) => (
                <tr key={row.detail}>
                  <td>
                    <strong>{row.title}</strong>
                    <span>{row.detail}</span>
                  </td>
                  <td className="mid"><Pill tone={toneFor(row.code)}>{row.code}</Pill></td>
                  <td className="mid"><Pill tone={toneFor(row.screens)}>{row.screens}</Pill></td>
                  <td className="mid"><Pill tone={toneFor(row.access)}>{row.access}</Pill></td>
                  <td className="mid score">{row.light}</td>
                  <td className="mid"><Pill tone={toneFor(row.scan)}>{row.scan}</Pill></td>
                  <td className="mid"><Pill tone={toneFor(row.deploy)}>{row.deploy}</Pill></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="aside-note">Code checks are lint, type checks, unit tests and the production build. Screens means Playwright at 390, 768 and 1440 wide.</p>
      </section>
      <Foot lines={["Tisan never merges a build. You review each draft pull request.", "Rows marked Example are samples, not a live build."]} />
    </>
  );
}

function Design({ startPrimary, onStart }: { startPrimary: boolean; onStart: () => void }) {
  return (
    <>
      <PageHead title="Design" lede="The locked Figma page Tisan builds from, the tokens it read, and the gaps it found." primary={startPrimary} onStart={onStart} />
      <section className="block tight">
        <h2>Locked page</h2>
        <p className="intro">Tisan reads one saved page. It never calls Figma while it builds.</p>
        <div className="locked">
          <div>
            <h3>Landing — Desktop & Mobile <Pill tone="solid">Locked</Pill> <Tag /></h3>
            <p>Saved copy in the repo · Read 16 Oct, 3:10 PM PT</p>
          </div>
          <div>
            <h3>Live Figma reads are off.</h3>
            <p>Tisan builds only from this saved page. To change the design, update the saved page.</p>
          </div>
        </div>
      </section>
      <section className="block">
        <div className="part-title"><h2>Tokens</h2><Tag /></div>
        <p className="intro">Named colours, type and spacing read from the saved page.</p>
        <div className="tokens">
          <article>
            <h3>Colours</h3>
            <ul className="swatches">
              {COLOURS.map((colour) => (
                <li key={colour.hex}>
                  <span className={`swatch ${colour.swatch}`} />
                  <span>
                    <strong>{colour.name}</strong>
                    <span className="hex">{colour.hex}</span>
                  </span>
                </li>
              ))}
            </ul>
          </article>
          <article>
            <h3>Type</h3>
            <p className="kicker">Headings</p>
            <p className="face display">Jost Light</p>
            <p className="kicker">Body</p>
            <p className="face body">Inter Regular</p>
            <p className="sizes">Sizes: 44, 36, 26, 16, 14, 12</p>
          </article>
          <article>
            <h3>Spacing</h3>
            <ul className="spaces">
              {SPACING.map((size) => (
                <li key={size}>
                  <span>{size}</span>
                  <i style={{ width: `${(size / 48) * 100}%` }} />
                </li>
              ))}
            </ul>
            <p className="sizes">Read from the layout. Not named in Figma.</p>
          </article>
        </div>
      </section>
      <section className="block">
        <div className="part-title"><h2>Gaps found</h2><Tag /></div>
        <p className="intro">Tisan lists what it could not find instead of guessing. These come from the saved copy and are not confirmed against the live file.</p>
        <div className="table-wrap">
          <table className="plain">
            <thead>
              <tr>
                <th>What is missing</th>
                <th>What Tisan did</th>
                <th className="end">Status</th>
              </tr>
            </thead>
            <tbody>
              {GAPS.map((gap) => (
                <tr key={gap.title}>
                  <td><strong>{gap.title}</strong><span>{gap.detail}</span></td>
                  <td>{gap.did}</td>
                  <td className="end"><Pill tone="quiet">Not confirmed</Pill></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="block">
        <div className="part-title"><h2>Component map</h2><Tag /></div>
        <p className="intro">Each Figma component and the part of the site built from it.</p>
        <div className="table-wrap">
          <table className="plain">
            <thead>
              <tr>
                <th>Figma component</th>
                <th>Built as</th>
                <th className="end">Status</th>
              </tr>
            </thead>
            <tbody>
              {COMPONENTS.map((row) => (
                <tr key={row.title}>
                  <td><strong>{row.title}</strong><span>{row.detail}</span></td>
                  <td>{row.built}</td>
                  <td className="end"><Pill tone="solid">Mapped</Pill></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <Foot lines={["The saved page is the approved read. A live Figma call is not approved.", "Rows marked Example are samples, not a live build."]} />
    </>
  );
}

function Tests({ startPrimary, onStart }: { startPrimary: boolean; onStart: () => void }) {
  return (
    <>
      <PageHead title="Tests" lede="The test gate every build must pass before it can go any further." primary={startPrimary} onStart={onStart} />
      <section className="block tight">
        <div className="part-title"><h2>Lighthouse scores</h2><Tag /></div>
        <p className="intro">From the last build. Each score must be 90 or above.</p>
        <div className="scores">
          {SCORES.map((score) => (
            <article key={score.label}>
              <div className="stat-top"><b>{score.score}</b><Tag /></div>
              <strong>{score.label}</strong>
              <p>Must be 90 or above.</p>
            </article>
          ))}
        </div>
      </section>
      <section className="block">
        <div className="part-title"><h2>Checks</h2><Tag /></div>
        <p className="intro">What each check proves, and how it did on the last build.</p>
        <div className="table-wrap">
          <table className="plain checks">
            <thead>
              <tr>
                <th>Check</th>
                <th>What it proves</th>
                <th className="end">Result</th>
              </tr>
            </thead>
            <tbody>
              {CHECKS.map((check) => (
                <tr key={check.title}>
                  <td><strong>{check.title}</strong><span>{check.tool}</span></td>
                  <td>{check.proves}</td>
                  <td className="end"><Pill tone={check.tone}>{check.result}</Pill></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <section className="block">
        <h2>Shared agent tests</h2>
        <p className="intro">Seven tests every Tervory agent will share.</p>
        <div className="waiting">
          <h3>Not added yet <Pill tone="quiet">Waiting</Pill></h3>
          <p>They need a gold set of examples and a trap-case runner first. Tisan will add them when those exist.</p>
        </div>
      </section>
      <Foot lines={["Tests run on every build. A failed check stops the build.", "Rows marked Example are samples, not a live build."]} />
    </>
  );
}

function Settings({ startPrimary, onStart }: { startPrimary: boolean; onStart: () => void }) {
  return (
    <>
      <PageHead title="Settings" lede="How Tisan builds, where it reads from, and when it may deploy." primary={startPrimary} onStart={onStart} />
      <section className="block tight">
        <div className="part-title"><h2>Building</h2><Tag /></div>
        <div className="settings">
          <Setting title="Repository" detail="Tisan works in tervory-tank and opens draft pull requests only." control={<span className="repo">tervory-tank</span>} />
          <Setting title="Merging" detail="Tisan never merges. You review and merge each pull request." control={<Pill tone="quiet">Off</Pill>} />
          <Setting title="Public internet" detail="Tisan has no route to the public internet while it builds." control={<Pill tone="quiet">Off</Pill>} />
        </div>
      </section>
      <section className="block">
        <div className="part-title"><h2>Design source</h2><Tag /></div>
        <div className="settings">
          <Setting title="Saved Figma page" detail="The approved read. Tisan builds from the saved copy in the repo." control={<Pill tone="solid">On</Pill>} />
          <Setting title="Live Figma reads" detail="Not approved. Tisan does not call Figma live." control={<Pill tone="quiet">Off</Pill>} />
        </div>
      </section>
      <section className="block">
        <div className="part-title"><h2>Deploy</h2><Tag /></div>
        <div className="settings">
          <Setting title="Coolify deploy" detail="Deploys only after the tests pass and the Radix scan is clean." control={<Pill tone="quiet">Off</Pill>} />
          <Setting title="Deploy key" detail="Set by your admin in Plugins. Shown as dots once saved." control={<Pill tone="quiet">Not set</Pill>} />
        </div>
      </section>
      <Foot lines={["Keys and tokens are stored on the server, never in the app code.", "Rows marked Example are samples, not a live build."]} />
    </>
  );
}

function Setting({ title, detail, control }: { title: string; detail: string; control: ReactNode }) {
  return (
    <div className="setting">
      <div>
        <h3>{title}</h3>
        <p>{detail}</p>
      </div>
      <div className="setting-ctl">{control}</div>
    </div>
  );
}

function StartBuild({ onClose }: { onClose: () => void }) {
  return (
    <div className="scrim" role="presentation">
      <div className="popup build-popup" role="dialog" aria-modal="true" aria-labelledby="start-title">
        <div className="popup-head">
          <h2 id="start-title">Start a build</h2>
          <button type="button" className="text" onClick={onClose}>Close</button>
        </div>
        <p className="sub">Tell Tisan what to build. It uses the locked Figma page for the design.</p>
        <form onSubmit={(event) => event.preventDefault()}>
          <label className="stack-label">
            What should Tisan build?
            <textarea placeholder="e.g. A one-page site for a gunsmith in Boise, with a contact form." rows={4} />
          </label>
          <p className="hint"><Tag /> Example text. Plain English is fine.</p>
          <p className="kicker">Design</p>
          <div className="design-row">
            <span>Landing — Desktop & Mobile (saved page)</span>
            <Pill tone="solid">Locked</Pill>
          </div>
          <div className="next">
            <h3>What happens next</h3>
            <ol>
              <li>Tisan builds the site on a new branch.</li>
              <li>It runs every test: code checks, three screen sizes, accessibility and Lighthouse.</li>
              <li>It opens a draft pull request for you. It does not merge or deploy.</li>
            </ol>
          </div>
          <div className="dialog-actions">
            <button type="button" className="line" onClick={onClose}>Cancel</button>
            <button type="submit" className="primary" data-primary="true">Start build</button>
          </div>
        </form>
      </div>
    </div>
  );
}
