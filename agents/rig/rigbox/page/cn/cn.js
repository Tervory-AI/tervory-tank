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

  function stockDetail(stock) {
    const lead = stock.lead && stock.lead.toLowerCase() !== stock.label.toLowerCase() ? stock.lead : "";
    return [stock.where, lead].filter(Boolean).join(" · ");
  }

  function tally(count, singular, plural) {
    return count + " " + (count === 1 ? singular : plural);
  }

  function peerDelta(item, results) {
    const peers = (results || []).filter(function (row) { return row.category === item.category; });
    if (peers.length < 2) return null;
    const cheapest = Math.min.apply(null, peers.map(function (row) { return Number(row.price.amount) || 0; }));
    return Number(item.price.amount) - cheapest;
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
      minPrice: params.get("min") || "0",
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
    if (filters.minPrice && Number(filters.minPrice) > 0) params.set("min", String(filters.minPrice));
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
    if (filters.minPrice && Number(filters.minPrice) > 0) params.set("min_price", String(filters.minPrice));
    if (filters.maxPrice && Number(filters.maxPrice) < 30000) params.set("max_price", String(filters.maxPrice));
    if (filters.sort) params.set("sort", filters.sort);
    if (filters.category && filters.category !== "all") params.set("category", filters.category === "Optics" ? "Sights" : filters.category);
    return api("/v1/rig/search?" + params.toString());
  }

  function specValue(verified, name) {
    const rows = Array.isArray(verified) ? verified : [];
    const found = rows.find(function (item) { return item && item.name === name; });
    if (!found) return "";
    const value = found.value;
    return Array.isArray(value) ? value.join(", ") : String(value);
  }

  function fieldSelect(name, label, value, options, onchange) {
    const select = h("select", { id: "field-" + name, name: name, "aria-label": label, onchange: onchange });
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
      const blocked = typeof value === "object" && value.disabled;
      const button = h("button", {
        type: "button",
        class: "chip" + (blocked ? " is-blocked" : ""),
        role: "radio",
        "data-code": id,
        "aria-checked": pressed ? "true" : "false",
        "aria-disabled": blocked ? "true" : "false",
        disabled: blocked ? true : null,
        tabindex: pressed || (!current && index === 0) ? "0" : "-1",
        text: label,
        onclick: function () { if (!blocked) onPick(id); },
        onkeydown: function (event) { if (!blocked) arrowRadio(event, row, onPick); },
      });
      row.append(button);
    });
    group.append(row);
    return group;
  }

  function optionCards(legend, values, current, onPick) {
    const group = h("fieldset", { class: "option", role: "radiogroup", "aria-label": legend });
    group.append(h("legend", { text: legend }));
    const row = h("div", { class: "choice-list" });
    values.forEach(function (value) {
      const pressed = current === value.code;
      const blocked = !!value.disabled;
      row.append(h("button", {
        type: "button",
        class: "choice-card" + (pressed ? " on" : "") + (blocked ? " is-blocked" : ""),
        role: "radio",
        "aria-checked": pressed ? "true" : "false",
        "aria-disabled": blocked ? "true" : "false",
        disabled: blocked ? true : null,
        onclick: function () { if (!blocked) onPick(value.code); },
      }, [
        h("strong", { text: value.name }),
        h("span", { class: "meta", text: value.price }),
        h("span", { class: "chip tiny" + (value.fits ? " on" : ""), text: value.badge }),
        h("span", { class: value.tone || "meta", text: value.stock }),
      ]));
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
    const filters = { q: "", inStock: false, minPrice: "0", maxPrice: "30000", sort: "", category: "all", view: "list" };
    const form = searchForm(filters, true);
    const flow = h("div", {
      class: "flow hero-graph",
      "data-flow": JSON.stringify({
        layout: "orbit",
        centre: "Ready when you are.",
        caption: "Open a list, compare, or map.",
        groups: groups,
        items: [],
      }),
      "aria-label": "Categories around the search",
    });
    const popular = ["Archon Type B", "Type B Ported", "Type A", "15-round magazine", "Performance trigger"];
    return h("div", { class: "home" }, [
      h("section", { class: "hero" }, [
        h("h1", { text: "Find the right Archon, fast." }),
        h("p", { class: "lede", text: "Search Custom Nation for Archon pistols, red dots, triggers, magazines and more." }),
        form,
        h("p", { class: "meta", text: "Popular searches" }),
        h("div", { class: "pills" }, popular.map(function (label) {
          const query = label === "15-round magazine" ? "15 round mag" : label === "Type A" ? "Archon Type A" : label === "Type B Ported" ? "type b ported" : label === "Performance trigger" ? "performance trigger" : label;
          return h("a", { class: "chip", href: "/cn/results?q=" + encodeURIComponent(query), text: label });
        })),
        flow,
        h("p", { class: "meta ask-note", text: "Or just ask. Answers come from " + CN.name + "’s own catalogue, with sources." }),
        askBox("ARCHON-TYPE-B"),
      ]),
    ]);
  }

  function pillMenu(name, label, value, options) {
    const current = options.find(function (option) { return option[0] === value; }) || options[0];
    const button = h("button", {
      type: "button",
      class: "pill",
      "aria-haspopup": "listbox",
      "aria-expanded": "false",
      text: label + ": " + current[1],
    });
    const hidden = h("input", { type: "hidden", name: name, value: current[0] });
    const list = h("ul", { class: "pill-list", role: "listbox", hidden: "hidden" });
    options.forEach(function (option) {
      list.append(h("li", {}, [h("button", {
        type: "button",
        role: "option",
        class: "pill-option",
        text: option[1],
        onclick: function () {
          hidden.value = option[0];
          button.textContent = label + ": " + option[1];
          list.hidden = true;
          button.setAttribute("aria-expanded", "false");
        },
      })]));
    });
    button.addEventListener("click", function () {
      const opening = list.hidden;
      document.querySelectorAll(".pill-list").forEach(function (node) { node.hidden = true; });
      list.hidden = !opening;
      button.setAttribute("aria-expanded", opening ? "true" : "false");
    });
    return h("div", { class: "pill-menu" }, [button, hidden, list]);
  }

  function searchForm(filters, primary) {
    const input = h("input", {
      type: "search",
      name: "q",
      placeholder: "Search a model or part — try “Archon Type B”",
      "aria-label": "Search a model or part",
      value: filters.q,
    });
    let inStock = !!filters.inStock;
    const stock = h("button", {
      type: "button",
      class: "pill",
      "aria-pressed": inStock ? "true" : "false",
      text: "In stock only",
    });
    stock.addEventListener("click", function () {
      inStock = !inStock;
      stock.setAttribute("aria-pressed", inStock ? "true" : "false");
    });
    const priceKey = (filters.minPrice || "0") + ":" + (filters.maxPrice || "30000");
    const price = pillMenu("price", "Price", priceKey, [
      ["0:30000", "any, up to R 30 000"],
      ["0:25000", "up to R 25 000"],
      ["0:10000", "up to R 10 000"],
      ["20000:30000", "from R 20 000"],
    ]);
    const sort = pillMenu("sort", "Sort", filters.sort || "", [
      ["", "best match"],
      ["price_asc", "price low–high"],
      ["price_desc", "price high–low"],
    ]);
    const category = pillMenu("category", "Category", filters.category || "all", [
      ["all", "all"], ["Pistols", "pistols"], ["Sights", "optics"], ["Triggers", "triggers"],
      ["Magazines", "magazines"], ["Lights", "lights"], ["Holsters", "holsters"], ["Barrels", "barrels"], ["Parts", "parts"],
    ]);
    const form = h("form", { class: "search-form", role: "search", onsubmit: function (event) {
      event.preventDefault();
      const span = (form.querySelector("[name=price]").value || "0:30000").split(":");
      go(searchUrl({
        q: input.value.trim(),
        inStock: inStock,
        minPrice: span[0] || "0",
        maxPrice: span[1] || "30000",
        sort: form.querySelector("[name=sort]").value,
        category: form.querySelector("[name=category]").value,
        view: filters.view || "list",
      }));
    } }, [
      h("div", { class: "search-row" }, [
        input,
        h("button", { class: primary ? "primary" : "ghost", type: "submit", text: "Search" }),
      ]),
      h("div", { class: "filter-row" }, [stock, price, sort, category]),
    ]);
    return form;
  }

  function askBox(productId) {
    const input = h("input", { type: "text", name: "question", "aria-label": "Ask about this catalogue", placeholder: "Ask about a spec in the catalogue" });
    const out = h("div", { "aria-live": "polite" });
    const form = h("form", { class: "ask", onsubmit: async function (event) {
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
      input,
      h("button", { type: "submit", class: "ghost ask-go", "aria-label": "Ask", text: "→" }),
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
      ? tally(results.length, "match", "matches") + " · " + tally((body.groups || []).length, "category", "categories")
      : "No matches";
    const tabs = viewTabs(filters);
    let messageTitle = "";
    if (body.message && body.honest === "closest") {
      messageTitle = /colour/.test(body.message) ? "That colour isn't offered." : "No exact match.";
    } else if (body.message && body.honest === "not_stocked") messageTitle = "We don’t stock that.";
    else if (body.message && body.honest === "exact") messageTitle = "Out of stock.";
    else if (body.message) messageTitle = "Nothing matches that yet.";
    const message = body.message ? banner(messageTitle, body.message) : null;
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
    } else if (filters.view === "compare") main = null;
    else if (filters.view === "visual") main = visualView(body, focus);
    else main = listView(results, body.fits || []);
    const stockAlternative = focus && focus.alternative && body.honest === "exact" && body.message;
    const openTarget = stockAlternative ? focus.alternative : focus;
    const open = openTarget
      ? h("a", {
          class: "primary sticky-action",
          href: "/cn/product/" + encodeURIComponent(openTarget.id),
          text: (body.honest === "closest" ? "Show " : "Open ") + openTarget.name,
        })
      : null;
    return h("section", { class: "results" }, [
      searchForm(filters, false),
      h("div", { class: "results-head" }, [
        h("h1", { class: "results-title", text: heading }),
        tabs,
      ]),
      message,
      h("div", { class: filters.view === "compare" ? "layout compare-only" : "layout" }, [
        filters.view === "compare" ? compareView(results, open) : main,
        filters.view === "compare" ? null : sidebar(results, focus, open, body.focus_id || (focus && focus.id) || ""),
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

  function listView(results) {
    const pistols = results.filter(function (item) { return item.category === "Pistols"; });
    const rest = results.filter(function (item) { return item.category !== "Pistols"; });
    const wrap = h("div", { class: "list" });
    if (pistols.length) {
      wrap.append(h("h2", { class: "section-label", text: "Pistols · " + pistols.length }));
      pistols.forEach(function (item) { wrap.append(compactRow(item, results)); });
    }
    if (rest.length && pistols.length) {
      wrap.append(h("h2", { class: "section-label", text: "Upgrades for your Type B · " + rest.length }));
      const dots = rest.filter(function (item) { return item.category === "Sights"; });
      if (dots.length) {
        const grid = h("div", { class: "upgrade-dots" });
        dots.forEach(function (item) { grid.append(dotCard(item, results)); });
        wrap.append(grid);
      }
      rest.filter(function (item) { return item.category !== "Sights"; }).forEach(function (item) {
        wrap.append(compactRow(item, results));
      });
    } else if (rest.length) {
      let category = "";
      rest.forEach(function (item) {
        if (item.category !== category) {
          category = item.category;
          wrap.append(h("h2", { class: "section-label", text: category }));
        }
        wrap.append(compactRow(item, results));
      });
    }
    return wrap;
  }

  function optionPills(item) {
    const picks = loadPicks(item);
    const groups = [
      ["slide_grip", picks.slide_grip],
      ["grip", picks.grip],
      ["barrel", picks.barrel],
      ["optic_cut", picks.optic_cut],
    ];
    const wrap = h("div", { class: "mini-pills" });
    groups.forEach(function (pair) {
      optionValues(item, pair[0]).forEach(function (value) {
        const code = typeof value === "string" ? value : value.code;
        const label = typeof value === "string" ? value : value.label;
        const on = pair[1] === code;
        wrap.append(h("button", {
          type: "button",
          class: "chip tiny" + (on ? " on" : ""),
          "aria-pressed": on ? "true" : "false",
          text: label,
          onclick: function () {
            const next = loadPicks(item);
            if (pair[0] === "grip") next.grip = code;
            else next[pair[0]] = code;
            savePicks(item.id, next);
            go(location.pathname + location.search);
          },
        }));
      });
    });
    return wrap;
  }

  function compactRow(item, results) {
    const stock = stockOf(item.availability);
    const delta = peerDelta(item, results);
    const badges = (item.badges || []).filter(function (badge) {
      return badge !== "Demo item" && badge !== "Cheapest";
    });
    const shown = [];
    if (delta === 0) shown.push("Cheapest");
    if (badges[0]) shown.push(badges[0]);
    const price = h("div", { class: "price-col" }, [
      h("strong", { text: rand(displayAmount(item, loadPicks(item))) }),
      delta > 0 ? h("span", { class: "meta", text: "+" + rand(delta) }) : null,
    ].concat(shown.map(function (badge) { return h("span", { class: "badge", text: badge }); })));
    const name = h("div", {}, [
      h("h3", {}, [h("a", { class: "name-link", href: "/cn/product/" + encodeURIComponent(item.id), text: item.name })]),
      h("p", { class: "meta", text: item.brand || "" }),
    ]);
    const avail = h("div", {}, [
      h("p", { class: stock.tone, text: stock.label }),
      h("p", { class: "meta", text: stockDetail(stock) }),
      item.availability && item.availability.status === "out_of_stock" ? h("button", {
        type: "button",
        class: "chip tiny",
        text: "Notify me",
        onclick: function () {
          openDialog("Notify me", [
            h("p", { text: "This demo does not send alerts. " + CN.name + " can confirm stock for " + item.name + " at " + CN.email + "." }),
          ]);
        },
      }) : null,
    ]);
    return h("article", { class: "row-line" }, [name, optionPills(item), avail, price]);
  }

  function dotCard(item, results) {
    const stock = stockOf(item.availability);
    const delta = peerDelta(item, results || []);
    return h("article", { class: "dot-card" }, [
      h("h3", {}, [h("a", { class: "name-link", href: "/cn/product/" + encodeURIComponent(item.id), text: item.name })]),
      h("p", { class: "price", text: rand(item.price.amount) }),
      delta === 0 ? h("span", { class: "badge", text: "Cheapest" }) : null,
      item.fit ? h("span", { class: "chip tiny" + (item.fit.fits ? " on" : ""), text: item.fit.badge }) : null,
      h("p", { class: stock.tone, text: stock.label }),
      item.availability && item.availability.status === "out_of_stock" ? h("button", {
        type: "button",
        class: "chip tiny",
        text: "Notify me",
        onclick: function () {
          openDialog("Notify me", [h("p", { text: "This demo does not send alerts. " + CN.name + " can confirm stock for " + item.name + "." })]);
        },
      }) : null,
    ]);
  }

  function compareView(results, open) {
    const pistols = results.filter(function (item) { return item.category === "Pistols"; });
    const rows = pistols.length >= 2 ? pistols : results.slice(0, 3);
    const missing = "—";
    const lines = [
      ["Difference from cheapest", function (item) {
        const delta = peerDelta(item, rows);
        if (delta === null || delta === 0) return "Cheapest";
        return "+" + rand(delta);
      }],
      ["Availability", function (item) { return stockOf(item.availability).label; }],
      ["Where it is", function (item) { return stockOf(item.availability).where || missing; }],
      ["Lead time", function (item) { return stockOf(item.availability).lead || missing; }],
      ["Lockup", function (item) { return specValue(item.attributes && item.attributes.verified, "locking") || missing; }],
      ["Barrel", function (item) { return specValue(item.attributes && item.attributes.verified, "barrel") || missing; }],
      ["Optic cuts", function (item) { return specValue(item.attributes && item.attributes.verified, "optic_cuts") || ((item.options && item.options.optic_cut) || []).join(", ") || missing; }],
      ["Colours", function (item) { return ((item.options && (item.options.slide_grip || item.options.grip)) || []).join(", ") || missing; }],
      ["In the box", function (item) { return specValue(item.attributes && item.attributes.verified, "in_box") || (item.attributes && item.attributes.in_box) || missing; }],
    ];
    const board = h("div", { class: "compare-board", style: "--cols:" + rows.length });
    board.append(h("div", { class: "compare-label" }, [h("h2", { text: "Comparing " + rows.length + (rows.length === 1 ? " result" : " pistols") })]));
    rows.forEach(function (item, index) {
      const stock = stockOf(item.availability);
      const detail = stockDetail(stock);
      const card = h("article", { class: "compare-card" + (index === 0 ? " is-focus" : "") }, [
        h("h3", {}, [h("a", { class: "name-link", href: "/cn/product/" + encodeURIComponent(item.id), text: item.name })]),
        h("p", { class: "price", text: rand(item.price.amount) }),
        h("p", { class: stock.tone, text: stock.label + (detail ? " · " + detail : "") }),
      ]);
      if (index === 0 && open) card.append(open);
      board.append(card);
    });
    lines.forEach(function (line) {
      board.append(h("div", { class: "compare-label" }, [h("p", { text: line[0] })]));
      rows.forEach(function (item) {
        board.append(h("div", { class: "compare-cell" }, [h("p", { text: line[1](item) })]));
      });
    });
    return h("div", { class: "compare-wrap" }, [
      board,
      h("p", { class: "note", text: "A dash means that spec is not in the catalogue." }),
    ]);
  }

  function visualView(body, focus) {
    const items = (body.results || []).map(function (item) {
      const stock = stockOf(item.availability);
      return {
        id: item.id,
        name: item.name,
        category: item.category,
        meta: rand(item.price.amount) + " · " + stock.label + (item.fit && item.fit.badge ? " · " + item.fit.badge : ""),
      };
    });
    const groups = body.groups || [];
    const narrow = window.matchMedia("(max-width: 800px)").matches;
    const pitch = 96;
    let height = narrow ? 108 + 28 : 32;
    groups.forEach(function (group) {
      const n = items.filter(function (item) { return item.category === group.category; }).length;
      if (narrow) height += 58 + 16 + n * pitch + 12;
      else height += Math.max(pitch, n * pitch) + 20;
    });
    if (!narrow) height += 48;
    return h("div", {
      class: "flow flow-wide",
      style: "height:" + height + "px",
      "data-flow": JSON.stringify({
        layout: "columns",
        centre: focus ? focus.name : "Results",
        caption: (body.results || []).length + " results, same list as a map",
        groups: body.groups || [],
        items: items,
      }),
      "aria-label": "Results as a graph",
    });
  }

  function priceBars(results) {
    const wrap = h("div", { class: "bars" });
    ["Pistols", "Sights"].forEach(function (category) {
      const rows = results.filter(function (item) { return item.category === category; });
      if (!rows.length) return;
      const peak = Math.max.apply(null, rows.map(function (item) { return Number(item.price.amount) || 1; }));
      const low = Math.min.apply(null, rows.map(function (item) { return Number(item.price.amount) || 0; }));
      wrap.append(h("h3", { text: category === "Sights" ? "Red dots" : category }));
      rows.forEach(function (item) {
        const amount = Number(item.price.amount) || 0;
        const width = Math.max(8, Math.round((amount / peak) * 100));
        const delta = rows.length > 1 ? amount - low : null;
        const note = delta === null ? "" : delta > 0 ? " +" + rand(delta) : " cheapest";
        wrap.append(h("div", { class: "bar-row" }, [
          h("span", { class: "bar-name", text: item.name }),
          h("span", { class: "bar", style: "width:" + width + "%" }),
          h("span", { class: "meta", text: rand(amount) + note }),
        ]));
      });
    });
    return wrap;
  }

  function sidebar(results, focus, open, askId) {
    const bars = priceBars(results);
    const side = h("aside", { class: "side" });
    if (bars.childNodes.length) {
      side.append(h("h2", { text: "Price comparison" }));
      side.append(bars);
    }
    if (focus && focus.price_history) {
      const history = focus.price_history;
      side.append(h("h3", { text: "Price history" }));
      side.append(h("p", { text: focus.name + " was " + rand(history.was) + ", now " + rand(history.amount) + " on " + history.on + ". " + (history.label || "Demo data") + "." }));
    }
    side.append(h("h2", { text: "Ask about these results" }));
    side.append(askBox(askId || (focus && focus.id) || "ARCHON-TYPE-B"));
    if (open) side.append(open);
    return side;
  }

  async function viewProduct(id) {
    const detail = await api("/v1/rig/products/" + encodeURIComponent(id));
    const rows = await catalogue();
    const map = byId(rows);
    const picks = loadPicks(detail);
    const stock = stockOf(detail.availability);
    const verified = (detail.attributes && detail.attributes.verified) || [];
    const family = detail.family || detail.id;
    function redraw() {
      savePicks(detail.id, picks);
      go(location.pathname);
    }
    const specs = h("dl", { class: "specs" });
    [
      ["Lockup", specValue(verified, "locking")],
      ["Action", specValue(verified, "action")],
      ["Calibre", specValue(verified, "caliber")],
      ["Barrel", specValue(verified, "barrel")],
      ["Weight", specValue(verified, "weight_oz") ? specValue(verified, "weight_oz") + " oz" : ""],
      ["Length", specValue(verified, "length_in") ? specValue(verified, "length_in") + " in" : ""],
      ["Rail", specValue(verified, "rail")],
    ].forEach(function (spec) {
      if (!spec[1]) return;
      specs.append(h("dt", { text: spec[0] }), h("dd", { text: spec[1] }));
    });
    const linked = (detail.fits || []).filter(function (fit) {
      return fit.fits_family === family || fit.fits_sku === detail.id || fit.fits_sku === family;
    }).map(function (fit) { return map[fit.part_sku]; }).filter(Boolean);
    const fitChips = h("div", { class: "fit-chips" });
    linked.forEach(function (part) {
      const fit = fitFor(part.id, picks.optic_cut, detail.fits || [], family);
      const partStock = stockOf(part.availability);
      const fits = fit ? fit.fits : true;
      fitChips.append(h("span", {
        class: "chip tiny" + (fits ? " on" : ""),
        text: (fit ? fit.badge : "Check fit") + " · " + partStock.label,
      }));
    });
    const stills = [
      ["/page/cn/media/type-b-render.jpg", "Type B render, muzzle left"],
      ["/page/cn/media/type-b-photo.jpg", "Type B studio photo"],
      ["/page/cn/media/grip.jpg", "Modular grip"],
      ["/page/cn/media/trigger.jpg", "Flat face trigger"],
    ];
    const choices = [];
    const grips = optionValues(detail, "slide_grip").length ? optionValues(detail, "slide_grip") : optionValues(detail, "grip");
    if (grips.length) choices.push(radioGroup("Colour", "colour", grips, picks.slide_grip || picks.grip, function (value) { picks.slide_grip = value; redraw(); }));
    const barrels = optionValues(detail, "barrel");
    if (barrels.length) {
      choices.push(radioGroup("Barrel", "barrel", barrels.map(function (barrel) {
        return { code: barrel.code, label: barrel.label + (barrel.delta ? " +" + rand(barrel.delta) : "") };
      }), picks.barrel, function (value) { picks.barrel = value; redraw(); }));
    }
    const cuts = optionValues(detail, "optic_cut");
    if (cuts.length) choices.push(radioGroup("Optic cut", "cut", cuts, picks.optic_cut, function (value) { picks.optic_cut = value; redraw(); }));
    const options = choices.length || linked.length ? h("div", { class: "product-options" }, [
      choices.length ? h("h2", { text: "Choose your options" }) : null,
    ].concat(choices).concat(linked.length ? [h("h2", { text: "Fits" }), fitChips] : [])) : null;
    const peers = h("div", { class: "search-compare" }, [h("h2", { text: "Compare in this search" })]);
    const same = rows.filter(function (item) { return item.category === detail.category; });
    same.forEach(function (item) {
      const peerStock = stockOf(item.availability);
      const delta = peerDelta(item, same);
      const mark = item.id === detail.id ? "This one" : delta > 0 ? "+" + rand(delta) : delta === 0 ? "Cheapest" : "";
      peers.append(h("p", {}, [
        h("a", { class: "name-link", href: "/cn/product/" + encodeURIComponent(item.id), text: item.name }),
        h("span", { class: "meta", text: " " + rand(item.price.amount) + " · " + peerStock.label + (mark ? " · " + mark : "") }),
      ]));
    });
    const summary = h("div", { class: "product-summary" }, [
      h("p", { class: "meta", text: detail.brand || "" }),
      h("h1", { text: detail.name }),
      detail.attributes && detail.attributes.tagline ? h("p", { class: "lede", text: detail.attributes.tagline }) : null,
      priceLine(displayAmount(detail, picks), "Demo price"),
      h("p", { class: stock.tone, text: stock.label + (stockDetail(stock) ? " · " + stockDetail(stock) : "") }),
      peers,
    ]);
    if (detail.price_history) {
      const history = detail.price_history;
      summary.append(h("h2", { text: "Price history" }), h("p", { text: "Was " + rand(history.was) + ". Now " + rand(history.amount) + " on " + history.on + "." }));
    }
    if (detail.attributes && detail.attributes.in_box) summary.append(h("h2", { text: "In the box" }), h("p", { text: detail.attributes.in_box }));
    summary.append(h("a", { class: "primary sticky-action", href: "/cn/build/" + encodeURIComponent(detail.id), text: detail.category === "Pistols" ? "Build this pistol" : "Reserve this part" }));
    const coming = String(detail.image || "").indexOf("photo-coming") >= 0;
    const routeFilters = filtersFrom(new URLSearchParams(location.search));
    return h("article", { class: "product-page" }, [
      searchForm(routeFilters, false),
      h("div", { class: "product" }, [
        h("div", { class: "product-media" }, [
          h("img", { class: "hero", src: detail.image, alt: coming ? "Photo coming" : detail.name }),
          coming ? h("p", { class: "photo-coming", text: "Photo coming" }) : null,
          detail.id === "ARCHON-TYPE-B" ? h("div", { class: "stills" }, stills.map(function (still) {
            return h("figure", {}, [h("img", { src: still[0], alt: still[1] }), h("figcaption", { text: still[1] })]);
          })) : null,
          specs,
        ]),
        options,
        summary,
      ]),
      h("h2", { text: "Ask about this" }),
      askBox(detail.id),
    ]);
  }

  async function viewBuild(id) {
    const detail = await api("/v1/rig/products/" + encodeURIComponent(id));
    const rows = await catalogue();
    const map = byId(rows.concat([detail]));
    const picks = loadPicks(detail);
    const lines = linesFor(detail, picks, map);
    const total = sum(lines);
    const family = detail.family || detail.id;
    const linked = (detail.fits || []).map(function (fit) { return map[fit.part_sku]; }).filter(function (row) {
      return row && (detail.fits || []).some(function (fit) {
        return fit.part_sku === row.id && (fit.fits_family === family || fit.fits_sku === detail.id || fit.fits_sku === family);
      });
    });
    function choiceFor(row) {
      const fit = fitFor(row.id, picks.optic_cut, detail.fits || [], family);
      const partStock = stockOf(row.availability);
      const blocked = (fit && fit.fits === false) || partStock.status === "out_of_stock";
      return {
        code: row.id,
        disabled: blocked,
        fits: !!(fit && fit.fits),
        name: row.name,
        price: rand(row.price.amount),
        badge: fit ? fit.badge : "Check fit",
        stock: partStock.label,
        tone: partStock.tone,
        label: row.name,
      };
    }
    const dots = linked.filter(function (row) { return row.category === "Sights"; });
    const dotChoices = dots.map(choiceFor);
    const pickedBlocked = dotChoices.some(function (choice) { return choice.code === picks.dot && choice.disabled; });
    const mags = linked.filter(function (row) { return row.category === "Magazines"; });
    const triggers = linked.filter(function (row) { return row.category === "Triggers"; });
    function redraw(key, value) { picks[key] = value; savePicks(detail.id, picks); go(location.pathname); }
    const steps = [
      ["0:00", "/page/cn/media/frame-a.jpg", "Base pistol, flush barrel"],
      ["0:06", "/page/cn/media/frame-c.jpg", "Threaded barrel, suppressor ready"],
      ["0:15", "/page/cn/media/still-s2.jpg", "Optics ready"],
      ["0:27", "/page/cn/media/grip.jpg", "Interchangeable grip textures"],
      ["0:41", "/page/cn/media/still-up.jpg", "Modular grip"],
    ];
    const list = h("ol", { class: "lines" });
    lines.forEach(function (line) {
      const fit = fitFor(line.product.id, picks.optic_cut, detail.fits || [], family);
      const partStock = stockOf(line.product.availability);
      list.append(h("li", {}, [
        h("span", { text: line.product.name }),
        h("span", { class: "meta", text: rand(line.product.price.amount) + " · " + (fit ? fit.badge : "Included") + " · " + partStock.label }),
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
      pickedBlocked ? h("p", { class: "note", text: "That red dot needs a different cut, or it is out of stock. Pick one that fits before reserving." }) : null,
      h("button", {
        class: "primary sticky-action",
        type: "submit",
        disabled: pickedBlocked ? true : null,
        text: "Reserve at " + CN.name,
      }),
      status,
    ]);
    const frames = h("div", { class: "frame-strip" });
    steps.forEach(function (step, index) {
      frames.append(h("figure", {}, [
        h("img", { src: step[1], alt: step[2] }),
        h("figcaption", { text: (index + 1) + " " + step[2] }),
      ]));
    });
    return h("article", { class: "build" }, [
      h("div", { class: "build-stage" }, [
        h("p", { class: "meta", text: "Results · " + detail.name + " · Your build" }),
        h("h1", { text: "Your " + detail.name + " build" }),
        h("img", { class: "hero-still", src: "/page/cn/media/still-up.jpg", alt: "Type B with optic and modular grip, Versatility video at about 41 seconds" }),
        frames,
      ]),
      h("aside", { class: "side build-side" }, [
        h("h2", { text: "Your build" }),
        h("p", { class: "gold", text: "Demo prices" }),
        list,
        h("p", { class: "meta", text: "Running total" }),
        h("p", { class: "total", text: rand(total) }),
        dots.length ? optionCards("Red dot options", dotChoices, picks.dot, function (value) { redraw("dot", value); }) : null,
        mags.length ? optionCards("Magazine", mags.map(choiceFor), picks.mag, function (value) { redraw("mag", value); }) : null,
        triggers.length ? radioGroup("Trigger", "trigger", [{ code: "standard", label: "Standard, included · In stock" }].concat(triggers.map(function (row) {
          const partStock = stockOf(row.availability);
          return { code: "performance", label: row.name + " · " + rand(row.price.amount) + " · Fits · " + partStock.label };
        })), picks.trigger, function (value) { redraw("trigger", value); }) : null,
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
      h("div", { class: "pills" }, [
        h("a", { class: "ghost", href: "mailto:" + CN.email, text: "Email " + CN.name }),
        h("a", { class: "ghost", href: "/cn", text: "Ask another question" }),
        h("button", { type: "button", class: "ghost", text: "Clear search", onclick: function () { go("/cn"); } }),
      ]),
    ]);
  }

  const menuToggle = document.getElementById("menu-toggle");
  const shopNav = document.getElementById("shop-nav");
  if (menuToggle && shopNav) {
    menuToggle.addEventListener("click", function () {
      const open = shopNav.classList.toggle("open");
      menuToggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
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
