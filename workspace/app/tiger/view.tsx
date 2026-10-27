"use client";

import { useEffect, useState } from "react";
import { addProduct, removeProduct } from "./actions";
import { EVERY_OPTIONS, FOOT, FOOT_SMALL, LEDE } from "./copy";
import { SECTIONS, searchTiger, type AlertRow, type ProductRow, type ReadRow, type Section, type TigerData, type UnreadRow } from "./model";
import { SquadLinks } from "../squad-links";

function SearchIcon() {
  return (
    <svg className="search-icon" viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="7" cy="7" r="4.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      <path d="M10.5 10.5 L14 14" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function Pill({ status }: { status: string }) {
  const solid = status === "Price changed" || status === "Stock changed";
  const hollow = status === "Can't read";
  return <span className={solid ? "pill solid" : hollow ? "pill hollow" : "pill"}><i />{status}</span>;
}

export function TigerApp({
  data,
  notice,
  initialTab,
  accountName,
}: {
  data: TigerData;
  notice: string;
  initialTab: Section;
  accountName: string | null;
}) {
  const [section, setSection] = useState<Section>(initialTab);
  const [addOpen, setAddOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const [hidden, setHidden] = useState<string[]>([]);
  const [help, setHelp] = useState(false);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      setAddOpen(false);
      setMenuOpen(false);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const products = data.products.filter((row) => !hidden.includes(row.id));
  const visible: TigerData = { ...data, products };
  const hit = searchTiger(visible, query);
  const headerRed = !addOpen;

  function show(next: Section) {
    setMenuOpen(false);
    setAddOpen(false);
    setQuery("");
    setSection(next);
  }

  const rootClass = ["tiger", addOpen ? "add-open" : "", menuOpen ? "menu-open" : ""].filter(Boolean).join(" ");

  return (
    <div className={rootClass}>
      <header className="topbar">
        <img src="/brand/tervory-logo-reversed.png" alt="Tervory" />
        <button type="button" className="menu" aria-expanded={menuOpen} onClick={() => setMenuOpen((open) => !open)}>Menu</button>
      </header>

      <aside className="panel" aria-label="Tiger">
        <div className="panel-top">
          <img src="/brand/tiger-on-dark.png" alt="Tiger" width={2607} height={801} />
        </div>
        <nav className="panel-account" aria-label="Account">
          <p className="account">{accountName?.trim() || "Your account"}</p>
          <a className="nav" href="/">Dashboard</a>
          <a className="nav" href="/tasks" onClick={() => setMenuOpen(false)}>Tasks</a>
          <a className="nav" href="/chats" onClick={() => setMenuOpen(false)}>Chats</a>
        </nav>
        <SquadLinks className="panel-account squad-nav" linkClassName="nav" />
        <div className="panel-own">
          <nav aria-label="Tiger sections">
            {SECTIONS.map((item) => (
              <button key={item.id} type="button" className={item.id === section ? "nav on" : "nav"} onClick={() => show(item.id)}>
                {item.label}
              </button>
            ))}
          </nav>
        </div>
        <div className="panel-bottom">
          <img src="/brand/tervory-logo-reversed.png" alt="Tervory" width={186} height={34} />
          <button type="button" className="nav" onClick={() => { setHelp((open) => !open); setMenuOpen(false); }}>Support</button>
        </div>
      </aside>

      <div className="body">
        <form className={query ? "search on" : "search"} role="search" onSubmit={(event) => { event.preventDefault(); setQuery(draft.trim()); }}>
          <SearchIcon />
          <input
            aria-label="Search watched products, reads and alerts"
            placeholder="Search watched products, reads and alerts"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
          />
          {query ? (
            <button type="button" className="text" onClick={() => { setQuery(""); setDraft(""); }}>Clear</button>
          ) : (
            <span className="hint">Press Enter to search</span>
          )}
        </form>

        <header className="head">
          <div>
            <h1>Tiger</h1>
            <p className="lede">{LEDE}</p>
          </div>
          <button type="button" className={headerRed ? "primary" : "line"} onClick={() => setAddOpen(true)}>Add a product</button>
        </header>

        {notice ? <p className="notice">{notice}</p> : null}
        {help ? <p className="notice">Tiger checks public product pages and tells you when a price or stock changes. It never logs in, and it does not guess a price it could not read.</p> : null}

        {hit ? <Results hit={hit} /> : null}
        {!hit && section === "overview" ? <Overview data={visible} onWatch={() => show("watch")} onAlerts={() => show("alerts")} /> : null}
        {!hit && section === "alerts" ? <Alerts rows={data.alerts} example={data.example} /> : null}
        {!hit && section === "watch" ? (
          <Watch rows={products} note={data.listNote} onHide={(id) => setHidden((current) => [...current, id])} />
        ) : null}
        {!hit && section === "history" ? (
          <section className="block">
            <div className="title-row"><h2>History</h2></div>
            <p className="intro">The latest 40 readings from your watched pages.</p>
            <SimpleTable heads={["When", "Product", "Price", "Stock"]}
              rows={data.reads.map((row) => [row.when, row.product, row.price, row.stock])}
              empty="No readings yet." priceCol={2} />
          </section>
        ) : null}
        {!hit && section === "unread" ? (
          <Unread rows={data.unread} />
        ) : null}

        <footer className="foot">
          <p>{FOOT}</p>
          <p className="small">{FOOT_SMALL}</p>
        </footer>
      </div>

      {addOpen ? <AddProduct onClose={() => setAddOpen(false)} /> : null}
    </div>
  );
}

function Overview({ data, onWatch, onAlerts }: { data: TigerData; onWatch: () => void; onAlerts: () => void }) {
  const recent = data.alerts.slice(0, 3);
  return (
    <>
      <section className="counts" aria-label="Counts">
        <article className="count"><b>{data.watchedCount}</b><strong>{data.watchedCount === 1 ? "Watched product" : "Watched products"}</strong><p className="fine">Product pages Tiger checks.</p></article>
        <article className="count"><b>{data.changesToday}</b><strong>{data.changesToday === 1 ? "Change today" : "Changes today"}</strong><p className="fine">Real price or stock changes since midnight.</p></article>
        <article className="count"><b>{data.unreadCount}</b><strong>Can&apos;t read</strong><p className="fine">Pages Tiger could not read. Nothing was guessed.</p></article>
      </section>
      <section className="block">
        <div className="title-row">
          <h2>Latest reads</h2>
        </div>
        <p className="intro">The price and stock Tiger read on each watched page, next to that product’s add-to-cart button.</p>
        {data.products.length === 0 ? <p className="empty">No products watched yet.</p> : (
        <ul className="cards">
          {data.products.map((row) => (
            <li key={row.id}>
              <div className="card-top">
                <strong>{row.name}</strong>
                <Pill status={row.status} />
              </div>
              {row.status === "Can't read" ? (
                <p>Not read. Nothing was guessed.</p>
              ) : (
                <p className="price">{row.price} · {row.stock}</p>
              )}
              <p className="fine">{row.store}</p>
              <p className="fine">{row.status === "Not checked" ? "Not checked yet" : `Checked ${row.checked}`}{data.example ? " · Example" : ""}</p>
            </li>
          ))}
        </ul>
        )}
        {data.products.length === 0 ? null : (
        <>
        <div className="table-wrap overview-table">
          <table>
            <thead><tr><th>Product</th><th>Store</th><th>Price</th><th>Stock</th><th>Last checked</th><th>Status</th></tr></thead>
            <tbody>
              {data.products.map((row) => (
                <tr key={row.id}>
                  <td className="name">{row.name}</td>
                  <td className="muted">{row.store}</td>
                  <td className={row.price === "—" ? "muted" : "price"}>{row.price}</td>
                  <td>{row.stock}</td>
                  <td className="muted">{row.checked}</td>
                  <td><Pill status={row.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="table-foot">
          <span>{data.listNote ?? `${data.products.length} watched`}</span>
          <button type="button" className="text" onClick={onWatch}>See full watch list →</button>
        </div>
        </>
        )}
      </section>
      <section className="block">
        <div className="title-row">
          <h2>Recent alerts</h2>
        </div>
        <p className="intro">Only real changes. A page that can’t be read never sends an alert.</p>
        {recent.length === 0 ? <p className="empty">No alerts yet.</p> : (
        <ul className="cards">
          {recent.map((row) => (
            <li key={row.id}>
              <p className="fine">{row.when}</p>
              <strong>{row.product}</strong>
              <p>{row.change}</p>
            </li>
          ))}
        </ul>
        )}
        {recent.length === 0 ? null : (
        <>
        <div className="table-wrap overview-table">
          <table>
            <thead><tr><th>When</th><th>Product</th><th>What changed</th></tr></thead>
            <tbody>
              {recent.map((row) => (
                <tr key={row.id}><td className="muted">{row.when}</td><td className="name">{row.product}</td><td>{row.change}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="table-foot end">
          <button type="button" className="text" onClick={onAlerts}>See all alerts →</button>
        </div>
        </>
        )}
      </section>
    </>
  );
}

function Alerts({ rows, example }: { rows: AlertRow[]; example: boolean }) {
  const [kind, setKind] = useState<"All" | "Price" | "Stock">("All");
  const listed = rows.filter((row) => kind === "All" || row.kind === kind);
  return (
    <section className="block">
      <div className="title-row">
        <h2>Alerts</h2>
      </div>
      <p className="intro">Real price and stock changes. Tiger only alerts when it read the page clearly. A page that can’t be read never sends an alert.</p>
      {rows.length === 0 ? <p className="empty">No alerts yet.</p> : null}
      <div className="filters">
        {(["All", "Price", "Stock"] as const).map((item) => (
          <button key={item} type="button" className={kind === item ? "chip on" : "chip"} onClick={() => setKind(item)}>{item}</button>
        ))}
      </div>
      <div className="table-wrap">
        <table>
          <thead><tr><th>When</th><th>Product</th><th>Store</th><th>Change</th><th>Before</th><th>Now</th></tr></thead>
          <tbody>
            {listed.map((row) => (
              <tr key={row.id}>
                <td className="muted">{row.when}</td>
                <td className="name">{row.product}</td>
                <td className="muted">{row.store}</td>
                <td><Pill status={row.kind} /></td>
                <td>{row.before}</td>
                <td>{row.now}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="table-foot">
        <span>{listed.length} {listed.length === 1 ? "alert" : "alerts"}{example ? " · Example" : ""}</span>
      </div>
      <article className="note-card">
        <h3>How alerts work</h3>
        <p>Price: Tiger reads the price next to the product’s add-to-cart button. If a sale price and a higher price are shown together, it says “can’t read”.</p>
        <p>Stock: Tiger records stock only for clear wording such as “in stock”, “out of stock”, “sold out” or “only 3 left”. Anything else is “can’t read” and does not alert.</p>
      </article>
    </section>
  );
}

function Watch({ rows, note, onHide }: { rows: ProductRow[]; note: string | null; onHide: (id: string) => void }) {
  return (
    <section className="block">
      <div className="title-row">
        <h2>Watch list</h2>
      </div>
      <p className="intro">Product pages Tiger checks. Add a product with the red button at the top. Remove a page any time.</p>
      {rows.length === 0 ? <p className="empty">No products watched yet.</p> : null}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Product</th><th>Page link</th><th>How often</th><th>Alert me on</th><th>Status</th><th /></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td className="name">{row.name}</td>
                <td><a href={row.url} target="_blank" rel="noreferrer">{row.path}</a></td>
                <td className="muted">{row.every}</td>
                <td className="muted">{row.alertOn}</td>
                <td><Pill status={row.status === "Price changed" || row.status === "Stock changed" ? "Read" : row.status} /></td>
                <td className="end">
                  {row.live ? (
                    <form action={removeProduct}>
                      <input type="hidden" name="id" value={row.id} />
                      <button type="submit" className="text">Remove</button>
                    </form>
                  ) : (
                    <button type="button" className="text" onClick={() => onHide(row.id)}>Remove</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="table-foot">
        <span>{note ?? `${rows.length} on the watch list`}</span>
      </div>
    </section>
  );
}

function Unread({ rows }: { rows: UnreadRow[] }) {
  return (
    <section className="block">
      <div className="title-row">
        <h2>Can&apos;t read</h2>
      </div>
      <p className="intro">Pages Tiger could not read clearly. It records them and skips them. It never guesses a price or stock.</p>
      {rows.length === 0 ? <p className="empty">No pages Tiger could not read.</p> : null}
      <div className="table-wrap">
        <table>
          <thead><tr><th scope="col">Product</th><th scope="col">Page</th><th scope="col">Why Tiger could not read it</th><th scope="col">Since</th></tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id}>
                <td className="name">{row.product}</td>
                <td className="muted"><a href={row.url} title={row.url} target="_blank" rel="noreferrer">{row.store}</a></td>
                <td>{row.why}</td>
                <td className="muted">{row.since}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <article className="note-card">
        <h3>What happens next</h3>
        <p>Tiger tries each page again at its next check. Nothing here sends an alert. If a page stays unreadable, you can remove it from the watch list.</p>
      </article>
    </section>
  );
}

function Results({ hit }: { hit: NonNullable<ReturnType<typeof searchTiger>> }) {
  return (
    <section className="block">
      <div className="title-row">
        <h2>Results for “{hit.query}”</h2>
      </div>
      <p className="intro">{hit.total} {hit.total === 1 ? "match" : "matches"} in your watched products, reads and alerts.</p>
      <h3 className="group">Watched products</h3>
      <SimpleTable
        heads={["Product", "Page link", "Stock"]}
        rows={hit.products.map((row) => [row.name, row.path, row.stock])}
        empty="No watched products match."
      />
      <h3 className="group">Reads</h3>
      <SimpleTable
        heads={["When", "Product", "Price", "Stock"]}
        rows={hit.reads.map((row: ReadRow) => [row.when, row.product, row.price, row.stock])}
        empty="No reads match."
        priceCol={2}
      />
      <h3 className="group">Alerts</h3>
      <SimpleTable
        heads={["When", "Product", "What changed"]}
        rows={hit.alerts.map((row) => [row.when, row.product, row.change])}
        empty="No alerts match."
      />
    </section>
  );
}

function SimpleTable({ heads, rows, empty, priceCol }: { heads: string[]; rows: string[][]; empty: string; priceCol?: number }) {
  if (rows.length === 0) return <p className="fine">{empty}</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{heads.map((head) => <th key={head}>{head}</th>)}</tr></thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, cellIndex) => <td key={cellIndex} className={cellIndex === priceCol ? "price" : cellIndex === 0 && priceCol === undefined ? "name" : ""}>{cell}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function AddProduct({ onClose }: { onClose: () => void }) {
  const [priceOn, setPriceOn] = useState(true);
  const [stockOn, setStockOn] = useState(true);
  return (
    <div className="scrim" role="presentation" onClick={onClose}>
      <div className="popup narrow" role="dialog" aria-modal="true" aria-labelledby="add-title" onClick={(event) => event.stopPropagation()}>
        <form action={addProduct} className="add-form">
          <div className="popup-head">
            <div>
              <h2 id="add-title">Add a product</h2>
              <p className="sub">Paste the link to a public product page. Tiger reads the price and stock next to that product’s add-to-cart button.</p>
            </div>
            <button type="button" className="text" onClick={onClose}>Close</button>
          </div>
          <label>
            Product page link
            <input name="url" type="url" required placeholder="https://store.example/product" autoComplete="off" />
            <span className="fine">Public pages only. Tiger never logs in.</span>
          </label>
          <label>
            Name (optional)
            <input name="label" type="text" placeholder="Product name" maxLength={200} autoComplete="off" />
          </label>
          <label>
            How often
            <select name="every" defaultValue="6h">
              {EVERY_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
            </select>
          </label>
          <fieldset>
            <legend>Alert me when</legend>
            <label className="check">
              <input name="price" type="checkbox" checked={priceOn} onChange={(event) => setPriceOn(event.target.checked)} />
              The price changes
            </label>
            <label className="check">
              <input name="stock" type="checkbox" checked={stockOn} onChange={(event) => setStockOn(event.target.checked)} />
              The stock changes
            </label>
            <span className="fine">Pages Tiger can’t read are listed under Can’t read. They never send an alert.</span>
          </fieldset>
          <div className="actions">
            <button type="button" className="line small" onClick={onClose}>Cancel</button>
            <button type="submit" className="primary">Start watching</button>
          </div>
        </form>
      </div>
    </div>
  );
}
