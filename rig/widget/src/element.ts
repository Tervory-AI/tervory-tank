import { RigClient } from "./api/client";
import { indicativeTotal, formatPrice } from "./api/format";
import { RigError } from "./api/types";
import type { GraphResponse, Product, Setup } from "./api/types";
import { resolveTheme, type Theme } from "./theme/themes";
import { renderView, type QuoteView, type Screen, type View } from "./ui/render";
import { styles } from "./ui/styles";

const FONT_HREF =
  "https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600&family=Inter:wght@400;500;600&family=Newsreader:opsz,wght@6..72,600&family=Source+Sans+3:wght@400;500;600&display=swap";

type QuoteTarget = { kind: "product"; productId: string } | { kind: "setup"; tier: string };

export class TervoryRig extends HTMLElement {
  static get observedAttributes(): string[] {
    return ["api-base", "rig-key", "theme"];
  }

  private client = new RigClient({ apiBase: "mock", key: "" });
  private themeOverride: Theme | null = null;
  private root: HTMLElement | null = null;
  private searchTimer = 0;
  private loadGen = 0;
  private focusAfter: string | null = null;

  private query = "";
  private screen: Screen = "home";
  private results: Product[] = [];
  private selectedId: string | null = null;
  private product: Product | null = null;
  private setups: Setup[] = [];
  private activeTier: string | null = null;
  private graph: GraphResponse | null = null;
  private expanded: string[] = [];
  private swap: View["swap"] = null;
  private askQuestion = "";
  private askAnswer: string | null = null;
  private askCites = "";
  private linkUrl = "";
  private linkNote = "";
  private linkRequestId: string | null = null;
  private linkError: string | null = null;
  private quote: QuoteView | null = null;
  private quoteTarget: QuoteTarget | null = null;
  private message: string | null = null;
  private customizedTiers: string[] = [];

  set themeData(theme: Theme) {
    this.themeOverride = theme;
    if (this.shadowRoot) {
      this.applyTheme();
      this.render();
    }
  }

  connectedCallback(): void {
    if (this.shadowRoot) return;
    const shadow = this.attachShadow({ mode: "open" });
    const style = document.createElement("style");
    style.textContent = styles;
    shadow.append(style);
    this.root = document.createElement("div");
    shadow.append(this.root);
    shadow.addEventListener("click", (event) => this.onClick(event));
    shadow.addEventListener("submit", (event) => this.onSubmit(event));
    shadow.addEventListener("input", (event) => this.onInput(event));
    shadow.addEventListener("keydown", (event) => this.onKey(event));
    ensureFonts();
    this.syncClient();
    this.applyTheme();
    this.render();
  }

  disconnectedCallback(): void {
    window.clearTimeout(this.searchTimer);
  }

  attributeChangedCallback(name: string): void {
    if (!this.shadowRoot) return;
    if (name === "api-base" || name === "rig-key") this.syncClient();
    if (name === "theme") this.themeOverride = null;
    this.applyTheme();
    this.render();
  }

  private syncClient(): void {
    this.client = new RigClient({
      apiBase: this.getAttribute("api-base") || "mock",
      key: this.getAttribute("rig-key") ?? "",
    });
  }

  private currentTheme(): Theme {
    return this.themeOverride ?? resolveTheme(this.getAttribute("theme"));
  }

  private applyTheme(): void {
    const theme = this.currentTheme();
    const vars: Record<string, string> = {
      "--rig-canvas": theme.colors.canvas,
      "--rig-ink": theme.colors.ink,
      "--rig-accent": theme.colors.accent,
      "--rig-muted": theme.colors.muted,
      "--rig-faint": theme.colors.faint,
      "--rig-line": theme.colors.line,
      "--rig-line-strong": theme.colors.lineStrong,
      "--rig-card": theme.colors.card,
      "--rig-badge": theme.colors.badge,
      "--rig-on-accent": theme.colors.onAccent,
      "--rig-featured": theme.colors.featured,
      "--rig-featured-text": theme.colors.featuredText,
      "--rig-featured-muted": theme.colors.featuredMuted,
      "--rig-font-heading": theme.fonts.heading,
      "--rig-font-body": theme.fonts.body,
      "--rig-radius": theme.radius,
      "--rig-radius-graph": theme.radiusGraph,
      "--rig-graph-canvas": theme.graph.canvas,
      "--rig-graph-raised": theme.graph.raised,
      "--rig-graph-text": theme.graph.text,
      "--rig-graph-muted": theme.graph.muted,
      "--rig-graph-line": theme.graph.line,
      "--rig-graph-chip": theme.graph.chip,
      "--rig-graph-chip-on": theme.graph.chipOn,
      "--rig-graph-glow": theme.graph.glow,
    };
    for (const [key, value] of Object.entries(vars)) this.style.setProperty(key, value);
  }

  private view(): View {
    return {
      theme: this.currentTheme(),
      query: this.query,
      screen: this.screen,
      results: this.results,
      selectedId: this.selectedId,
      product: this.product,
      setups: this.setups,
      activeTier: this.activeTier,
      graph: this.graph,
      expanded: this.expanded,
      swap: this.swap,
      askQuestion: this.askQuestion,
      askAnswer: this.askAnswer,
      askCites: this.askCites,
      linkUrl: this.linkUrl,
      linkNote: this.linkNote,
      linkRequestId: this.linkRequestId,
      linkError: this.linkError,
      quote: this.quote,
      message: this.message,
      customizedTiers: this.customizedTiers,
    };
  }

  private render(): void {
    if (!this.root) return;
    const previous = this.captureFocus();
    this.classList.toggle("is-explore", this.screen === "explore");
    this.root.innerHTML = renderView(this.view());
    const prefer = this.focusAfter;
    this.focusAfter = null;
    this.restoreFocus(prefer ?? previous?.id ?? null, prefer ? null : previous);
  }

  private captureFocus(): { id: string; start: number | null; end: number | null } | null {
    const active = this.shadowRoot?.activeElement;
    if (!(active instanceof HTMLElement) || !active.id) return null;
    if (active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement) {
      return { id: active.id, start: active.selectionStart, end: active.selectionEnd };
    }
    return { id: active.id, start: null, end: null };
  }

  private restoreFocus(
    id: string | null,
    previous: { id: string; start: number | null; end: number | null } | null,
  ): void {
    if (!id || !this.root) return;
    const next = this.root.querySelector(`#${CSS.escape(id)}`);
    if (!(next instanceof HTMLElement)) return;
    next.focus();
    if (
      previous &&
      previous.id === id &&
      (next instanceof HTMLInputElement || next instanceof HTMLTextAreaElement) &&
      previous.start !== null &&
      previous.end !== null
    ) {
      next.setSelectionRange(previous.start, previous.end);
    }
  }

  private onClick(event: Event): void {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const action = target.closest("[data-action]");
    if (!(action instanceof HTMLElement)) return;
    const id = action.dataset.id ?? "";
    const tier = action.dataset.tier ?? "";
    switch (action.dataset.action) {
      case "popular":
        this.query = action.dataset.q ?? "";
        void this.searchNow();
        break;
      case "complete":
        void this.openSetup(id);
        break;
      case "explore":
        void this.openExplore(id);
        break;
      case "quote-product":
        this.openQuoteProduct(id);
        break;
      case "quote-setup":
        this.openQuoteSetup(tier);
        break;
      case "swap":
        void this.openSwap(tier, action.dataset.role ?? "");
        break;
      case "pick-swap":
        this.pickSwap(tier, id);
        break;
      case "tier":
        this.activeTier = tier;
        this.swap = null;
        this.render();
        break;
      case "branch":
        this.toggleBranch(action.dataset.category ?? "");
        break;
      case "pick-graph":
        void this.pickGraph(id);
        break;
      case "back":
        this.goBack();
        break;
      case "close-quote":
        this.quote = null;
        this.quoteTarget = null;
        this.render();
        break;
      default:
        break;
    }
  }

  private onSubmit(event: Event): void {
    event.preventDefault();
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (form.classList.contains("link-form")) {
      void this.submitLink();
      return;
    }
    if (form.classList.contains("ask")) {
      void this.submitAsk();
      return;
    }
    if (form.classList.contains("quote")) {
      void this.submitQuote(form);
      return;
    }
    void this.searchNow();
  }

  private onInput(event: Event): void {
    const target = event.target;
    if (!(target instanceof HTMLInputElement || target instanceof HTMLTextAreaElement)) return;
    if (target.id === "q") {
      this.query = target.value;
      this.scheduleSearch();
    } else if (target.id === "link-url") {
      this.linkUrl = target.value;
    } else if (target.id === "link-note") {
      this.linkNote = target.value;
    } else if (target.id === "ask-q") {
      this.askQuestion = target.value;
    } else if (target.id === "quote-name" && this.quote) {
      this.quote = { ...this.quote, name: target.value };
    } else if (target.id === "quote-email" && this.quote) {
      this.quote = { ...this.quote, email: target.value };
    }
  }

  private onKey(event: Event): void {
    if (!(event instanceof KeyboardEvent) || event.key !== "Escape") return;
    if (this.quote) {
      this.quote = null;
      this.quoteTarget = null;
      this.render();
    } else if (this.swap) {
      this.swap = null;
      this.render();
    }
  }

  private scheduleSearch(): void {
    window.clearTimeout(this.searchTimer);
    if (!this.query.trim()) {
      this.loadGen += 1;
      this.screen = "home";
      this.results = [];
      this.message = null;
      this.linkError = null;
      this.render();
      return;
    }
    this.searchTimer = window.setTimeout(() => void this.searchNow(), 250);
  }

  private async searchNow(): Promise<void> {
    window.clearTimeout(this.searchTimer);
    const query = this.query.trim();
    if (!query) {
      this.screen = "home";
      this.results = [];
      this.message = null;
      this.render();
      return;
    }
    const gen = ++this.loadGen;
    this.message = this.currentTheme().copy.loading;
    this.render();
    try {
      const response = await this.client.search(query, 12);
      if (gen !== this.loadGen) return;
      this.results = response.results;
      this.screen = response.results.length ? "results" : "missing";
      this.swap = null;
      this.quote = null;
      this.message = null;
      if (this.screen === "missing") {
        this.linkUrl = "";
        this.linkNote = "";
        this.linkRequestId = null;
        this.linkError = null;
      }
    } catch (error) {
      if (gen !== this.loadGen) return;
      this.message = errorText(error);
    }
    this.render();
  }

  private async openSetup(id: string): Promise<void> {
    const known = this.findProduct(id);
    this.selectedId = id;
    this.product = known;
    this.screen = "setup";
    this.swap = null;
    this.quote = null;
    this.graph = null;
    this.message = this.currentTheme().copy.loading;
    this.render();
    const gen = ++this.loadGen;
    try {
      const [detail, built] = await Promise.all([this.client.product(id), this.client.setups(id)]);
      if (gen !== this.loadGen) return;
      this.product = detail;
      this.setups = built.setups;
      this.activeTier = built.setups.find((setup) => setup.badge)?.tier ?? built.setups[0]?.tier ?? null;
      this.customizedTiers = [];
      this.message = null;
    } catch (error) {
      if (gen !== this.loadGen) return;
      this.message = errorText(error);
    }
    this.render();
  }

  private async openExplore(id: string): Promise<void> {
    this.selectedId = id;
    this.screen = "explore";
    this.swap = null;
    this.quote = null;
    this.askAnswer = null;
    this.askCites = "";
    this.message = this.currentTheme().copy.loading;
    this.render();
    const gen = ++this.loadGen;
    try {
      const [graph, built] = await Promise.all([this.client.graph(id), this.client.setups(id)]);
      if (gen !== this.loadGen) return;
      this.graph = graph;
      this.product = graph.centre;
      this.setups = built.setups;
      this.customizedTiers = [];
      this.activeTier = built.setups.find((setup) => setup.badge)?.tier ?? built.setups[0]?.tier ?? null;
      const active = this.setups.find((setup) => setup.tier === this.activeTier) ?? this.setups[0];
      const used = new Set(active?.parts.map((part) => part.product.id) ?? []);
      this.expanded = graph.branches
        .filter((branch) => branch.products.some((item) => used.has(item.id)))
        .map((branch) => branch.category);
      this.message = null;
    } catch (error) {
      if (gen !== this.loadGen) return;
      this.message = errorText(error);
    }
    this.render();
  }

  private async openSwap(tier: string, role: string): Promise<void> {
    if (this.swap?.tier === tier && this.swap.role === role) {
      this.swap = null;
      this.render();
      return;
    }
    const setup = this.setups.find((item) => item.tier === tier);
    if (!setup) return;
    this.message = this.currentTheme().copy.loading;
    this.render();
    try {
      const response = await this.client.swap(setup, role);
      this.swap = { tier, role, options: response.options };
      this.message = null;
    } catch (error) {
      this.message = errorText(error);
    }
    this.render();
  }

  private pickSwap(tier: string, id: string): void {
    const setup = this.setups.find((item) => item.tier === tier);
    const option = this.swap?.options.find((item) => item.id === id);
    if (!setup || !option || this.swap?.tier !== tier) return;
    const part = setup.parts.find((item) => item.role === this.swap?.role);
    if (!part) return;
    part.product = option;
    setup.total = indicativeTotal(setup.parts, setup.total);
    if (!this.customizedTiers.includes(tier)) this.customizedTiers.push(tier);
    this.swap = null;
    this.render();
  }

  private async pickGraph(id: string): Promise<void> {
    const setup = this.setups.find((item) => item.tier === this.activeTier) ?? this.setups[0];
    const product = this.findProduct(id);
    if (!setup || !product || product.id === this.selectedId) return;
    if (setup.parts.some((part) => part.product.id === product.id)) return;
    const part = setup.parts.find((item) => item.product.category === product.category);
    if (!part) return;
    try {
      const response = await this.client.swap(setup, part.role);
      const choice = response.options.find((item) => item.id === product.id);
      if (!choice) {
        this.message = "That part is not an alternative that fits.";
        this.render();
        return;
      }
      part.product = choice;
      setup.total = indicativeTotal(setup.parts, setup.total);
      if (!this.customizedTiers.includes(setup.tier)) this.customizedTiers.push(setup.tier);
      this.message = null;
    } catch (error) {
      this.message = errorText(error);
    }
    this.render();
  }

  private toggleBranch(category: string): void {
    this.expanded = this.expanded.includes(category)
      ? this.expanded.filter((item) => item !== category)
      : [...this.expanded, category];
    this.render();
  }

  private goBack(): void {
    this.screen = this.setups.length && this.selectedId ? "setup" : this.results.length ? "results" : "home";
    this.message = null;
    this.render();
  }

  private openQuoteProduct(id: string): void {
    const product = this.findProduct(id);
    if (!product) return;
    this.quoteTarget = { kind: "product", productId: id };
    this.quote = {
      kind: "product",
      title: product.name,
      totalLabel: formatPrice(product.price),
      name: "",
      email: "",
      error: null,
      requestId: null,
    };
    this.focusAfter = "quote-name";
    this.render();
  }

  private openQuoteSetup(tier: string): void {
    const setup = this.setups.find((item) => item.tier === tier);
    if (!setup) return;
    this.quoteTarget = { kind: "setup", tier };
    this.quote = {
      kind: "setup",
      title: setup.parts.map((part) => part.product.name).join(" + "),
      totalLabel: formatPrice(setup.total),
      name: "",
      email: "",
      error: null,
      requestId: null,
    };
    this.focusAfter = "quote-name";
    this.render();
  }

  private async submitQuote(form: HTMLFormElement): Promise<void> {
    if (!this.quote || !this.quoteTarget) return;
    const data = new FormData(form);
    const name = String(data.get("name") ?? "").trim();
    const email = String(data.get("email") ?? "").trim();
    this.quote = { ...this.quote, name, email, error: null };
    const contact = { name, email };
    const target = this.quoteTarget;
    try {
      const setup = target.kind === "setup" ? this.setups.find((item) => item.tier === target.tier) : undefined;
      if (target.kind === "setup" && !setup) {
        throw new RigError("invalid_quote", "That setup is no longer available.", 400);
      }
      const response =
        target.kind === "product"
          ? await this.client.quote({ contact, product_id: target.productId })
          : await this.client.quote({ contact, setup });
      this.quote = { ...this.quote, requestId: response.request_id };
    } catch (error) {
      this.quote = { ...this.quote, error: errorText(error) };
    }
    this.render();
  }

  private async submitLink(): Promise<void> {
    this.linkError = null;
    try {
      const response = await this.client.linkQuote({ url: this.linkUrl, note: this.linkNote });
      this.linkRequestId = response.request_id;
    } catch (error) {
      this.linkError = errorText(error);
    }
    this.render();
  }

  private async submitAsk(): Promise<void> {
    const productId = this.graph?.centre.id ?? this.selectedId;
    if (!productId) return;
    const setup = this.setups.find((item) => item.tier === this.activeTier) ?? this.setups[0];
    this.message = this.currentTheme().copy.loading;
    this.render();
    try {
      const response = await this.client.ask({
        product_id: productId,
        ...(setup ? { setup } : {}),
        question: this.askQuestion,
      });
      this.askAnswer = response.answer;
      this.askCites = this.citeLabel(response.cites);
      this.message = null;
    } catch (error) {
      this.message = errorText(error);
    }
    this.render();
  }

  private citeLabel(ids: string[]): string {
    const names = new Map<string, string>();
    if (this.graph) {
      names.set(this.graph.centre.id, this.graph.centre.name);
      for (const branch of this.graph.branches) {
        for (const product of branch.products) names.set(product.id, product.name);
      }
    }
    return ids.map((id) => names.get(id) ?? id).join(", ");
  }

  private findProduct(id: string): Product | null {
    if (this.product?.id === id) return this.product;
    const fromResults = this.results.find((item) => item.id === id);
    if (fromResults) return fromResults;
    for (const setup of this.setups) {
      const part = setup.parts.find((item) => item.product.id === id);
      if (part) return part.product;
    }
    if (this.graph) {
      if (this.graph.centre.id === id) return this.graph.centre;
      for (const branch of this.graph.branches) {
        const product = branch.products.find((item) => item.id === id);
        if (product) return product;
      }
    }
    const option = this.swap?.options.find((item) => item.id === id);
    return option ?? null;
  }
}

function errorText(error: unknown): string {
  if (error instanceof RigError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

function ensureFonts(): void {
  if (document.querySelector('link[data-tervory-rig-fonts="true"]')) return;
  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = FONT_HREF;
  link.dataset.tervoryRigFonts = "true";
  document.head.appendChild(link);
}
