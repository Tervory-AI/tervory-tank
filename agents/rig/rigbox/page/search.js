const form = document.querySelector("form.search");
const query = document.querySelector("#q");
const status = document.querySelector("#status");
const results = document.querySelector("#results");

form.addEventListener("submit", (event) => {
  event.preventDefault();
  void run(query.value.trim());
});

async function run(q) {
  results.replaceChildren();
  if (!q) {
    status.textContent = "Type a name to search.";
    return;
  }
  status.textContent = "Searching…";
  const params = new URLSearchParams({ q, limit: "12" });
  let response;
  try {
    response = await fetch("/v1/rig/search?" + params.toString(), {
      headers: {
        Accept: "application/json",
        "X-Rig-Key": window.RIG_KEY || "",
      },
    });
  } catch {
    status.textContent = "Search did not complete. Try again.";
    return;
  }
  if (!response.ok) {
    status.textContent = "Search did not complete. Try again.";
    return;
  }
  const body = await response.json();
  const items = Array.isArray(body.results) ? body.results : [];
  if (items.length === 0) {
    status.textContent = "Nothing matched that search.";
    return;
  }
  status.textContent = items.length === 1 ? "1 product" : items.length + " products";
  for (const item of items) {
    results.append(card(item));
  }
}

function card(item) {
  const row = document.createElement("li");
  row.className = "card";
  const name = document.createElement("h2");
  name.textContent = item.name || "";
  const meta = document.createElement("p");
  meta.className = "meta";
  meta.textContent = [item.brand, item.category].filter(Boolean).join(" · ");
  const price = document.createElement("p");
  price.className = "price";
  price.textContent = priceLine(item.price);
  row.append(name, meta, price);
  return row;
}

function priceLine(price) {
  if (!price || price.amount == null) return "";
  const value = Number(price.amount);
  const amount = Number.isFinite(value)
    ? value.toLocaleString("en-ZA", { maximumFractionDigits: 2 })
    : String(price.amount);
  return price.currency ? amount + " " + price.currency : amount;
}
