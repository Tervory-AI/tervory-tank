"use client";

import { useEffect, useRef, useState, type ReactNode, type KeyboardEvent } from "react";
import { Plugins } from "./plugins";
import { checks, exampleFindings, exampleReport } from "./content";
import { RadixDesk } from "./conversation";

type Section = "Overview" | "Findings" | "Reports";
const sections: Section[] = ["Overview", "Findings", "Reports"];

function keepDialogFocus(event: KeyboardEvent<HTMLDialogElement>) {
  if (event.key !== "Tab") return;
  const nodes = Array.from(event.currentTarget.querySelectorAll<HTMLElement>(
    'button, a[href], input, select, textarea, summary, [tabindex]:not([tabindex="-1"])',
  )).filter((node) => node.tabIndex >= 0 && !node.matches(":disabled") && node.getClientRects().length > 0);
  const first = nodes[0];
  const last = nodes[nodes.length - 1];
  if (!first) return;
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function Logo() {
  return <img src="/brand/tervory-logo-reversed.png" width={186} height={34} alt="Tervory" className="rx-logo" />;
}

export function RadixPage({ accountName, settings }: { accountName: string; settings: ReactNode }) {
  const [pluginsOpen, setPluginsOpen] = useState(false);
  const [vaultEnabled, setVaultEnabled] = useState(false);
  const [section, setSection] = useState<Section>("Overview");
  const [example, setExample] = useState(false);
  const [severity, setSeverity] = useState("All");
  const [query, setQuery] = useState("");
  const plugins = useRef<HTMLDialogElement>(null);
  const menu = useRef<HTMLDialogElement>(null);
  const body = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const pluginsTrigger = useRef<HTMLButtonElement | null>(null);
  const menuTrigger = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const media = window.matchMedia("(min-width: 801px)");
    function closeMenu() { if (media.matches) menu.current?.close(); }
    media.addEventListener("change", closeMenu);
    return () => media.removeEventListener("change", closeMenu);
  }, []);

  function navigate(next: Section, showExample = false) {
    menu.current?.close();
    setSection(next);
    setExample(showExample);
    setSeverity("All");
    setQuery("");
    body.current?.scrollTo({ top: 0 });
    requestAnimationFrame(() => heading.current?.focus());
  }
  function openPlugins(trigger: HTMLButtonElement) {
    const fromMenu = Boolean(menu.current?.open);
    menu.current?.close();
    pluginsTrigger.current = fromMenu ? menuTrigger.current : trigger;
    setPluginsOpen(true);
    plugins.current?.showModal();
  }
  function navigation() {
    return <>
      <a href="/" className="rx-brand" aria-label="Tervory workspace"><Logo /></a>
      <nav className="rx-standard" aria-label="Standard navigation">
        <p className="rx-account">{accountName}</p>
        <a href="/radix">Dashboard</a>
        <a href="/tasks">Projects</a>
        <a href="/">Chats</a>
      </nav>
      <div className="rx-page-nav">
        <p className="rx-kicker">Radix</p>
        <nav aria-label="Radix">
          {sections.map((item) => <button key={item} type="button" aria-current={section === item ? "page" : undefined}
            onClick={() => navigate(item)}>{item}</button>)}
          <button type="button" onClick={(event) => openPlugins(event.currentTarget)} aria-haspopup="dialog">Plugins</button>
        </nav>
      </div>
      <nav className="rx-bottom" aria-label="Workspace">
        <span onClickCapture={() => menu.current?.close()}>{settings}</span>
        <a href="https://tervory.com" target="_blank" rel="noreferrer">Support<span className="rx-sr"> (opens a new tab)</span></a>
      </nav>
    </>;
  }
  const filtered = exampleFindings.filter((finding) =>
    (severity === "All" || finding.severity === severity) &&
    (finding.title + " " + finding.file + " " + finding.rule).toLowerCase().includes(query.toLowerCase().trim()));
  return <div className="rx">
    <a className="rx-skip" href="#rx-heading">Skip to page content</a>
    <header className="rx-mobile-bar">
      <Logo />
      <button ref={menuTrigger} type="button" aria-haspopup="dialog" onClick={() => menu.current?.showModal()}>Menu</button>
    </header>
    <aside className="rx-panel" data-panel-anchor="fixed">{navigation()}</aside>
    <dialog className="rx-menu-dialog" ref={menu} aria-label="Navigation" onKeyDown={keepDialogFocus}>
      <button className="rx-menu-close" type="button" onClick={() => menu.current?.close()}>Close menu</button>
      {navigation()}
    </dialog>
    <div className="rx-body" ref={body} data-scroll-root>
      <p className="rx-crumb"><a href="/">Workspace</a> / Radix</p>
      <header className="rx-intro">
        <div>
          <h1 id="rx-heading" ref={heading} tabIndex={-1}>{section === "Overview" ? "Radix" : example ? "Example " + section.toLowerCase() : section}</h1>
          <p className="rx-lead">{section === "Overview"
            ? "Check code before it ships. Review exposed secrets, risky dependencies, and unsafe code."
            : example ? "Example only. These findings are made up to show the review flow."
            : "Review the checks made on code supplied to Radix."}</p>
        </div>
        {example ? <a className="rx-secondary" download="radix-example-report.md"
          href={"data:text/markdown;charset=utf-8," + encodeURIComponent(exampleReport())}>Download example report</a>
          : <button className="rx-secondary" type="button" onClick={() => navigate("Reports", true)}>View example report</button>}
      </header>

      <RadixDesk />

      <section className="rx-card rx-seal" aria-label="Outbound access">
        <h2>Outbound scans are off</h2>
        <p>A real client hostname must be named and approved before a site can be checked.</p>
      </section>

      {section === "Overview" ? <>
        <section aria-labelledby="rx-checks">
          <h2 id="rx-checks" className="rx-section-heading">Code checks</h2>
          <div className="rx-checks">{checks.map((check) => <article key={check.title} className="rx-card">
            <h3>{check.title}</h3><p>{check.copy}</p>
          </article>)}</div>
        </section>
        <section className="rx-card">
          <h2>Scan results are not connected</h2>
          <p>This page cannot load or start a scan yet. Open the example report to see how findings and fixes will appear.</p>
        </section>
        <section aria-labelledby="rx-flow">
          <h2 id="rx-flow" className="rx-section-heading">From finding to fix</h2>
          <ol className="rx-steps"><li>Review the file and rule.</li><li>Make the change.</li><li>Run a fresh check.</li></ol>
        </section>
      </> : !example ? <section className="rx-card rx-empty">
        <h2>{section === "Findings" ? "Findings are not connected" : "Reports are not connected"}</h2>
        <p>This page cannot read your scan history yet. That does not mean your code has no findings.</p>
        {section === "Findings" ? <button type="button" className="rx-text-button" onClick={() => navigate("Findings", true)}>Browse example findings</button> : null}
      </section> : <>
        <div className="rx-example-banner"><span className="rx-badge">Example</span><p>3 made-up findings. This is not a scan of your code or approval to release it.</p></div>
        <div className="rx-filter">
          <label>Severity<select aria-label="Severity" value={severity} onChange={(event) => setSeverity(event.target.value)}>
            {["All", "Critical", "High", "Medium"].map((value) => <option key={value}>{value}</option>)}
          </select></label>
          <label>Find a file or issue<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search example findings" /></label>
          <p role="status">{filtered.length} example {filtered.length === 1 ? "finding" : "findings"}</p>
        </div>
        <section className="rx-findings" aria-label="Example findings">
          {filtered.map((finding) => <article key={finding.id} className="rx-card">
            <div className="rx-finding-heading"><h2>{finding.title}</h2><span className="rx-badge">{finding.severity}</span></div>
            <p className="rx-meta">Example · {finding.file}:{finding.line}</p>
            <p>{finding.fix}</p>
            <details><summary>Review the fix</summary><p>{finding.detail}</p><p className="rx-meta">Rule: {finding.rule}</p></details>
          </article>)}
          {!filtered.length ? <div className="rx-card"><h2>No matching example findings</h2><p>Try another search or severity.</p><button type="button" className="rx-text-button" onClick={() => { setQuery(""); setSeverity("All"); }}>Clear filters</button></div> : null}
        </section>
        <button type="button" className="rx-text-button rx-exit-example" onClick={() => navigate(section)}>Leave example</button>
      </>}
      <footer className="rx-footnote">Code checks use supplied files. No website is scanned from this page.</footer>
    </div>
    <dialog ref={plugins} className="rx-plugins-dialog" aria-labelledby="rx-plugins-title" onKeyDown={keepDialogFocus}
      onClose={() => { setPluginsOpen(false); pluginsTrigger.current?.focus(); }}>
      <div className="rx-modal-header">
        <div><h2 id="rx-plugins-title">Plugins</h2><p>The files and connections Radix can use.</p></div>
        <button type="button" className="rx-text-button" onClick={() => plugins.current?.close()}>Close</button>
      </div>
      <Plugins open={pluginsOpen} onEnabled={setVaultEnabled} />
      <button type="button" className={vaultEnabled ? "rx-secondary" : "rx-primary"} onClick={() => plugins.current?.close()}>Done</button>
    </dialog>
  </div>;
}
