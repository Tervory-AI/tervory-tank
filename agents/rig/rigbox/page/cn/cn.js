/* Custom Nation shopper. Prices, stock, and fits come from Rig. */
(function () {
  const CN = window.CN || { key: "", email: "", phone: "", name: "Custom Nation" };
  const app = document.getElementById("app");
  const dialog = document.getElementById("dialog");
  let token = 0;
  let unmountVisual = null;

  function h(tag, props, kids) {
    const node = document.createElement(tag);
    Object.entries(props || {}).forEach(function (entry) {
      const key = entry[0];
      const value = entry[1];
      if (value == null || value === false) return;
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = String(value);
      else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
      else if (key in node && (key === "checked" || key === "disabled" || key === "hidden" || key === "value")) node[key] = value;
      else node.setAttribute(key, String(value));
    });
    (kids || []).forEach(function (kid) {
      if (kid == null || kid === false) return;
      node.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
    });
    return node;
  }

  function rand(amount) {
    const n = Math.round(Number(amount) || 0);
    return "R " + String(n).replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  }

  function pathOf() {
    const path = location.pathname.replace(/\/+$/, "") || "/cn";
    const rest = path === "/cn" ? "/" : path.replace(/^\/cn/, "") || "/";
    const params = new URLSearchParams(location.search);
    return { rest: rest, params: params };
  }

  function go(url) {
    history.pushState({}, "", url);
    render();
  }

  async function api(path, options) {
    const response = await fetch(path, Object.assign({}, options, {
      headers: Object.assign({ "X-Rig-Key": CN.key, "Content-Type": "application/json" }, (options && options.headers) || {}),
    }));
    const body = await response.json().catch(function () { return {}; });
    if (!response.ok) {
      const message = body.error && body.error.message ? body.error.message : "The catalogue didn't answer.";
      const error = new Error(message);
      error.status = response.status;
      throw error;
    }
    return body;
  }

  let catalogueJob = null;
  function catalogue() {
    if (!catalogueJob) catalogueJob = api("/v1/rig/search?limit=50&category=all").then(function (body) { return body.results || []; });
    return catalogueJob;
  }

  function byId(rows) {
    const map = {};
    (rows || []).forEach(function (row) { map[row.id] = row; });
    return map;
  }

  function picksKey(id) { return "cn-picks:" + id; }

  function defaultPicks(product) {
    const defaults = product.defaults || {};
    return {
      slide_grip: defaults.slide_grip || defaults.grip || "",
      barrel: defaults.barrel || "",
      optic_cut: defaults.optic_cut || "RMR",
      trigger: product.id === "ARCHON-TYPE-B" ? "performance" : "standard",
      dot: "ARCHON-DOT-RMR",
      mag: "ARCHON-MAG-15",
    };
  }

  function loadPicks(product) {
    const base = defaultPicks(product);
    try {
      const saved = JSON.parse(sessionStorage.getItem(picksKey(product.id)) || "null");
      if (saved && typeof saved === "object") return Object.assign(base, saved);
    } catch (_error) { /* keep the defaults */ }
    return base;
  }

  function savePicks(id, picks) {
    sessionStorage.setItem(picksKey(id), JSON.stringify(picks));
  }

  function stockOf(availability) {
    const stock = availability || {};
    let label = "Out of stock";
    let tone = "status-oos";
    if (stock.status === "in_stock") { label = "In stock"; tone = "status-ok"; }
    else if (stock.status === "low_stock") {
      label = "Low stock" + (stock.qty ? " · " + stock.qty + " left" : "");
      tone = "status-low";
    } else if (stock.status === "on_order") { label = "On order"; tone = "status-low"; }
    return { label: label, tone: tone, where: stock.location || "", lead: stock.lead || "", demo: stock.label || "Demo stock" };
  }

  function barrelOf(product, picks) {
    const barrels = (product.options && product.options.barrel) || [];
    return barrels.find(function (item) { return item.code === picks.barrel; }) || null;
  }

  function displayAmount(product, picks) {
    const barrel = barrelOf(product, picks);
    return Number(product.price.amount) + Number((barrel && barrel.delta) || 0);
  }

  function fitFor(partSku, cut, fits, family) {
    const rows = (fits || []).filter(function (fit) {
      return fit.part_sku === partSku && (fit.fits_family === family || fit.fits_sku === family);
    });
    if (!rows.length) return null;
    for (let i = 0; i < rows.length; i += 1) {
      const needed = (rows[i].rule && rows[i].rule.optic_cut) || "";
      if (!needed || needed === cut) {
        return { fits: true, badge: needed ? "Fits your " + needed + " cut" : (rows[i].note || "Fits"), note: rows[i].note || "" };
      }
    }
    const note = rows[0].note || "";
    const needed = (rows[0].rule && rows[0].rule.optic_cut) || "";
    const badge = note.toLowerCase().startsWith("needs") ? note : (needed ? "Needs " + needed + " cut" : note);
    return { fits: false, badge: badge, note: note };
  }

  function linesFor(product, picks, map) {
    const lines = [{ product: product, choice: choiceText(product, picks) }];
    if (product.category !== "Pistols") return lines;
    const barrel = barrelOf(product, picks);
    if (barrel && barrel.sku && map[barrel.sku]) lines.push({ product: map[barrel.sku], choice: barrel.label || "" });
    if (picks.trigger === "performance" && map["ARCHON-TRIGGER-PERF"]) {
      lines.push({ product: map["ARCHON-TRIGGER-PERF"], choice: "Performance" });
    }
    if (picks.dot && map[picks.dot]) lines.push({ product: map[picks.dot], choice: map[picks.dot].name });
    if (picks.dot === "ARCHON-DOT-RMR" && map["ARCHON-RMR-SCREWS"]) {
      lines.push({ product: map["ARCHON-RMR-SCREWS"], choice: "RMR" });
    }
    if (picks.mag && map[picks.mag]) lines.push({ product: map[picks.mag], choice: map[picks.mag].name });
    return lines;
  }

  function choiceText(product, picks) {
    const parts = [picks.slide_grip || picks.grip, picks.barrel, picks.optic_cut].filter(Boolean);
    return parts.join(" · ");
  }

  function sum(lines) {
    return lines.reduce(function (total, line) { return total + Number(line.product.price.amount); }, 0);
  }

  function priceLine(amount, label) {
    return h("p", { class: "price" }, [
      rand(amount) + " ",
      h("span", { class: "gold", text: label || "Demo price" }),
    ]);
  }

  function openDialog(title, kids) {
    const panel = h("div", { class: "panel", role: "dialog", "aria-modal": "true", "aria-label": title }, [
      h("h2", { text: title }),
    ].concat(kids || []).concat([
      h("button", { type: "button", class: "ghost", text: "Close", onclick: closeDialog }),
    ]));
    dialog.replaceChildren(panel);
    dialog.hidden = false;
    panel.querySelector("button").focus();
  }

  function closeDialog() {
    dialog.hidden = true;
    dialog.replaceChildren();
  }

  function mountFlow(host, model) {
    if (unmountVisual) unmountVisual();
    unmountVisual = null;
    if (!host || !window.CNVisual) return;
    unmountVisual = window.CNVisual.mount(host, model);
  }

  function filtersFrom(params) {
    return {
      q: params.get("q") || "",
      inStock: params.get("in_stock") === "1",
      maxPrice: params.get("max") || "30000",
      sort: params.get("sort") || "",
      category: params.get("category") || "all",
      view: params.get("view") || "list",
    };
  }

  function searchUrl(filters) {
    const params = new URLSearchParams();
    if (filters.q) params.set("q", filters.q);
    if (filters.inStock) params.set("in_stock", "1");
    if (filters.maxPrice && String(filters.maxPrice) !== "30000") params.set("max", String(filters.maxPrice));
    if (filters.sort) params.set("sort", filters.sort);
    if (filters.category && filters.category !== "all") params.set("category", filters.category);
    if (filters.view && filters.view !== "list") params.set("view", filters.view);
    const query = params.toString();
    return "/cn/results" + (query ? "?" + query : "");
  }

  function apiSearch(filters) {
    const params = new URLSearchParams();
    params.set("q", filters.q || "");
    params.set("limit", "24");
    if (filters.inStock) params.set("in_stock", "true");
    if (filters.maxPrice && Number(filters.maxPrice) < 30000) params.set("max_price", String(filters.maxPrice));
    if (filters.sort) params.set("sort", filters.sort);
    if (filters.category && filters.category !== "all") params.set("category", filters.category === "Optics" ? "Sights" : filters.category);
    return api("/v1/rig/search?" + params.toString());
  }

  function fieldSelect(name, label, value, options, onchange) {
    const select = h("select", { id: name, name: name, onchange: onchange });
    options.forEach(function (option) {
      const node = h("option", { value: option[0], text: option[1] });
      if (option[0] === value) node.selected = true;
      select.append(node);
    });
    return h("label", { class: "field", text: label }, [select]);
  }

  function radioGroup(legend, name, values, current, onPick) {
    const group = h("fieldset", { class: "option", role: "radiogroup", "aria-label": legend });
    group.append(h("legend", { text: legend }));
    const row = h("div", { class: "chips" });
    values.forEach(function (value, index) {
      const id = typeof value === "string" ? value : value.code;
      const label = typeof value === "string" ? value : value.label;
      const pressed = current === id;
      const button = h("button", {
        type: "button",
        class: "chip",
        role: "radio",
        "data-code": id,
        "aria-checked": pressed ? "true" : "false",
        tabindex: pressed || (!current && index === 0) ? "0" : "-1",
        text: label,
        onclick: function () { onPick(id); },
        onkeydown: function (event) { arrowRadio(event, row, onPick); },
      });
      row.append(button);
    });
    group.append(row);
    return group;
  }

  function arrowRadio(event, row, onPick) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const buttons = Array.from(row.querySelectorAll("[role='radio']"));
    const index = buttons.indexOf(event.currentTarget);
    const next = event.key === "ArrowRight" ? (index + 1) % buttons.length : (index - 1 + buttons.length) % buttons.length;
    event.preventDefault();
    onPick(buttons[next].getAttribute("data-code") || "");
  }

  function optionValues(product, key) {
    const options = (product.options && product.options[key]) || [];
    return options;
  }

  async function render() {
    const current = ++token;
    if (unmountVisual) { unmountVisual(); unmountVisual = null; }
    app.setAttribute("aria-busy", "true");
    app.replaceChildren(h("p", { class: "lede", text: "Looking through the catalogue…" }));
    const route = pathOf();
    try {
      let view;
      if (route.rest === "/" || route.rest === "") view = await viewHome();
      else if (route.rest === "/results") view = await viewResults(route.params);
      else if (route.rest === "/honest") view = await viewHonest();
      else if (route.rest.indexOf("/product/") === 0) view = await viewProduct(decodeURIComponent(route.rest.slice("/product/".length)));
      else if (route.rest.indexOf("/build/") === 0) view = await viewBuild(decodeURIComponent(route.rest.slice("/build/".length)));
      else view = await viewHome();
      if (current !== token) return;
      app.replaceChildren(view);
      const flow = app.querySelector("[data-flow]");
      if (flow) {
        const model = JSON.parse(flow.getAttribute("data-flow"));
        model.onOpen = function (id) { go("/cn/product/" + encodeURIComponent(id)); };
        mountFlow(flow, model);
      }
    } catch (error) {
      if (current !== token) return;
      app.replaceChildren(banner("The catalogue is not connected.", error.message || "Try again in a moment."));
    } finally {
      if (current === token) app.removeAttribute("aria-busy");
    }
  }

  function banner(title, copy) {
    return h("section", { class: "banner" }, [h("strong", { text: title }), h("p", { text: copy })]);
  }

  async function viewHome() {
    const rows = await catalogue();
    const counts = {};
    rows.forEach(function (row) { counts[row.category] = (counts[row.category] || 0) + 1; });
    const order = ["Pistols", "Sights", "Triggers", "Magazines", "Lights", "Holsters"];
    const groups = order.filter(function (name) { return counts[name]; }).map(function (name) {
      return { category: name, count: counts[name] };
    });
    const filters = { q: "", inStock: false, maxPrice: "30000", sort: "", category: "all", view: "list" };
    const form = homeForm(filters);
    const flow = h("div", {
      class: "flow",
      "data-flow": JSON.stringify({ layout: "orbit", centre: "Ready when you are.", groups: groups, items: [] }),
      role: "img",
      "aria-label": "Categories around the search",
    });
    const popular = ["Archon Type B", "Type B Ported", "Type A", "15-round magazine", "Performance trigger"];
    return h("div", { class: "home" }, [
      h("section", {}, [
        h("h1", { text: "Find the right Archon, fast." }),
        h("p", { class: "lede", text: "Search the Custom Nation demo catalogue. Every price is a demo price and every stock line is demo stock." }),
        form,
        h("p", { class: "meta", text: "Popular searches" }),
        h("div", { class: "pills" }, popular.map(function (label) {
          const query = label === "15-round magazine" ? "15 round mag" : label === "Type A" ? "Archon Type A" : label === "Type B Ported" ? "type b ported" : label === "Performance trigger" ? "performance trigger" : label;
          return h("a", { class: "chip", href: "/cn/results?q=" + encodeURIComponent(query), text: label });
        })),
        askBox("ARCHON-TYPE-B"),
      ]),
      h("section", {}, [flow]),
    ]);
  }

  function homeForm(filters) {
    const input = h("input", {
      type: "search",
      name: "q",
      placeholder: "Search a model or part — try “Archon Type B”",
      "aria-label": "Search a model or part",
      value: filters.q,
    });
    const stock = h("input", { type: "checkbox", name: "in_stock" });
    const max = h("input", { type: "range", name: "max", min: "5000", max: "30000", step: "500", value: filters.maxPrice, "aria-describedby": "max-label" });
    const maxLabel = h("span", { id: "max-label", text: "Any, up to " + rand(filters.maxPrice) });
    max.addEventListener("input", function () {
      maxLabel.textContent = Number(max.value) >= 30000 ? "Any, up to R 30 000" : "Up to " + rand(max.value);
    });
    const sort = fieldSelect("sort", "Sort", filters.sort, [["", "Price low–high"], ["price_desc", "Price high–low"]]);
    const category = fieldSelect("category", "Category", filters.category, [
      ["all", "All"], ["Pistols", "Pistols"], ["Sights", "Optics"], ["Triggers", "Triggers"],
      ["Magazines", "Magazines"], ["Lights", "Lights"], ["Holsters", "Holsters"], ["Barrels", "Barrels"], ["Parts", "Parts"],
    ]);
    const form = h("form", { class: "search-form", role: "search", onsubmit: function (event) {
      event.preventDefault();
      go(searchUrl({
        q: input.value.trim(),
        inStock: stock.checked,
        maxPrice: max.value,
        sort: form.querySelector("#sort").value,
        category: form.querySelector("#category").value,
        view: "list",
      }));
    } }, [
      h("div", { class: "search-row" }, [input, h("button", { class: "primary", type: "submit", text: "Search" })]),
      h("div", { class: "filters" }, [
        h("label", { class: "check" }, [stock, " In stock only"]),
        h("label", { class: "field" }, ["Price ", maxLabel, max]),
        sort,
        category,
      ]),
      h("p", {}, [h("span", { class: "gold", text: "Demo stock" }), " Prices and stock on this page are demo figures."]),
    ]);
    return form;
  }

  function askBox(productId) {
    const input = h("input", { type: "text", name: "question", "aria-label": "Ask about this catalogue", placeholder: "Ask about a spec in the catalogue" });
    const out = h("div", { "aria-live": "polite" });
    const form = h("form", { class: "stack", onsubmit: async function (event) {
      event.preventDefault();
      const question = input.value.trim();
      if (!question) return;
      out.replaceChildren(h("p", { class: "lede", text: "Checking the catalogue…" }));
      try {
        const body = await api("/v1/rig/ask", { method: "POST", body: JSON.stringify({ product_id: productId, question: question }) });
        out.replaceChildren(answerCard(question, body.answer || ""));
      } catch (error) {
        out.replaceChildren(banner("The catalogue didn't answer.", error.message));
      }
    } }, [
      h("label", { class: "field", text: "Ask" }, [input]),
      h("button", { type: "submit", class: "ghost", text: "Ask" }),
      out,
    ]);
    return form;
  }

  function answerCard(question, answer) {
    const unknown = String(answer).trim().toLowerCase() === "i don't know";
    const kids = [h("strong", { text: unknown ? "I don’t know." : answer })];
    if (unknown) {
      kids.push(h("p", { text: question.toLowerCase().indexOf("muzzle velocity") >= 0
        ? "Muzzle velocity isn’t in the catalogue."
        : "That isn’t in this catalogue." }));
      kids.push(h("p", { text: "Contact " + CN.name + " at " + CN.email + (CN.phone ? " or " + CN.phone : "") + "." }));
    }
    return h("div", { class: "banner" }, kids);
  }

  async function viewResults(params) {
    const filters = filtersFrom(params);
    const body = await apiSearch(filters);
    const results = body.results || [];
    const focus = results.find(function (item) { return item.id === body.focus_id; }) || results[0];
    const heading = results.length
      ? results.length + " matches · " + (body.groups || []).length + " categories"
      : "No matches";
    const tabs = viewTabs(filters);
    const message = body.message ? banner(body.honest === "closest" ? "No exact match." : body.honest === "not_stocked" ? "We don’t stock that." : "Nothing matches that yet.", body.message) : null;
    let main;
    if (!results.length) {
      main = h("div", {}, [
        message,
        h("p", { class: "lede", text: "Try a model we list, or one of these." }),
        h("div", { class: "pills" }, [
          h("a", { class: "chip", href: "/cn/results?q=Archon%20Type%20B", text: "Archon Type B" }),
          h("a", { class: "chip", href: "/cn/results?q=magazine", text: "Magazine" }),
          h("a", { class: "chip", href: "/cn/results?q=holster", text: "Holster" }),
        ]),
      ]);
    } else if (filters.view === "compare") main = compareView(results);
    else if (filters.view === "visual") main = visualView(body, focus);
    else main = listView(results, body.fits || []);
    const open = focus
      ? h("a", {
          class: "primary",
          href: "/cn/product/" + encodeURIComponent(focus.id),
          text: (body.honest === "closest" ? "Show " : "Open ") + focus.name,
        })
      : null;
    return h("section", {}, [
      h("h1", { text: filters.q ? "Results for “" + filters.q + "”" : "Catalogue" }),
      h("p", { class: "meta", text: heading }),
      tabs,
      message,
      h("div", { class: "layout" }, [
        main,
        sidebar(results, focus, open),
      ]),
    ]);
  }

  function viewTabs(filters) {
    const views = [["list", "List"], ["compare", "Compare"], ["visual", "Visual"]];
    const row = h("div", { class: "tabs", role: "tablist", "aria-label": "Result view" });
    views.forEach(function (pair) {
      const selected = filters.view === pair[0];
      row.append(h("button", {
        type: "button",
        role: "tab",
        "aria-selected": selected ? "true" : "false",
        tabindex: selected ? "0" : "-1",
        class: "chip",
        text: pair[1],
        onclick: function () {
          filters.view = pair[0];
          go(searchUrl(filters));
        },
        onkeydown: function (event) {
          if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
          const index = views.findIndex(function (item) { return item[0] === filters.view; });
          const next = event.key === "ArrowRight" ? (index + 1) % views.length : (index - 1 + views.length) % views.length;
          filters.view = views[next][0];
          go(searchUrl(filters));
        },
      }));
    });
    return row;
  }

  function listView(results, fits) {
    const wrap = h("div", {});
    let category = "";
    results.forEach(function (item) {
      if (item.category !== category) {
        category = item.category;
        wrap.append(h("h2", { class: "group", text: category }));
      }
      wrap.append(resultCard(item, fits));
    });
    return wrap;
  }

  function resultCard(item, fits) {
    const stock = stockOf(item.availability);
    const picks = loadPicks(item);
    const media = h("img", { src: item.image, alt: item.name });
    const body = h("div", {});
    body.append(h("h3", {}, [h("a", { href: "/cn/product/" + encodeURIComponent(item.id), text: item.name })]));
    body.append(priceLine(displayAmount(item, picks), item.price_label));
    body.append(h("p", { class: stock.tone, text: stock.label + (stock.where ? " · " + stock.where : "") + (stock.lead ? " · " + stock.lead : "") }));
    body.append(h("p", { class: "meta", text: stock.demo }));
    if (item.badges && item.badges.length) {
      body.append(h("div", { class: "badges" }, item.badges.map(function (badge) { return h("span", { class: "badge", text: badge }); })));
    }
    const grip = optionValues(item, "slide_grip");
    const barrels = optionValues(item, "barrel");
    const cuts = optionValues(item, "optic_cut");
    if (grip.length) body.append(radioGroup("Slide / grip", "grip", grip, picks.slide_grip, function (value) {
      picks.slide_grip = value;
      savePicks(item.id, picks);
      go(location.pathname + location.search);
    }));
    if (barrels.length) {
      body.append(radioGroup("Barrel", "barrel", barrels.map(function (barrel) {
        const extra = barrel.delta ? " +" + rand(barrel.delta) : "";
        return { code: barrel.code, label: barrel.label + extra };
      }), picks.barrel, function (value) {
        picks.barrel = value;
        savePicks(item.id, picks);
        go(location.pathname + location.search);
      }));
    }
    if (cuts.length) body.append(radioGroup("Optic cut", "cut", cuts, picks.optic_cut, function (value) { picks.optic_cut = value; savePicks(item.id, picks); go(location.pathname + location.search); }));
    const fit = item.fit;
    if (fit) body.append(h("p", { text: fit.badge }));
    else if (item.category !== "Pistols") body.append(h("p", { class: "muted", text: "Check fit" }));
    if (item.availability && item.availability.status === "out_of_stock") {
      if (item.alternative) {
        body.append(h("p", { text: "Nearest in stock: " + item.alternative.name + " · " + rand(item.alternative.price.amount) }));
      }
      body.append(h("button", { type: "button", class: "ghost", text: "Notify me", onclick: function () {
        openDialog("Notify me", [
          h("p", { text: "This demo does not send alerts. " + CN.name + " can confirm stock for " + item.name + " at " + CN.email + "." }),
        ]);
      } }));
    }
    if (item.demo_item) body.append(h("p", { class: "meta", text: "Demo item" }));
    return h("article", { class: "card" }, [media, body]);
  }

  function compareView(results) {
    const pistols = results.filter(function (item) { return item.category === "Pistols"; });
    const rows = pistols.length >= 2 ? pistols : results.slice(0, 3);
    return h("div", { class: "compare-grid" }, rows.map(function (item) {
      const stock = stockOf(item.availability);
      const verified = (item.attributes && item.attributes.verified) || {};
      const history = item.price_history;
      const specs = [
        ["Difference from cheapest", item.compare && item.compare.delta ? "+" + rand(item.compare.delta) : rand(0)],
        ["Availability", stock.label],
        ["Where", stock.where || "Not in the catalogue"],
        ["Lead time", stock.lead || "Not in the catalogue"],
        ["Length", verified.length_in ? verified.length_in + " in" : "Not in the catalogue"],
        ["Lockup", verified.locking || "Not in the catalogue"],
        ["Barrel", verified.barrel || "Not in the catalogue"],
        ["Optic cuts", ((item.options && item.options.optic_cut) || verified.optic_cuts || []).join(", ") || "Not in the catalogue"],
        ["Colours", ((item.options && (item.options.slide_grip || item.options.grip)) || []).join(", ") || "Not in the catalogue"],
        ["In the box", (item.attributes && item.attributes.in_box) || "Not in the catalogue"],
        ["Fit", item.fit ? item.fit.badge : "Check fit"],
        ["Price history", history ? "Was " + rand(history.was) + ", now " + rand(history.amount) + " on " + history.on + ". " + (history.label || "") : "Not in the catalogue"],
      ];
      const card = h("article", { class: "compare-card" }, [
        h("h3", { text: item.name }),
        priceLine(item.price.amount, item.price_label),
      ]);
      const list = h("dl", {});
      specs.forEach(function (spec) {
        list.append(h("dt", { text: spec[0] }), h("dd", { text: spec[1] }));
      });
      card.append(list, h("a", { class: "ghost", href: "/cn/product/" + encodeURIComponent(item.id), text: "Open" }));
      return card;
    }));
  }

  function visualView(body, focus) {
    const items = (body.results || []).map(function (item) {
      return { id: item.id, name: item.name, category: item.category, meta: rand(item.price.amount) };
    });
    return h("div", {
      class: "flow",
      "data-flow": JSON.stringify({
        layout: "columns",
        centre: focus ? focus.name : "Results",
        groups: body.groups || [],
        items: items,
      }),
      role: "img",
      "aria-label": "Results as a graph",
    });
  }

  function sidebar(results, focus, open) {
    const side = h("aside", { class: "side" }, [h("h2", { text: "In this catalogue" })]);
    ["Pistols", "Sights"].forEach(function (category) {
      const rows = results.filter(function (item) { return item.category === category; });
      if (!rows.length) return;
      side.append(h("h3", { text: category === "Sights" ? "Red dots" : "Pistols" }));
      rows.forEach(function (item) {
        const delta = item.compare ? item.compare.delta : 0;
        side.append(h("p", { text: item.name + " · " + rand(item.price.amount) + (delta ? " · +" + rand(delta) : " · cheapest") }));
      });
    });
    if (focus && focus.price_history) {
      const history = focus.price_history;
      side.append(h("h3", { text: "Price history" }));
      side.append(h("p", { text: focus.name + " was " + rand(history.was) + ", now " + rand(history.amount) + " on " + history.on + ". " + (history.label || "Demo data") + "." }));
    }
    if (open) side.append(open);
    return side;
  }

  async function viewProduct(id) {
    const detail = await api("/v1/rig/products/" + encodeURIComponent(id));
    const rows = await catalogue();
    const map = byId(rows);
    const picks = loadPicks(detail);
    const stock = stockOf(detail.availability);
    const verified = (detail.attributes && detail.attributes.verified) || {};
    const family = detail.family || detail.id;
    function redraw() {
      savePicks(detail.id, picks);
      go(location.pathname);
    }
    const specs = h("dl", {});
    [
      ["Lockup", verified.locking],
      ["Action", verified.action],
      ["Calibre", verified.caliber],
      ["Barrel", verified.barrel],
      ["Weight", verified.weight_oz ? verified.weight_oz + " oz" : ""],
      ["Length", verified.length_in ? verified.length_in + " in" : ""],
      ["Rail", verified.rail],
    ].forEach(function (spec) {
      if (!spec[1]) return;
      specs.append(h("dt", { text: spec[0] }), h("dd", { text: spec[1] }));
    });
    const dots = ["ARCHON-DOT-RMS", "ARCHON-DOT-RMR", "ARCHON-DOT-ACRO"].map(function (sku) { return map[sku]; }).filter(Boolean);
    const fitLines = dots.map(function (dot) {
      const fit = fitFor(dot.id, picks.optic_cut, detail.fits || [], family);
      return h("p", { text: dot.name + " · " + (fit ? fit.badge : "Check fit") + " · " + rand(dot.price.amount) + " · " + (dot.price_label || "Demo price") });
    });
    const stills = [
      ["/page/cn/media/type-b-render.jpg", "Type B render, muzzle left"],
      ["/page/cn/media/type-b-photo.jpg", "Type B studio photo"],
      ["/page/cn/media/grip.jpg", "Modular grip"],
      ["/page/cn/media/trigger.jpg", "Flat face trigger"],
    ];
    const column = h("div", {}, [
      h("h1", { text: detail.name }),
      detail.attributes && detail.attributes.tagline ? h("p", { class: "lede", text: detail.attributes.tagline }) : null,
      priceLine(displayAmount(detail, picks), detail.price_label),
      h("p", { class: stock.tone, text: stock.label + (stock.where ? " · " + stock.where : "") + (stock.lead ? " · " + stock.lead : "") }),
      h("p", { class: "meta", text: stock.demo }),
      detail.demo_item ? h("p", { class: "banner", text: "Demo item. The picture is a stand-in, not a verified photo of this exact model." }) : null,
    ]);
    const grips = optionValues(detail, "slide_grip").length ? optionValues(detail, "slide_grip") : optionValues(detail, "grip");
    if (grips.length) column.append(radioGroup("Colour", "colour", grips, picks.slide_grip || picks.grip, function (value) { picks.slide_grip = value; redraw(); }));
    const barrels = optionValues(detail, "barrel");
    if (barrels.length) {
      column.append(radioGroup("Barrel", "barrel", barrels.map(function (barrel) {
        return { code: barrel.code, label: barrel.label + (barrel.delta ? " +" + rand(barrel.delta) : "") + (barrel.demo_item ? " · demo" : "") };
      }), picks.barrel, function (value) { picks.barrel = value; redraw(); }));
    }
    const cuts = optionValues(detail, "optic_cut");
    if (cuts.length) column.append(radioGroup("Optic cut", "cut", cuts, picks.optic_cut, function (value) { picks.optic_cut = value; redraw(); }));
    column.append(h("h2", { text: "Compared in this catalogue" }));
    if (detail.compare) {
      column.append(h("p", { text: detail.compare.delta ? "+" + rand(detail.compare.delta) + " from the cheapest in " + detail.category : "Cheapest in " + detail.category }));
    }
    if (detail.price_history) {
      const history = detail.price_history;
      column.append(h("h2", { text: "Price history" }), h("p", { text: "Was " + rand(history.was) + ", now " + rand(history.amount) + " on " + history.on + ". " + (history.label || "Demo data") + "." }));
    }
    if (detail.attributes && detail.attributes.in_box) column.append(h("h2", { text: "In the box" }), h("p", { text: detail.attributes.in_box }));
    column.append(h("h2", { text: "Fits" }));
    fitLines.forEach(function (line) { column.append(line); });
    column.append(h("a", { class: "primary", href: "/cn/build/" + encodeURIComponent(detail.id), text: detail.category === "Pistols" ? "Build this pistol" : "Reserve this part" }));
    return h("article", { class: "product" }, [
      h("div", {}, [
        h("img", { class: "hero", src: detail.image, alt: detail.name }),
        detail.id === "ARCHON-TYPE-B" ? h("div", { class: "stills" }, stills.map(function (still) {
          return h("figure", {}, [h("img", { src: still[0], alt: still[1] }), h("figcaption", { text: still[1] })]);
        })) : null,
        specs,
      ]),
      column,
    ]);
  }

  async function viewBuild(id) {
    const detail = await api("/v1/rig/products/" + encodeURIComponent(id));
    const rows = await catalogue();
    const map = byId(rows.concat([detail]));
    const picks = loadPicks(detail);
    const lines = linesFor(detail, picks, map);
    const total = sum(lines);
    const dots = ["ARCHON-DOT-RMS", "ARCHON-DOT-RMR", "ARCHON-DOT-ACRO"].map(function (sku) { return map[sku]; }).filter(Boolean);
    const mags = ["ARCHON-MAG-12", "ARCHON-MAG-15", "ARCHON-MAG-18"].map(function (sku) { return map[sku]; }).filter(Boolean);
    function redraw(key, value) { picks[key] = value; savePicks(detail.id, picks); go(location.pathname); }
    const steps = [
      ["0:00", "/page/cn/media/type-b-render.jpg", "Base pistol, flush barrel"],
      ["0:06", "/page/cn/media/type-b-render-left.jpg", "Threaded barrel, suppressor ready"],
      ["0:15", "/page/cn/media/sheet-versatility.jpg", "Optics ready"],
      ["0:27", "/page/cn/media/grip.jpg", "Interchangeable grip textures"],
      ["0:41", "/page/cn/media/still-up.jpg", "Modular grip"],
    ];
    const list = h("ol", { class: "lines" });
    lines.forEach(function (line) {
      list.append(h("li", {}, [
        h("span", { text: line.product.name + " · " + line.product.id }),
        h("span", { class: "meta", text: rand(line.product.price.amount) + " · " + (line.product.price_label || "Demo price") }),
      ]));
    });
    const name = h("input", { name: "name", required: "true", autocomplete: "name", "aria-label": "Your name" });
    const email = h("input", { name: "email", type: "email", required: "true", autocomplete: "email", "aria-label": "Email" });
    const phone = h("input", { name: "phone", type: "tel", autocomplete: "tel", "aria-label": "Phone" });
    const status = h("div", { "aria-live": "polite" });
    const form = h("form", { class: "form", onsubmit: async function (event) {
      event.preventDefault();
      const button = form.querySelector(".primary");
      button.disabled = true;
      status.replaceChildren(h("p", { text: "Sending the reservation…" }));
      try {
        const quoted = await api("/v1/rig/quote", {
          method: "POST",
          body: JSON.stringify({
            contact: { name: name.value.trim(), email: email.value.trim(), phone: phone.value.trim() },
            setup: {
              label: "Your " + detail.name + " build",
              parts: lines.map(function (line) {
                return { role: line.product.category, product: { id: line.product.id }, choice: line.choice || "" };
              }),
            },
          }),
        });
        form.querySelector(".primary").remove();
        status.replaceChildren(h("div", { class: "banner" }, [h("strong", { text: confirmation(quoted) })]));
      } catch (error) {
        button.disabled = false;
        status.replaceChildren(banner("The reservation was not sent.", error.message));
      }
    } }, [
      h("label", { class: "field", text: "Name" }, [name]),
      h("label", { class: "field", text: "Email" }, [email]),
      h("label", { class: "field", text: "Phone" }, [phone]),
      h("button", { class: "primary", type: "submit", text: "Reserve at Custom Nation" }),
      status,
    ]);
    return h("article", { class: "build" }, [
      h("div", {}, [
        h("h1", { text: "Your " + detail.name + " build" }),
        detail.id === "ARCHON-TYPE-B" ? h("p", { class: "lede", text: "Stills from the versatility video. A spin and a 3D view come next. The exploded-view PDF is not in yet." }) : h("p", { class: "lede", text: "The lines below are catalogue prices. " + CN.name + " confirms stock and paperwork before anything is final." }),
        detail.id === "ARCHON-TYPE-B" ? h("div", { class: "timeline" }, steps.map(function (step) {
          return h("div", { class: "step" }, [
            h("span", { class: "meta", text: step[0] }),
            h("img", { src: step[1], alt: step[2] }),
            h("span", { text: step[2] }),
          ]);
        })) : null,
        h("h2", { text: "Parts" }),
        list,
      ]),
      h("aside", { class: "side" }, [
        h("p", { class: "meta", text: "Running total" }),
        h("p", { class: "total", text: rand(total) }),
        h("p", {}, [h("span", { class: "gold", text: "Demo price" })]),
        dots.length ? radioGroup("Red dot", "dot", dots.map(function (dot) { return { code: dot.id, label: dot.name + " " + rand(dot.price.amount) }; }), picks.dot, function (value) { redraw("dot", value); }) : null,
        mags.length ? radioGroup("Magazine", "mag", mags.map(function (mag) { return { code: mag.id, label: mag.name + " " + rand(mag.price.amount) }; }), picks.mag, function (value) { redraw("mag", value); }) : null,
        detail.id === "ARCHON-TYPE-B" ? radioGroup("Trigger", "trigger", [{ code: "standard", label: "Standard, included" }, { code: "performance", label: "Performance" }], picks.trigger, function (value) { redraw("trigger", value); }) : null,
        h("p", { class: "note", text: CN.name + " confirms stock and paperwork before anything is final. Nothing is held or charged until they confirm." }),
        form,
      ]),
    ]);
  }

  function confirmation(quoted) {
    const ref = quoted.request_id || "";
    if (quoted.delivered) {
      return "Reservation " + ref + " is with " + CN.name + ". " + CN.name + " will confirm stock and paperwork. Nothing is held or charged.";
    }
    return "Reservation " + ref + " is saved. Mail is not connected on this server yet. Nothing is held or charged.";
  }

  async function viewHonest() {
    const missing = await apiSearch({ q: "Archon Type C", inStock: false, maxPrice: "30000", sort: "", category: "all", view: "list" });
    const unknown = await api("/v1/rig/ask", { method: "POST", body: JSON.stringify({ product_id: "ARCHON-TYPE-B", question: "What muzzle velocity does the Type B get with 147 gr ammo?" }) });
    const nothing = await apiSearch({ q: "xq-77 laser grip", inStock: false, maxPrice: "30000", sort: "", category: "all", view: "list" });
    const focus = (missing.results || []).find(function (item) { return item.id === missing.focus_id; }) || (missing.results || [])[0];
    return h("section", {}, [
      h("h1", { text: "Honest states" }),
      h("div", { class: "compare-grid" }, [
        h("article", { class: "compare-card" }, [
          h("h2", { text: "Archon Type C" }),
          h("p", { text: missing.message || "No exact match." }),
          h("p", { text: "Closest matches: " + (missing.results || []).map(function (item) { return item.name; }).join(", ") + "." }),
          focus ? h("a", { class: "primary", href: "/cn/product/" + encodeURIComponent(focus.id), text: "Show " + focus.name }) : null,
        ]),
        h("article", { class: "compare-card" }, [
          h("h2", { text: "Muzzle velocity" }),
          answerCard("What muzzle velocity does the Type B get with 147 gr ammo?", unknown.answer || ""),
        ]),
        h("article", { class: "compare-card" }, [
          h("h2", { text: "xq-77 laser grip" }),
          h("p", { text: nothing.message || "Nothing matches that yet." }),
          h("div", { class: "pills" }, [
            h("a", { class: "ghost", href: "/cn/results?q=Archon%20Type%20B", text: "Archon Type B" }),
            h("a", { class: "ghost", href: "/cn/results?q=magazine", text: "Magazine" }),
            h("a", { class: "ghost", href: "/cn/results?q=holster", text: "Holster" }),
          ]),
        ]),
      ]),
    ]);
  }

  document.getElementById("contact-us").addEventListener("click", function () {
    openDialog("Contact us", [
      h("p", { text: CN.email }),
      CN.phone ? h("p", { text: CN.phone }) : null,
      h("p", { class: "meta", text: "Sales mail from this demo goes to the shop address in the catalogue settings." }),
    ]);
  });
  document.getElementById("client-login").addEventListener("click", function () {
    openDialog("Client login", [h("p", { text: "Client login is not part of this demo." })]);
  });
  dialog.addEventListener("click", function (event) { if (event.target === dialog) closeDialog(); });
  document.addEventListener("keydown", function (event) { if (event.key === "Escape") closeDialog(); });
  document.addEventListener("click", function (event) {
    const link = event.target.closest("a[href^='/cn']");
    if (!link || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    go(link.getAttribute("href"));
  });
  window.addEventListener("popstate", render);
  render();
})();
