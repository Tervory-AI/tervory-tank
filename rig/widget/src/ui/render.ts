import type { GraphResponse, Price, Product, Setup, SetupPart } from "../api/types";
import { detailOf, formatPrice, isSample, matchNote, summaryOf, whyLines } from "../api/format";
import type { Theme } from "../theme/themes";

export type Screen = "home" | "results" | "missing" | "setup" | "explore";

export type QuoteView = {
  kind: "product" | "setup";
  title: string;
  totalLabel: string;
  name: string;
  email: string;
  error: string | null;
  requestId: string | null;
};

export type View = {
  theme: Theme;
  query: string;
  screen: Screen;
  results: Product[];
  selectedId: string | null;
  product: Product | null;
  setups: Setup[];
  activeTier: string | null;
  graph: GraphResponse | null;
  expanded: string[];
  swap: { role: string; tier: string; options: Product[] } | null;
  askQuestion: string;
  askAnswer: string | null;
  askCites: string;
  linkUrl: string;
  linkNote: string;
  linkRequestId: string | null;
  linkError: string | null;
  quote: QuoteView | null;
  message: string | null;
  customizedTiers: string[];
};

export function renderView(view: View): string {
  if (view.screen === "explore") return explore(view);
  return `<div class="shell">${light(view)}</div>${quoteDialog(view)}`;
}

function light(view: View): string {
  const body =
    view.screen === "home"
      ? home(view)
      : view.screen === "results"
        ? results(view)
        : view.screen === "missing"
          ? missing(view)
          : setupScreen(view);
  return `${header(view, false)}${title(view)}${searchForm(view, "q")}${message(view)}${body}`;
}

function header(view: View, dark: boolean): string {
  const copy = view.theme.copy;
  return `<header class="${dark ? "explore-header" : "header"}">
    ${dark ? "" : `<span class="dash" aria-hidden="true"></span>`}
    ${dark ? "" : `<p class="eyebrow">${esc(copy.eyebrow)}</p>`}
    <p class="${dark ? "explore-mark" : "mark"}">${esc(copy.mark)}</p>
  </header>`;
}

function title(view: View): string {
  return `<h1 class="title">${esc(view.theme.copy.title)}</h1>`;
}

function searchForm(view: View, id: string): string {
  const copy = view.theme.copy;
  return `<form class="search" role="search">
    <label class="sr" for="${id}">${esc(copy.search)}</label>
    <span class="search-icon" aria-hidden="true">⌕</span>
    <input id="${id}" type="search" name="q" autocomplete="off" enterkeyhint="search" placeholder="${esc(copy.placeholder)}" value="${esc(view.query)}">
    <button class="btn btn-accent" type="submit">${esc(copy.search)}</button>
  </form>`;
}

function message(view: View): string {
  return view.message ? `<p class="status" role="status">${esc(view.message)}</p>` : "";
}

function home(view: View): string {
  const copy = view.theme.copy;
  const chips = copy.popular
    .map(
      (name) =>
        `<button type="button" class="chip" data-action="popular" data-q="${esc(name)}">${esc(name)}</button>`,
    )
    .join("");
  const steps = copy.steps
    .map(
      (step, index) => `<section class="step">
        <span class="step-no">${String(index + 1).padStart(2, "0")}</span>
        <h2>${esc(step.title)}</h2>
        <p>${esc(step.body)}</p>
      </section>`,
    )
    .join("");
  return `<div class="popular"><span class="popular-label">${esc(copy.popularLabel)}</span>${chips}</div>
    <div class="steps">${steps}</div>`;
}

function results(view: View): string {
  const copy = view.theme.copy;
  const noun = view.results.length === 1 ? copy.resultWord : copy.resultsWord;
  const cards = view.results.map((product) => resultCard(view, product)).join("");
  return `<div class="meta-row">
      <strong>${view.results.length} ${esc(noun)} ${esc(copy.forWord)} “${esc(view.query)}”</strong>
      ${sampleBadge(copy.sampleLabel)}
    </div>
    <div class="cards">${cards}</div>`;
}

function resultCard(view: View, product: Product): string {
  const copy = view.theme.copy;
  const selected = view.selectedId === product.id;
  const primary = selected
    ? `<button type="button" class="btn btn-selected" data-action="complete" data-id="${esc(product.id)}">${esc(copy.selected)} ✓</button>`
    : `<button type="button" class="btn btn-ghost" data-action="complete" data-id="${esc(product.id)}">${esc(copy.complete)}</button>`;
  return `<article class="card${selected ? " selected" : ""}">
    ${photo(product, view, "photo-lg")}
    <div class="brand-row"><p class="brand">${esc(product.brand)}</p>${isSample(product) ? sampleBadge(copy.sampleLabel) : ""}</div>
    <h2 class="card-name">${esc(product.name)}</h2>
    <p class="summary">${esc(summaryOf(product))}</p>
    ${priceRow(copy.indicative, product.price, "")}
    <div class="actions">
      ${primary}
      <button type="button" class="btn btn-ghost" data-action="quote-product" data-id="${esc(product.id)}">${esc(copy.quoteOnly)}</button>
    </div>
    <button type="button" class="text-btn" data-action="explore" data-id="${esc(product.id)}">${esc(copy.explore)}</button>
  </article>`;
}

function missing(view: View): string {
  const copy = view.theme.copy;
  const ack = view.linkRequestId
    ? `<p class="ack" role="status">${esc(copy.quoteSent)} ${esc(view.linkRequestId)}.</p>`
    : "";
  const error = view.linkError ? `<p class="status" role="status">${esc(view.linkError)}</p>` : "";
  return `<section class="missing">
    <h2>${esc(copy.missingTitle)}</h2>
    <p class="missing-copy">${esc(copy.missingBody)}</p>
    <form class="link-form">
      <div class="link-row">
        <label class="sr" for="link-url">${esc(copy.linkLabel)}</label>
        <input class="link-url" id="link-url" type="url" inputmode="url" placeholder="${esc(copy.linkPlaceholder)}" value="${esc(view.linkUrl)}">
        <button class="btn btn-accent" type="submit">${esc(copy.requestQuote)}</button>
      </div>
      <label class="note"><span>${esc(copy.noteLabel)}</span>
        <textarea class="field" id="link-note" rows="2" placeholder="${esc(copy.notePlaceholder)}">${esc(view.linkNote)}</textarea>
      </label>
    </form>
    ${error}${ack}
  </section>`;
}

function setupScreen(view: View): string {
  const copy = view.theme.copy;
  const product = view.product;
  if (!product) return "";
  const note = matchNote(product);
  const cards = view.setups.map((setup, index) => setupCard(view, setup, index)).join("");
  const empty = view.setups.length === 0 ? `<p class="fine">${esc(copy.noSetups)}</p>` : "";
  return `<section class="chosen">
      ${photo(product, view, "photo-sm")}
      <div class="chosen-copy">
        <p class="you-chose">${esc(copy.youChose)}</p>
        <h2>${esc(product.name)} · ${esc(detailOf(product))}</h2>
        ${note ? `<p class="chosen-note">${esc(note)}</p>` : ""}
      </div>
      <div class="chosen-side">
        <button type="button" class="btn btn-ghost" data-action="quote-product" data-id="${esc(product.id)}">${esc(copy.quoteOnly)}</button>
        <button type="button" class="btn btn-ghost" data-action="explore" data-id="${esc(product.id)}">${esc(copy.explore)}</button>
        ${isSample(product) ? sampleBadge(copy.sampleLabel) : ""}
      </div>
    </section>
    ${
      view.setups.length
        ? `<div class="kicker-row"><span class="kicker-bar" aria-hidden="true"></span><h2 class="kicker">${esc(copy.setupKicker)} — ${view.setups.length} ${esc(copy.optionsWord)}</h2></div>`
        : ""
    }
    <div class="setups">${cards}</div>
    ${empty}
    ${view.setups.length ? `<p class="fine">${esc(copy.finePrint)}</p>` : ""}`;
}

function setupCard(view: View, setup: Setup, index: number): string {
  const copy = view.theme.copy;
  const featured = Boolean(setup.badge);
  const lines = whyLines(setup.why);
  const customized = view.customizedTiers.includes(setup.tier);
  const fit = customized ? copy.swappedNote : lines[0] ?? "";
  const parts = setup.parts
    .map((part) => partRow(view, setup, part))
    .join("");
  return `<article class="setup${featured ? " featured" : ""}">
    <div class="setup-head">
      <span class="setup-no">${String(index + 1).padStart(2, "0")}</span>
      <h3 class="setup-name">${esc(setup.tier)}</h3>
      ${setup.badge ? `<span class="badge-hot">${esc(setup.badge)}</span>` : ""}
      ${setup.parts.some((part) => isSample(part.product)) ? sampleBadge(copy.sampleLabel) : ""}
    </div>
    <p class="label">${esc(setup.label)}</p>
    ${parts}
    ${fit ? `<p class="fit-line">${esc(fit)}</p>` : ""}
    ${priceRow(copy.setupIndicative, setup.total, "price-lg")}
    <button type="button" class="btn btn-accent quote-wide" data-action="quote-setup" data-tier="${esc(setup.tier)}">${esc(copy.quoteSetup)} →</button>
  </article>`;
}

function partRow(view: View, setup: Setup, part: SetupPart): string {
  const copy = view.theme.copy;
  const host = part.product.id === view.selectedId;
  const open = view.swap?.role === part.role && view.swap.tier === setup.tier;
  const options = open
    ? `<div class="options">${
        view.swap?.options.length
          ? view.swap.options
              .map(
                (option) =>
                  `<button type="button" class="option" data-action="pick-swap" data-tier="${esc(setup.tier)}" data-id="${esc(option.id)}">${esc(option.name)}</button>`,
              )
              .join("")
          : `<p class="fit-line">${esc(copy.noSwap)}</p>`
      }</div>`
    : "";
  return `<div class="part-block">
    <div class="part">
      ${photo(part.product, view, "photo-xs")}
      <div class="part-copy">
        <span class="role">${esc(part.role)}</span>
        <span class="part-name">${esc(part.product.name)}</span>
        ${isSample(part.product) ? sampleBadge(copy.sampleLabel) : ""}
      </div>
      ${
        host
          ? ""
          : `<button type="button" class="swap-btn" data-action="swap" data-tier="${esc(setup.tier)}" data-role="${esc(part.role)}" aria-expanded="${open ? "true" : "false"}">${esc(copy.swap)} ⇄</button>`
      }
    </div>
    ${options}
  </div>`;
}

function explore(view: View): string {
  const copy = view.theme.copy;
  const graph = view.graph;
  const product = graph?.centre ?? view.product;
  const setup = activeSetup(view);
  const branches = graph?.branches ?? [];
  const branchRows = branches
    .map((branch) => {
      const on = branch.products.some((item) => setup?.parts.some((part) => part.product.id === item.id));
      const expanded = view.expanded.includes(branch.category);
      const chips = expanded
        ? branch.products
            .map((item) => {
              const selected = setup?.parts.some((part) => part.product.id === item.id) ?? false;
              return `<button type="button" class="g-chip${selected ? " on" : ""}" data-action="pick-graph" data-id="${esc(item.id)}">
                <span class="swatch" aria-hidden="true"></span>
                <span class="g-copy">
                  <span class="g-name">${esc(item.name)}</span>
                  <span class="g-meta">${esc(formatPrice(item.price))} · ${esc(copy.fits)} ✓${isSample(item) ? ` · ${esc(copy.sampleLabel)}` : ""}</span>
                </span>
              </button>`;
            })
            .join("")
        : "";
      const more = branch.count - branch.products.length;
      const moreLine = expanded && more > 0 ? `<p class="more">+ ${more} ${esc(copy.moreWord)} ${esc(branch.category.toLowerCase())}</p>` : "";
      return `<div class="branch-row">
        <button type="button" class="branch${on ? " on" : ""}" data-action="branch" data-category="${esc(branch.category)}" aria-expanded="${expanded ? "true" : "false"}">
          <span class="count">${branch.count}</span>
          <span class="cat">${esc(branch.category)}</span>
        </button>
        <div class="products">${chips}${moreLine}</div>
      </div>`;
    })
    .join("");
  const summary = product ? summaryOf(product) : "";
  const centre = product
    ? `<div class="centre">
        <div class="orb-wrap">
          <span class="orb-label">${esc(copy.youChose)}</span>
          <span class="orb" aria-hidden="true"></span>
        </div>
        <h2>${esc(product.name)}</h2>
        <p>${esc([summary, `${copy.indicative} ${formatPrice(product.price)}`].filter(Boolean).join(" · "))}</p>
      </div>`
    : "";
  return `<div class="shell shell-explore"><div class="explore">
    <header class="explore-header">
      <button type="button" class="back" data-action="back">${esc(copy.back)}</button>
      <h1>${esc(copy.title)}</h1>
      <form class="explore-search" role="search">
        <label class="sr" for="q">${esc(copy.search)}</label>
        <span aria-hidden="true">⌕</span>
        <input id="q" type="search" name="q" autocomplete="off" value="${esc(view.query)}" placeholder="${esc(copy.placeholder)}">
      </form>
      <p class="explore-mark">${esc(copy.mark)}</p>
    </header>
    ${message(view)}
    <div class="explore-grid">
      ${centre}
      <div class="graph">${branchRows}</div>
      <div class="side">${panel(view, setup)}${askBox(view)}</div>
    </div>
    ${sampleBadge(copy.sampleLabel, "sample sample-float")}
  </div></div>${quoteDialog(view)}`;
}

function panel(view: View, setup: Setup | null): string {
  const copy = view.theme.copy;
  if (!setup) return `<aside class="panel"><p class="panel-body">${esc(copy.noSetups)}</p></aside>`;
  const customized = view.customizedTiers.includes(setup.tier);
  const lines = whyLines(setup.why);
  const body = customized ? copy.swappedNote : lines[1] ?? lines[0] ?? setup.label;
  const why = customized ? copy.swappedNote : lines[2] ?? lines[1] ?? lines[0] ?? setup.label;
  const names = setup.parts.map((part) => part.product.name).join(" + ");
  const tiers = view.setups
    .map((item) => {
      const on = item.tier === setup.tier;
      return `<button type="button" class="tier${on ? " on" : ""}" data-action="tier" data-tier="${esc(item.tier)}" aria-pressed="${on ? "true" : "false"}">${esc(labelOf(item))}</button>`;
    })
    .join("");
  const noun = setup.parts.length === 1 ? copy.partWord : copy.partsWord;
  return `<aside class="panel">
    <p class="panel-kicker">${esc(copy.yourSetup)} · ${esc(setup.tier)}</p>
    <h2>${esc(names)}</h2>
    <p class="panel-body">${esc(body)}</p>
    <div class="stats">
      <div class="stat"><strong>${setup.parts.length}</strong><span>${esc(noun)}, ${esc(copy.partsFit)}</span></div>
      <div class="stat"><strong>${esc(formatPrice(setup.total))}</strong><span>${esc(copy.graphIndicative)}</span></div>
    </div>
    <div class="tier-row">${tiers}</div>
    <div class="why"><strong>✦ ${esc(copy.whyLabel)}</strong><p>${esc(why)}</p></div>
    <button type="button" class="btn btn-accent quote-wide" data-action="quote-setup" data-tier="${esc(setup.tier)}">${esc(copy.quoteSetup)} →</button>
  </aside>`;
}

function askBox(view: View): string {
  const copy = view.theme.copy;
  const answer = view.askAnswer
    ? `<div class="answer" role="status"><p>${esc(view.askAnswer)}</p>${view.askCites ? `<span>${esc(view.askCites)}</span>` : ""}</div>`
    : "";
  return `${answer}<form class="ask">
    <label class="sr" for="ask-q">${esc(copy.ask)}</label>
    <input id="ask-q" type="text" name="question" placeholder="${esc(copy.askPlaceholder)}" value="${esc(view.askQuestion)}">
    <button class="ask-go" type="submit" aria-label="${esc(copy.ask)}">→</button>
  </form>`;
}

function quoteDialog(view: View): string {
  const quote = view.quote;
  if (!quote) return "";
  const copy = view.theme.copy;
  if (quote.requestId) {
    return `<div class="backdrop">
      <div class="quote" role="dialog" aria-modal="true" aria-labelledby="quote-title">
        <h2 id="quote-title">${esc(copy.quoteTitle)}</h2>
        <p class="ack" role="status">${esc(copy.quoteSent)} ${esc(quote.requestId)}.</p>
        ${quote.totalLabel ? `<p class="summary">${esc(quote.totalLabel)}</p>` : ""}
        <button type="button" class="btn btn-accent" data-action="close-quote">${esc(copy.close)}</button>
      </div>
    </div>`;
  }
  return `<div class="backdrop">
    <form class="quote" role="dialog" aria-modal="true" aria-labelledby="quote-title">
      <h2 id="quote-title">${esc(copy.quoteTitle)}</h2>
      <p>${esc(quote.title)}</p>
      ${quote.totalLabel ? `<p class="price-row"><span class="price-cap">${esc(view.theme.copy.indicative)}</span><span class="price">${esc(quote.totalLabel)}</span></p>` : ""}
      <label>${esc(copy.quoteName)}
        <input class="field" id="quote-name" name="name" autocomplete="name" required value="${esc(quote.name)}">
      </label>
      <label>${esc(copy.quoteEmail)}
        <input class="field" id="quote-email" name="email" type="email" autocomplete="email" required value="${esc(quote.email)}">
      </label>
      ${quote.error ? `<p class="status" role="status">${esc(quote.error)}</p>` : ""}
      <button class="btn btn-accent" type="submit">${esc(copy.quoteSend)}</button>
      <button type="button" class="text-btn" data-action="close-quote">${esc(copy.close)}</button>
    </form>
  </div>`;
}

function activeSetup(view: View): Setup | null {
  return view.setups.find((setup) => setup.tier === view.activeTier) ?? view.setups[0] ?? null;
}

function labelOf(setup: Setup): string {
  return setup.tier.charAt(0).toUpperCase() + setup.tier.slice(1);
}

function priceRow(caption: string, price: Price, priceClass: string): string {
  return `<div class="price-row"><span class="price-cap">${esc(caption)}</span><span class="price ${priceClass}">${esc(formatPrice(price))}</span></div>`;
}

function photo(product: Product, view: View, size: string): string {
  const src = safeImage(product.image);
  const label = view.theme.copy.photoLabel;
  const inner = src ? `<img src="${esc(src)}" alt="">` : size === "photo-lg" ? `<span>${esc(label)}</span>` : "";
  return `<div class="photo ${size}" aria-hidden="true">${inner}</div>`;
}

function sampleBadge(label: string, className = "sample"): string {
  return `<span class="${className}">${esc(label)}</span>`;
}

function safeImage(src: string): string {
  if (/^https?:\/\//i.test(src) || src.startsWith("data:image/")) return src;
  return "";
}

function esc(value: string): string {
  return value.replace(/[&<>"']/g, (char) => {
    switch (char) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case '"':
        return "&quot;";
      default:
        return "&#39;";
    }
  });
}
