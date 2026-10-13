export type ThemeStep = {
  title: string;
  body: string;
};

export type Theme = {
  id: string;
  colors: {
    canvas: string;
    ink: string;
    accent: string;
    muted: string;
    faint: string;
    line: string;
    lineStrong: string;
    card: string;
    badge: string;
    onAccent: string;
    featured: string;
    featuredText: string;
    featuredMuted: string;
  };
  graph: {
    canvas: string;
    raised: string;
    text: string;
    muted: string;
    line: string;
    chip: string;
    chipOn: string;
    glow: string;
  };
  fonts: {
    heading: string;
    body: string;
    href?: string;
  };
  radius: string;
  radiusGraph: string;
  copy: {
    eyebrow: string;
    title: string;
    placeholder: string;
    popularLabel: string;
    popular: string[];
    steps: ThemeStep[];
    setupKicker: string;
    optionsWord: string;
    youChose: string;
    finePrint: string;
    missingTitle: string;
    missingBody: string;
    linkPlaceholder: string;
    linkLabel: string;
    notePlaceholder: string;
    noteLabel: string;
    requestQuote: string;
    quoteSetup: string;
    search: string;
    complete: string;
    quoteOnly: string;
    selected: string;
    explore: string;
    indicative: string;
    setupIndicative: string;
    swap: string;
    noSwap: string;
    back: string;
    askPlaceholder: string;
    ask: string;
    whyLabel: string;
    partsFit: string;
    partWord: string;
    partsWord: string;
    moreWord: string;
    fits: string;
    yourSetup: string;
    quoteTitle: string;
    quoteName: string;
    quoteEmail: string;
    quoteSend: string;
    quoteSent: string;
    graphIndicative: string;
    photoLabel: string;
    loading: string;
    noSetups: string;
    swappedNote: string;
    resultWord: string;
    resultsWord: string;
    forWord: string;
    mark: string;
    close: string;
    sampleLabel: string;
    notAlternative: string;
    errorGeneric: string;
    unavailable: string;
  };
};

export const customNation: Theme = {
  id: "custom-nation",
  colors: {
    canvas: "#f2efe7",
    ink: "#242722",
    accent: "#ad322c",
    muted: "#686b60",
    faint: "#9a9c92",
    line: "#e3dfd4",
    lineStrong: "#d5d0c3",
    card: "#ffffff",
    badge: "#e8e4da",
    onAccent: "#ffffff",
    featured: "#242722",
    featuredText: "#fcfaf4",
    featuredMuted: "#b8baab",
  },
  graph: {
    canvas: "#121510",
    raised: "#1a1d18",
    text: "#fcfaf4",
    muted: "#b8baab",
    line: "rgba(255,255,255,0.12)",
    chip: "#1a1d18",
    chipOn: "#2a1a18",
    glow: "rgba(31,42,34,1)",
  },
  fonts: {
    heading: '"Barlow Condensed", "Arial Narrow", sans-serif',
    body: 'Inter, "Helvetica Neue", sans-serif',
    href: "https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600&family=Inter:wght@400;500;600&display=swap",
  },
  radius: "0px",
  radiusGraph: "8px",
  copy: {
    eyebrow: "Sourced from the USA",
    title: "Find it. We source it.",
    placeholder: "Search a make, model or part — e.g. Staccato, Leupold Mark 5, MDT ACC",
    popularLabel: "Popular:",
    popular: ["Staccato", "Leupold", "Nightforce", "MDT", "TriggerTech", "Proof Research"],
    steps: [
      { title: "Search", body: "Every SKU from our US suppliers, as you type." },
      { title: "Complete your setup", body: "We suggest the parts that fit what you chose." },
      { title: "Request a quote", body: "One indicative price. We confirm and import it for you." },
    ],
    setupKicker: "Complete your setup",
    optionsWord: "options",
    youChose: "You chose",
    finePrint:
      "One indicative total per setup. We confirm stock, permits and the final quotation in your client space. Prices shown are sample data until the US feeds are connected.",
    missingTitle: "Not in our feeds yet? We can still get it.",
    missingBody: "Paste the link to the product on any US store and we will quote it for you.",
    linkPlaceholder: "https://…",
    linkLabel: "Link",
    notePlaceholder: "Anything we should know",
    noteLabel: "Note",
    requestQuote: "Request a quote",
    quoteSetup: "Request a quote for this setup",
    search: "Search",
    complete: "Complete my setup",
    quoteOnly: "Quote this only",
    selected: "Selected",
    explore: "Explore",
    indicative: "Indicative",
    setupIndicative: "Setup, indicative",
    swap: "Swap",
    noSwap: "No other part fits this role.",
    back: "Back",
    askPlaceholder: "Ask a question… “Will this fit a weapon light too?”",
    ask: "Ask",
    whyLabel: "Why this setup",
    partsFit: "all fit",
    partWord: "part",
    partsWord: "parts",
    moreWord: "more",
    fits: "fits",
    yourSetup: "Your setup",
    quoteTitle: "Request a quote",
    quoteName: "Name",
    quoteEmail: "Email",
    quoteSend: "Send request",
    quoteSent: "Request received. Reference",
    graphIndicative: "indicative",
    photoLabel: "Product photo (from feed)",
    loading: "Loading…",
    noSetups: "No setups came back for this product. You can still quote it on its own.",
    swappedNote: "Updated with a part that still fits.",
    resultWord: "result",
    resultsWord: "results",
    forWord: "for",
    mark: "Rig · by Tervory",
    close: "Close",
    sampleLabel: "SAMPLE DATA",
    notAlternative: "That part is not an alternative that fits.",
    errorGeneric: "Something went wrong.",
    unavailable: "That setup is no longer available.",
  },
};

export const neutral: Theme = {
  id: "neutral",
  colors: {
    canvas: "#f4f5f7",
    ink: "#1c1e21",
    accent: "#1d4e89",
    muted: "#5c6370",
    faint: "#8b919a",
    line: "#d5d8de",
    lineStrong: "#c5c9d1",
    card: "#ffffff",
    badge: "#e6e8ec",
    onAccent: "#ffffff",
    featured: "#1c1e21",
    featuredText: "#f7f8fa",
    featuredMuted: "#c5c9d1",
  },
  graph: {
    canvas: "#12141a",
    raised: "#1b1e27",
    text: "#f7f8fa",
    muted: "#c5c9d1",
    line: "rgba(255,255,255,0.14)",
    chip: "#1b1e27",
    chipOn: "#172033",
    glow: "rgba(29,78,137,0.35)",
  },
  fonts: {
    heading: "Newsreader, Georgia, serif",
    body: '"Source Sans 3", "Helvetica Neue", sans-serif',
    href: "https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,600&family=Source+Sans+3:wght@400;500;600&display=swap",
  },
  radius: "10px",
  radiusGraph: "16px",
  copy: {
    eyebrow: "From specialist suppliers",
    title: "Find it. Complete the kit.",
    placeholder: "Search a make, model or part — e.g. Sony, 70-200, Peak Design",
    popularLabel: "Popular:",
    popular: ["Sony", "Canon", "Nikon", "Peak Design", "SmallRig", "Godox"],
    steps: [
      { title: "Search", body: "Every item from the suppliers, as you type." },
      { title: "Complete your setup", body: "Parts that fit what you chose." },
      { title: "Request a quote", body: "One indicative price. The shop confirms it." },
    ],
    setupKicker: "Complete your setup",
    optionsWord: "options",
    youChose: "You chose",
    finePrint: "One indicative total per setup. The shop confirms stock and the final quotation. Prices shown are sample data.",
    missingTitle: "Not in the catalogue yet? We can still quote it.",
    missingBody: "Paste a link to the product and a short note, and the shop will quote it.",
    linkPlaceholder: "https://…",
    linkLabel: "Link",
    notePlaceholder: "A short note",
    noteLabel: "Note",
    requestQuote: "Request a quote",
    quoteSetup: "Request a quote for this setup",
    search: "Search",
    complete: "Complete my setup",
    quoteOnly: "Quote this only",
    selected: "Selected",
    explore: "Explore",
    indicative: "Indicative",
    setupIndicative: "Setup, indicative",
    swap: "Swap",
    noSwap: "No other part fits this role.",
    back: "Back",
    askPlaceholder: "Ask a question… “Does this work with the rest of the kit?”",
    ask: "Ask",
    whyLabel: "Why this setup",
    partsFit: "all fit",
    partWord: "part",
    partsWord: "parts",
    moreWord: "more",
    fits: "fits",
    yourSetup: "Your setup",
    quoteTitle: "Request a quote",
    quoteName: "Name",
    quoteEmail: "Email",
    quoteSend: "Send request",
    quoteSent: "Request received. Reference",
    graphIndicative: "indicative",
    photoLabel: "Photo",
    loading: "Loading…",
    noSetups: "No setups came back for this product. You can still quote it on its own.",
    swappedNote: "Updated with a part that still fits.",
    resultWord: "result",
    resultsWord: "results",
    forWord: "for",
    mark: "Rig · by Tervory",
    close: "Close",
    sampleLabel: "SAMPLE DATA",
    notAlternative: "That part is not an alternative that fits.",
    errorGeneric: "Something went wrong.",
    unavailable: "That setup is no longer available.",
  },
};

export function resolveTheme(value: string | null): Theme {
  if (value === "custom-nation") return customNation;
  if (!value || value === "neutral") return neutral;
  if (value.trim().startsWith("{")) {
    try {
      const parsed = JSON.parse(value) as Partial<Theme> & { id?: string };
      return {
        ...neutral,
        ...parsed,
        id: typeof parsed.id === "string" ? parsed.id : "custom",
        colors: { ...neutral.colors, ...parsed.colors },
        graph: { ...neutral.graph, ...parsed.graph },
        fonts: { ...neutral.fonts, ...parsed.fonts },
        copy: {
          ...neutral.copy,
          ...parsed.copy,
          popular: parsed.copy?.popular ?? neutral.copy.popular,
          steps: parsed.copy?.steps ?? neutral.copy.steps,
        },
      };
    } catch {
      return neutral;
    }
  }
  return neutral;
}
