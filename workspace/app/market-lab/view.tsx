"use client";

import { useEffect, useState } from "react";
import { useFormStatus } from "react-dom";
import { HELP_HREF, MARKET_LAB_LOGO_SRC, WORKSPACE_HREF } from "./catalog";
import type { LinkGroupView, OnCard, PageModel } from "./model";

const SECTIONS = ["overview", "on", "off", "linked"] as const;

function RefreshButton() {
  const { pending } = useFormStatus();
  return (
    <button className="ml-refresh" type="submit" disabled={pending}>
      {pending ? "Refreshing…" : "Refresh feeds"}
    </button>
  );
}

function scrollToSection(id: string) {
  const root = document.querySelector<HTMLElement>("[data-scroll-root]");
  const target = document.getElementById(id);
  if (!root || !target) return;
  const top = target.getBoundingClientRect().top - root.getBoundingClientRect().top + root.scrollTop;
  root.scrollTo({ top, behavior: "smooth" });
}

function OnCardView({ card }: { card: OnCard }) {
  const bare = !card.headline && !card.detail && card.lines.length === 0 && card.notices.length === 0 && !card.problem;
  return (
    <article className="ml-card">
      <h3>{card.title}</h3>
      <p className="ml-meta">
        {card.sourceLabel} · {card.cadence}
      </p>
      <p className="ml-summary">{card.summary}</p>
      {card.headline ? <p className="ml-value">{card.headline}</p> : null}
      {card.detail ? <p className="ml-detail">{card.detail}</p> : null}
      {card.lines.length ? (
        <ul className="ml-lines">
          {card.lines.map((line) => (
            <li key={`${card.id}-${line.label}`}>
              <span>{line.label}</span>
              <b>{line.value}</b>
            </li>
          ))}
        </ul>
      ) : null}
      {card.notices.length ? (
        <ul className="ml-notices">
          {card.notices.map((notice) => (
            <li key={`${card.id}-${notice.title}`}>
              <p>{notice.title}</p>
              <p className="ml-meta">{notice.meta}</p>
            </li>
          ))}
        </ul>
      ) : null}
      {card.problem ? <p className="ml-problem">{card.problem}</p> : null}
      {bare ? <p className="ml-quiet">No reading yet</p> : null}
    </article>
  );
}

function GroupCard({ group, open, onToggle }: { group: LinkGroupView; open: boolean; onToggle: () => void }) {
  const count = group.pages.length;
  return (
    <article className={open ? "ml-group open" : "ml-group"}>
      <header>
        <h3>{group.title}</h3>
        <span>{count}</span>
      </header>
      <p className="ml-cadence">{group.cadence}</p>
      <button type="button" className="ml-expand" onClick={onToggle} aria-expanded={open}>
        {open ? "Hide pages" : `${count} pages ›`}
      </button>
      <ul className="ml-pages">
        {group.pages.map((page) => (
          <li key={page.id}>
            <a href={page.href} target="_blank" rel="noreferrer">
              {page.label}
            </a>
            <span>{page.note}</span>
          </li>
        ))}
      </ul>
    </article>
  );
}

export function MarketLabView({ model, refresh }: { model: PageModel; refresh: () => Promise<void> }) {
  const [active, setActive] = useState<string>("overview");
  const [menu, setMenu] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [openGroups, setOpenGroups] = useState<Record<string, boolean>>({});
  const visual = [...model.featured, ...model.cards];
  const refreshedLine =
    model.refreshedLabel === "Not refreshed yet" ? "Not refreshed yet" : `Last refreshed ${model.refreshedLabel}`;

  useEffect(() => {
    const root = document.querySelector<HTMLElement>("[data-scroll-root]");
    if (!root) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        const id = visible?.target.id;
        if (id) setActive(id);
      },
      { root, rootMargin: "-20% 0px -55% 0px", threshold: [0.15, 0.4] },
    );
    for (const id of SECTIONS) {
      const section = document.getElementById(id);
      if (section) observer.observe(section);
    }
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!menu) return;
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setMenu(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [menu]);

  function go(id: string) {
    setActive(id);
    setMenu(false);
    scrollToSection(id);
  }

  const nav = [
    { id: "overview", label: "Overview", count: null },
    { id: "on", label: "On", count: model.onCount },
    { id: "off", label: "Off (needs a key)", count: model.offCount },
    { id: "linked", label: "Linked pages", count: model.linkedCount },
  ];

  return (
    <div className="ml">
      <header className="ml-top">
        <img src="/brand/tervory-logo-reversed.png" alt="Tervory" width={186} height={34} />
        <button type="button" className="ml-menu" aria-expanded={menu} onClick={() => setMenu(true)}>
          <span className="ml-burger" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          Menu
        </button>
      </header>

      {menu ? <button type="button" className="ml-dim" aria-label="Close menu" onClick={() => setMenu(false)} /> : null}

      <aside id="ml-panel" className={menu ? "ml-panel open" : "ml-panel"} data-panel-anchor="fixed">
        <div className="ml-panel-top">
          <img className="ml-logo" src="/brand/tervory-logo-reversed.png" alt="Tervory" width={186} height={34} />
          <button type="button" className="ml-close" aria-label="Close" onClick={() => setMenu(false)}>
            <span className="ml-x" />
          </button>
        </div>
        <div className="ml-slot" aria-hidden={MARKET_LAB_LOGO_SRC ? undefined : true}>
          {MARKET_LAB_LOGO_SRC ? <img src={MARKET_LAB_LOGO_SRC} alt="Market Lab" /> : null}
        </div>
        <p className="ml-kicker">Market Lab</p>
        <nav aria-label="Market Lab">
          {nav.map((item) => (
            <a
              key={item.id}
              className={active === item.id ? "ml-link active" : "ml-link"}
              href={`#${item.id}`}
              aria-current={active === item.id ? "true" : undefined}
              onClick={(event) => {
                event.preventDefault();
                go(item.id);
              }}
            >
              <span>{item.label}</span>
              {item.count === null ? null : <span className="ml-count">{item.count}</span>}
            </a>
          ))}
        </nav>
        <div className="ml-rule" />
        <nav aria-label="Workspace">
          <a className="ml-link" href={WORKSPACE_HREF}>
            Workspace
          </a>
          <a className="ml-link" href={HELP_HREF} target="_blank" rel="noreferrer">
            Help
          </a>
        </nav>
        <div className="ml-refreshed">
          <p className="ml-refreshed-label">Last refreshed</p>
          <p className="ml-time">{model.refreshedLabel}</p>
        </div>
      </aside>

      <div className="ml-main" data-scroll-root>
        <div className="ml-body">
          <section id="overview" className="ml-intro">
            <div>
              <p className="ml-crumb">
                <a href={WORKSPACE_HREF}>Workspace</a> / Market Lab
              </p>
              <h1>Market Lab</h1>
              <p className="ml-lead">
                The public data feeds Market Lab reads. A feed with a key shows its latest data. A feed without one stays off and is not called.
              </p>
            </div>
            <form action={refresh}>
              <RefreshButton />
              <p className="ml-under">{refreshedLine}</p>
            </form>
          </section>

          <div className="ml-stats">
            <div className="ml-stat">
              <b>{model.onCount}</b>
              <span className="ml-desk">feeds on and showing data</span>
              <span className="ml-mob">on</span>
            </div>
            <div className="ml-stat tint">
              <b>{model.offCount}</b>
              <span className="ml-desk">feeds off. Each needs a key.</span>
              <span className="ml-mob">off</span>
            </div>
            <div className="ml-stat">
              <b>{model.linkedCount}</b>
              <span className="ml-desk">linked pages, watched for changes</span>
              <span className="ml-mob">linked</span>
            </div>
          </div>

          <section id="on" className={showAll ? "ml-section ml-on ml-show-all" : "ml-section ml-on"}>
            <h2>On</h2>
            {model.loadError ? (
              <div className="ml-state">
                <h3>Feeds could not load</h3>
                <p>We could not read the feed status. Nothing has changed. Try Refresh feeds, or check back in a few minutes.</p>
              </div>
            ) : model.onEmpty ? (
              <div className="ml-state">
                <h3>No feed data yet</h3>
                <p>The feeds have not run yet. Their data shows here after the first refresh.</p>
              </div>
            ) : (
              <>
                <p className="ml-copy">These feeds have what they need. Each shows its latest data.</p>
                {model.featured.length ? (
                  <div className="ml-featured">
                    {model.featured.map((card, index) => (
                      <div key={card.id} className={index >= 3 ? "ml-extra" : undefined}>
                        <OnCardView card={card} />
                      </div>
                    ))}
                  </div>
                ) : null}
                {model.cards.length ? (
                  <div className="ml-cards">
                    {model.cards.map((card, index) => (
                      <div key={card.id} className={model.featured.length + index >= 3 ? "ml-extra" : undefined}>
                        <OnCardView card={card} />
                      </div>
                    ))}
                  </div>
                ) : null}
                {visual.length > 3 ? (
                  <button type="button" className="ml-more" onClick={() => setShowAll((value) => !value)}>
                    {showAll ? "Show fewer feeds" : `Show all ${model.onCount} feeds`}
                  </button>
                ) : null}
              </>
            )}
          </section>

          <section id="off" className="ml-section">
            <h2>Off</h2>
            <p className="ml-copy ml-copy-long">
              These feeds need a key that is not set. They stay off and Market Lab does not call them.
            </p>
            <p className="ml-copy ml-copy-short">These feeds need a key that is not set. They stay off and are not called.</p>
            <div className="ml-off">
              {model.off.map((row) => (
                <article key={row.id} className="ml-off-row">
                  <h3>{row.title}</h3>
                  <p className="ml-off-summary">{row.summary}</p>
                  <p className="ml-off-state">Off. Needs a key.</p>
                  <p className="ml-chip">{row.keyName}</p>
                  <p className="ml-not-called">Not called</p>
                </article>
              ))}
            </div>
          </section>

          <section id="linked" className="ml-section">
            <h2>Linked pages</h2>
            <p className="ml-copy ml-copy-long">
              Market Lab links to these pages and does not copy them. It checks the rule and season pages each week and notes when one changes.
            </p>
            <p className="ml-copy ml-copy-short">Linked, not copied. Rule and season pages are checked weekly.</p>
            <div className="ml-groups">
              {model.groups.map((group) => (
                <GroupCard
                  key={group.id}
                  group={group}
                  open={Boolean(openGroups[group.id])}
                  onToggle={() => setOpenGroups((current) => ({ ...current, [group.id]: !current[group.id] }))}
                />
              ))}
            </div>
          </section>

          <p className="ml-footer">
            Public sources only. Market Lab keeps counts, not names or addresses. FRED is read live and never stored.
          </p>
        </div>
      </div>
    </div>
  );
}
