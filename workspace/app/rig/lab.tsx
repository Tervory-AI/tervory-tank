"use client";

import { useEffect, useState } from "react";
import {
  BUILT,
  CHANGES,
  DECIDED,
  PLAN,
  REFRESHED,
  SKIN_STEPS,
  TABS,
  WAITING,
  type TabId,
  type WaitingFit,
} from "./copy";
import { Plugins } from "./plugins";
import { SearchView } from "./search-view";

type NavLink = { href: string; label: string };
type Decided = { id: string; name: string; fits: string; why: string; state: string; on: boolean };

function Pill({ children, on = true }: { children: string; on?: boolean }) {
  return (
    <span className={on ? "pill" : "pill off"}>
      <i />
      {children}
    </span>
  );
}

function CompactSearch({ onSearch }: { onSearch: (query: string) => void }) {
  return (
    <form
      className="compact"
      role="search"
      onSubmit={(event) => {
        event.preventDefault();
        const data = new FormData(event.currentTarget);
        const query = String(data.get("q") ?? "").trim();
        if (query) onSearch(query);
      }}
    >
      <input name="q" placeholder="Search a brand, model or part" aria-label="Search a brand, model or part" />
      <button type="submit" className="line">
        Search
      </button>
    </form>
  );
}

export function Lab({
  standardNav,
  products,
  fits,
  live,
}: {
  standardNav: NavLink[];
  products: number;
  fits: number;
  live: boolean;
}) {
  const [tab, setTab] = useState<TabId>("search");
  const [pluginsOpen, setPluginsOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [query, setQuery] = useState("Staccato");
  const [waiting, setWaiting] = useState<WaitingFit[]>(WAITING);
  const [decided, setDecided] = useState<Decided[]>(DECIDED.map((row) => ({ ...row })));
  const [approve, setApprove] = useState<WaitingFit | null>(null);
  const [keySaved, setKeySaved] = useState(true);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setPluginsOpen(false);
      setMenuOpen(false);
      setApprove(null);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  function show(next: TabId) {
    setPluginsOpen(false);
    setMenuOpen(false);
    setApprove(null);
    setTab(next);
  }

  function searchFrom(value: string) {
    setQuery(value);
    show("search");
  }

  function confirmApprove() {
    if (!approve) return;
    setDecided((current) => [{ id: approve.id, name: approve.name, fits: approve.fits, why: approve.why, state: "Approved", on: true }, ...current]);
    setWaiting((current) => current.filter((row) => row.id !== approve.id));
    setApprove(null);
  }

  function reject(row: WaitingFit) {
    setDecided((current) => [{ id: row.id, name: row.name, fits: row.fits, why: row.why, state: "Rejected", on: false }, ...current]);
    setWaiting((current) => current.filter((item) => item.id !== row.id));
  }

  const rootClass = ["rig", pluginsOpen || approve ? "modal-open" : "", menuOpen ? "menu-open" : ""].filter(Boolean).join(" ");

  return (
    <div className={rootClass}>
      <header className="topbar">
        <img src="/brand/tervory-logo-reversed.png" alt="Tervory" width={186} height={34} />
        <button type="button" className="menu" aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)}>
          Menu
        </button>
      </header>

      <aside className="panel" aria-label="Rig">
        <div className="panel-top">
          <img src="/brand/tervory-logo-reversed.png" alt="Tervory" width={186} height={34} />
          <nav className="std" aria-label="Standard">
            {standardNav.map((link) => (
              <a key={link.href} href={link.href}>
                {link.label}
              </a>
            ))}
          </nav>
        </div>
        <div className="panel-own">
          <p className="rig-label">RIG</p>
          <nav aria-label="Rig">
            {TABS.map((item) => (
              <button key={item.id} type="button" className={item.id === tab && !pluginsOpen ? "nav on" : "nav"} aria-current={item.id === tab && !pluginsOpen ? "page" : undefined} onClick={() => show(item.id)}>
                {item.label}
              </button>
            ))}
            <button type="button" className={pluginsOpen ? "nav on" : "nav"} aria-expanded={pluginsOpen} onClick={() => { setMenuOpen(false); setApprove(null); setPluginsOpen(true); }}>
              Plugins
            </button>
          </nav>
        </div>
        <div className="panel-bottom">
          <a className="nav" href="/">
            Workspace
          </a>
          <button type="button" className="nav">
            Help
          </button>
          <p className="refreshed">
            <span>Last refreshed</span>
            <b>{REFRESHED}</b>
          </p>
        </div>
      </aside>

      <div className={tab === "search" ? "body home" : "body"}>
        {tab === "search" ? <SearchView query={query} onQuery={setQuery} /> : null}

        {tab === "overview" ? (
          <>
            <header className="head">
              <div className="titles">
                <h1>Rig</h1>
                <p className="lede">Finds the parts that fit and puts the customer's build together at the best prices.</p>
              </div>
              <CompactSearch onSearch={searchFrom} />
              <a className="primary" href="https://rig.tervory.com">
                Open live search
              </a>
            </header>
            <section className="counts" aria-label="Counts">
              <article className="count">
                <b>{live ? "Up" : "Down"}</b>
                <strong>rig.tervory.com</strong>
                <p className="fine">{live ? "The live search page is running." : "The live search page did not answer."}</p>
              </article>
              <article className="count">
                <b>{products}</b>
                <strong>Products</strong>
                <p className="fine">In the Staccato demo catalogue.</p>
              </article>
              <article className="count">
                <b>{fits}</b>
                <strong>Approved fits</strong>
                <p className="fine">Parts confirmed to fit a pistol.</p>
              </article>
            </section>
            <section className="block">
              <h2>Live now</h2>
              <p className="intro">What shoppers see on rig.tervory.com today.</p>
              <div className="cards">
                <article className="card">
                  <div className="card-top">
                    <h3>Live site</h3>
                    <Pill on={live}>{live ? "Up" : "Down"}</Pill>
                  </div>
                  <p>rig.tervory.com, Tervory skin. Searches the Staccato demo catalogue.</p>
                  <p className="meta">Version 81bda21 · live since 3:57 PM PT</p>
                </article>
                <article className="card">
                  <div className="card-top">
                    <h3>Search checks</h3>
                    <Pill>Passed</Pill>
                  </div>
                  <p className="big">
                    5 of 5 <span>checks passed</span>
                  </p>
                  <p className="meta">Right product in the top 3, “I don't know” for things we don't stock, under 300 ms.</p>
                </article>
                <article className="card">
                  <div className="card-top">
                    <h3>Distributor feeds</h3>
                    <Pill on={false}>Off</Pill>
                  </div>
                  <p>Rig uses stand-in products for now. Real feeds go on once the search is proven.</p>
                  <p className="meta">Needs Zenas's OK to turn on</p>
                </article>
              </div>
            </section>
            <section className="block">
              <h2>What's built</h2>
              <p className="intro">Stage R4 is finished and live.</p>
              <div className="sheet">
                {BUILT.map((row) => (
                  <div className="wide-row" key={row.title}>
                    <div>
                      <h3>{row.title}</h3>
                      <p>{row.text}</p>
                    </div>
                    <Pill>Done</Pill>
                  </div>
                ))}
              </div>
            </section>
            <section className="block">
              <h2>Next step</h2>
              <article className="card">
                <div className="card-top">
                  <h3>R5 — 3D models</h3>
                  <Pill on={false}>Next</Pill>
                </div>
                <p>A simple 3D model of each pistol and part. Fit comes from maker standards, like the RMSc optic footprint, so the models don't have to be perfect.</p>
                <button type="button" className="text more" onClick={() => show("progress")}>
                  See progress →
                </button>
              </article>
            </section>
            <footer className="foot">
              <p>Stand-in products only. Rig does not read real distributor feeds yet.</p>
              <p className="small">Prices are demo figures in rand.</p>
            </footer>
          </>
        ) : null}

        {tab === "catalogues" ? (
          <>
            <header className="head">
              <div className="titles">
                <h1>Catalogues</h1>
                <p className="lede">The product lists Rig searches. Everything here is stand-in data for now.</p>
              </div>
              <CompactSearch onSearch={searchFrom} />
              <button type="button" className="primary">
                Add a catalogue
              </button>
            </header>
            <section className="counts">
              <article className="count">
                <b>3</b>
                <strong>Catalogues</strong>
                <p className="fine">Loaded and searchable.</p>
              </article>
              <article className="count">
                <b>{products}</b>
                <strong>Products on the live page</strong>
                <p className="fine">From the Staccato demo catalogue.</p>
              </article>
              <article className="count">
                <b>0</b>
                <strong>Distributor feeds on</strong>
                <p className="fine">Real feeds stay off until the search is proven.</p>
              </article>
            </section>
            <section className="block">
              <h2>Loaded catalogues</h2>
              <p className="intro">Each shop's products stay in their own catalogue. Results never mix between shops.</p>
              <div className="sheet">
                <table className="catalogues">
                  <thead>
                    <tr>
                      <th>Catalogue</th>
                      <th>Products</th>
                      <th>Fits</th>
                      <th>Prices</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td>
                        <strong>Staccato demo</strong>
                        <p>Staccato pistols and parts from a stand-in distributor sheet.</p>
                      </td>
                      <td className="num">{products}</td>
                      <td className="num">{fits}</td>
                      <td>Retailer price, plus 2 demo shops for the market average</td>
                      <td><Pill>On the live page</Pill></td>
                    </tr>
                    <tr>
                      <td>
                        <strong>Rifle test set</strong>
                        <p>A rifle, a scope and rings. Used by the automatic search checks.</p>
                      </td>
                      <td className="num">3</td>
                      <td className="num">3</td>
                      <td>Retailer price only</td>
                      <td><Pill on={false}>Tests only</Pill></td>
                    </tr>
                    <tr>
                      <td>
                        <strong>Second shop test set</strong>
                        <p>Non-gun products from a second shop. Proves results never cross between shops.</p>
                      </td>
                      <td className="num">2</td>
                      <td className="num">1</td>
                      <td>Retailer price only</td>
                      <td><Pill on={false}>Tests only</Pill></td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
            <section className="block">
              <h2>Distributor feeds</h2>
              <p className="intro">Where real products will come from later.</p>
              <article className="card">
                <div className="card-top">
                  <h3>Distributor product feeds</h3>
                  <Pill on={false}>Off</Pill>
                </div>
                <p>Rig is tested on stand-in products only, never on the real feeds. Feeds are connected once the search is proven and Zenas says yes. Their keys go in the Plugins tab.</p>
                <button type="button" className="text more" onClick={() => setPluginsOpen(true)}>
                  Open Plugins →
                </button>
              </article>
            </section>
            <footer className="foot">
              <p>Stand-in products only. Prices are demo figures.</p>
              <p className="small">Market average prices are shown once a shopper's selection is final.</p>
            </footer>
          </>
        ) : null}

        {tab === "fits" ? (
          <>
            <header className="head">
              <div className="titles">
                <h1>Fits to review</h1>
                <p className="lede">New fits wait here until an admin approves them. Shoppers only see approved fits.</p>
              </div>
              <CompactSearch onSearch={searchFrom} />
              <button type="button" className="primary">
                Find new fits
              </button>
            </header>
            <article className="card key-card">
              <div>
                <h3>Admin key</h3>
                <p>Approving or rejecting a fit needs the admin key. Once saved it is never shown again.</p>
              </div>
              {keySaved ? (
                <div className="mask">{`•••• saved 17 Oct`}</div>
              ) : (
                <input type="password" aria-label="Admin key" placeholder="Paste key" autoComplete="off" />
              )}
              <button
                type="button"
                className="text"
                onClick={() => {
                  setKeySaved((saved) => !saved);
                }}
              >
                Replace
              </button>
            </article>
            <section className="counts">
              <article className="count">
                <b>{waiting.length}</b>
                <strong>Waiting</strong>
                <p className="fine">Suggested fits not yet decided.</p>
              </article>
              <article className="count">
                <b>{fits}</b>
                <strong>Approved</strong>
                <p className="fine">Showing to shoppers now.</p>
              </article>
              <article className="count">
                <b>{decided.filter((row) => !row.on).length}</b>
                <strong>Rejected</strong>
                <p className="fine">Never shown to shoppers.</p>
              </article>
            </section>
            <section className="block">
              <h2>Waiting for review</h2>
              <p className="intro">Check each one against the maker's fit list before approving.</p>
              <div className="sheet">
                <table className="fits">
                  <thead>
                    <tr>
                      <th>Part</th>
                      <th>Why Rig thinks it fits</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {waiting.map((row) => (
                      <tr key={row.id}>
                        <td>
                          <strong>{row.name}</strong>
                          <p>{row.fits}</p>
                        </td>
                        <td>{row.why}</td>
                        <td className="act">
                          <button type="button" className="line" onClick={() => setApprove(row)}>
                            Approve
                          </button>
                          <button type="button" className="text" onClick={() => reject(row)}>
                            Reject
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <section className="block">
              <h2>Recently decided</h2>
              <div className="sheet">
                <table className="fits">
                  <thead>
                    <tr>
                      <th>Part</th>
                      <th>Reason</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {decided.map((row) => (
                      <tr key={row.id}>
                        <td>
                          <strong>{row.name}</strong>
                          <p>{row.fits}</p>
                        </td>
                        <td>{row.why}</td>
                        <td>
                          <Pill on={row.on}>{row.state}</Pill>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
            <footer className="foot">
              <p>Rig only looks for new fits when you press Find new fits. It never runs on its own.</p>
              <p className="small">Only approved fits are shown to shoppers.</p>
            </footer>
          </>
        ) : null}

        {tab === "skins" ? (
          <>
            <header className="head">
              <div className="titles">
                <h1>Skins</h1>
                <p className="lede">How Rig looks on each shop's site. A dealer's page carries the dealer's brand, never Tervory's.</p>
              </div>
              <CompactSearch onSearch={searchFrom} />
              <a className="primary" href="https://rig.tervory.com">
                Preview live page
              </a>
            </header>
            <section className="counts">
              <article className="count">
                <b>1</b>
                <strong>Live skin</strong>
                <p className="fine">Tervory, on rig.tervory.com.</p>
              </article>
              <article className="count">
                <b>1</b>
                <strong>Dealer skin planned</strong>
                <p className="fine">Custom Nation is first.</p>
              </article>
              <article className="count">
                <b>0</b>
                <strong>Dealer pages live</strong>
                <p className="fine">Built after the main product.</p>
              </article>
            </section>
            <section className="block">
              <h2>Skins</h2>
              <div className="skin-grid">
                <article className="card skin">
                  <div className="banner">Tervory skin preview</div>
                  <div className="card-top">
                    <h3>Tervory</h3>
                    <Pill>Live</Pill>
                  </div>
                  <p>The default skin. Tervory logo, navy and red. Used on rig.tervory.com.</p>
                  <a className="text more" href="https://rig.tervory.com">
                    Open rig.tervory.com →
                  </a>
                </article>
                <article className="card skin later">
                  <div className="banner dashed">Custom Nation skin preview, coming later</div>
                  <div className="card-top">
                    <h3>Custom Nation</h3>
                    <Pill on={false}>Later</Pill>
                  </div>
                  <p>The first dealer skin and our case study. Custom Nation's own logo, colours and prices. No Tervory branding anywhere on the page.</p>
                  <p className="meta">Starts once the main product is finished</p>
                </article>
              </div>
            </section>
            <section className="block">
              <h2>How a dealer skin works</h2>
              <ol className="sheet steps">
                {SKIN_STEPS.map((step, index) => (
                  <li key={step}>
                    <span>{index + 1}</span>
                    {step}
                  </li>
                ))}
              </ol>
            </section>
            <footer className="foot">
              <p>Dealer skins are planned, not built yet.</p>
            </footer>
          </>
        ) : null}

        {tab === "progress" ? (
          <>
            <header className="head">
              <div className="titles">
                <h1>Progress</h1>
                <p className="lede">Where Rig is on the build plan.</p>
              </div>
              <CompactSearch onSearch={searchFrom} />
              <button type="button" className="primary">
                Open build plan
              </button>
            </header>
            <section className="block">
              <h2>Build plan</h2>
              <div className="sheet">
                {PLAN.map((row) => (
                  <div className="plan-row" key={row.title}>
                    <b>{row.code}</b>
                    <div>
                      <h3>{row.title}</h3>
                      <p>{row.text}</p>
                    </div>
                    <Pill on={row.on}>{row.state}</Pill>
                  </div>
                ))}
              </div>
            </section>
            <section className="block">
              <h2>Recent changes</h2>
              <p className="intro">What went live most recently.</p>
              <div className="sheet">
                {CHANGES.map((row) => (
                  <div className="change-row" key={row.id}>
                    <span>Change #{row.id}</span>
                    <strong>{row.title}</strong>
                    <span>{row.when}</span>
                    <Pill>Live</Pill>
                  </div>
                ))}
              </div>
            </section>
            <footer className="foot">
              <p>Each change passes Rig's search checks before it goes live.</p>
            </footer>
          </>
        ) : null}
      </div>

      {pluginsOpen ? <Plugins onClose={() => setPluginsOpen(false)} /> : null}

      {approve ? (
        <div className="scrim" role="presentation">
          <div className="popup approve" role="dialog" aria-modal="true" aria-labelledby="approve-title">
            <div className="popup-head">
              <h2 id="approve-title">Approve this fit?</h2>
              <button type="button" className="text close" onClick={() => setApprove(null)}>
                Close
              </button>
            </div>
            <p className="sub">Once approved, shoppers see it as a compatible upgrade.</p>
            <article className="fit-summary">
              <h3>{approve.name}</h3>
              <p>{approve.fits}</p>
              <p>Why Rig thinks it fits: {approve.why.charAt(0).toLowerCase() + approve.why.slice(1)}</p>
            </article>
            <label className="admin-field">
              Admin key
              <input readOnly value={`•••• saved 17 Oct`} aria-label="Admin key" />
            </label>
            <div className="popup-actions">
              <button type="button" className="line" onClick={() => setApprove(null)}>
                Cancel
              </button>
              <button type="button" className="primary" onClick={confirmApprove}>
                Approve fit
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
