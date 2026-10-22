/**
 * Loads the shared shell at phone width and checks every signed-in route.
 * Set SHELL_SHOTS=1 to write docs/screenshots/shell-1/.
 */
import { actualShellHtml } from "./shell_popout.ts";
import { spawn, type ChildProcess } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readFile, realpath, rm, writeFile } from "node:fs/promises";
import { createServer } from "node:http";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import { extname, join, resolve, sep } from "node:path";
import {
  FOUNDER_LINKS,
  REST_LINKS,
  REVIEW_LINK,
  SHELL_ROUTES,
  TOP_LINKS,
  linkIsCurrent,
  logoWidth,
  pageSection,
  squadMembers,
  type NavLink,
  type SquadMember,
} from "../workspace/app/product-nav.ts";

const ROOT = new URL("..", import.meta.url);
const CSS = new URL("workspace/app/globals.css", ROOT);
const BRAND = new URL("workspace/public/", ROOT);
const SHOTS = new URL("docs/screenshots/shell-1/", ROOT);

const TITLES: Record<string, string> = {
  "/": "Dashboard",
  "/matters": "Matters",
  "/tasks": "Tasks",
  "/ledger": "Ledger",
  "/billing": "Billing",
  "/prices": "Prices",
  "/data": "Data",
  "/onboarding": "Get started",
  "/base": "Base",
  "/tiger": "Tiger",
  "/market-lab": "Market Lab",
  "/rig": "Rig",
  "/tisan": "Tisan",
  "/radix": "Radix",
  "/zenas": "Zenas",
  "/skala": "Skala",
  "/skala/gold": "Squad training",
  "/tank": "Tank",
  "/admin": "Admin",
  "/admin/feeds": "Feeds",
  "/admin/homes": "Homes",
  "/zenas/feeds": "Law feeds",
  "/review": "Review",
};

function chromePath(): string {
  const candidates = [
    process.env.CHROME_PATH,
    "/opt/google/chrome/chrome",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
  ].filter((item): item is string => Boolean(item));
  const found = candidates.find((item) => existsSync(item));
  if (!found) throw new Error(`Chrome was not found. Looked in ${candidates.join(", ")}`);
  return found;
}

function fileUrl(url: URL): string {
  return url.href;
}

function brandSrc(logo: string): string {
  return fileUrl(new URL(logo.replace(/^\//, ""), BRAND));
}

function linkHtml(link: NavLink, route: string): string {
  const current = linkIsCurrent(link.href, route, "", "");
  const external = link.href.startsWith("http");
  if (external) {
    return `<a href="${link.href}" target="_blank" rel="noreferrer">${link.label}<span class="shell-sr"> (opens a new tab)</span></a>`;
  }
  return `<a href="${link.href}"${current ? ' aria-current="page"' : ""}>${link.label}</a>`;
}

function memberHtml(member: SquadMember, route: string): string {
  const here = route === member.href || (member.href !== "/" && route.startsWith(`${member.href}/`));
  const width = logoWidth(member, 40);
  return `<li><a href="${member.href}" data-squad-member=""${here ? ' aria-current="page"' : ""}>
    <img src="${brandSrc(member.logo)}" alt="" width="${width}" height="40" />
    <span class="shell-member-name">${member.label}</span>
    <span class="shell-member-job">${member.job}</span>
  </a></li>`;
}

export function shellHtml(route: string, founder: boolean, reviewer: boolean): string {
  const section = pageSection(route, founder, reviewer);
  const title = TITLES[route] ?? "Tervory";
  const members = squadMembers(founder);
  const own = section
    ? `<nav class="shell-nav shell-own" aria-label="${section.title}"><p class="shell-kicker">${section.title}</p>${section.links.map((link) => linkHtml(link, route)).join("")}</nav>`
    : "";
  const founderLinks = founder ? FOUNDER_LINKS.map((link) => linkHtml(link, route)).join("") : "";
  const review = reviewer ? linkHtml(REVIEW_LINK, route) : "";
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>${title}</title>
  <link rel="stylesheet" href="${fileUrl(CSS)}" />
</head>
<body>
  <div class="app-shell product">
    <a class="shell-skip" href="#shell-content">Skip to content</a>
    <header class="shell-mobile">
      <img src="${brandSrc("/brand/tervory-logo-reversed.png")}" alt="Tervory" width="218" height="40" />
      <button type="button" class="shell-menu" id="shell-menu" aria-expanded="false" aria-controls="app-sidebar">Menu</button>
    </header>
    <aside id="app-sidebar" class="shell-side" aria-label="Sidebar">
      <div class="shell-brand">
        <img src="${brandSrc("/brand/tervory-logo-reversed.png")}" alt="Tervory" width="218" height="40" />
        <button type="button" class="shell-side-close" id="shell-side-close">Close</button>
      </div>
      <p class="shell-account">Your account</p>
      <nav class="shell-nav" aria-label="Workspace">
        ${TOP_LINKS.map((link) => linkHtml(link, route)).join("")}
        <div class="shell-squad">
          <button type="button" class="shell-squad-button" id="squad-button" aria-expanded="false" aria-controls="squad-popout" aria-haspopup="dialog">Squad</button>
        </div>
      </nav>
      ${own}
      <div class="shell-spacer"></div>
      <nav class="shell-nav" aria-label="Account">
        ${REST_LINKS.map((link) => linkHtml(link, route)).join("")}
        ${review}
        ${founderLinks}
      </nav>
    </aside>
    <div id="shell-content" class="shell-main"><main><h1>${title}</h1><p>Signed-in workspace.</p></main></div>
  </div>
  <div id="squad-popout" class="shell-pop" role="dialog" aria-modal="true" aria-label="Squad" hidden>
    <div class="shell-pop-head">
      <p class="shell-kicker">Squad</p>
      <button type="button" class="shell-pop-close" id="squad-close">Close</button>
    </div>
    <ul class="shell-members">${members.map((member) => memberHtml(member, route)).join("")}</ul>
  </div>
  <script>
    const button = document.getElementById("squad-button");
    const pop = document.getElementById("squad-popout");
    const side = document.getElementById("app-sidebar");
    const menu = document.getElementById("shell-menu");
    function setOpen(open) {
      button.setAttribute("aria-expanded", open ? "true" : "false");
      pop.hidden = !open;
      if (open) pop.querySelector("[data-squad-member]")?.focus();
      else button.focus();
    }
    button.addEventListener("click", () => setOpen(button.getAttribute("aria-expanded") !== "true"));
    document.getElementById("squad-close").addEventListener("click", () => setOpen(false));
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && button.getAttribute("aria-expanded") === "true") {
        event.preventDefault();
        setOpen(false);
      }
    });
    pop.addEventListener("keydown", (event) => {
      const nodes = [...pop.querySelectorAll("[data-squad-member]")];
      const index = nodes.indexOf(document.activeElement);
      if (event.key === "ArrowDown" && nodes.length) {
        event.preventDefault();
        nodes[index < 0 ? 0 : (index + 1) % nodes.length].focus();
      }
      if (event.key === "ArrowUp" && nodes.length) {
        event.preventDefault();
        nodes[index <= 0 ? nodes.length - 1 : index - 1].focus();
      }
    });
    document.addEventListener("pointerdown", (event) => {
      if (pop.hidden) return;
      if (pop.contains(event.target) || button.contains(event.target)) return;
      setOpen(false);
    });
    menu.addEventListener("click", () => {
      side.classList.add("open");
      menu.setAttribute("aria-expanded", "true");
    });
    document.getElementById("shell-side-close").addEventListener("click", () => {
      side.classList.remove("open");
      menu.setAttribute("aria-expanded", "false");
      menu.focus();
    });
  </script>
</body>
</html>`;
}

type CdpResult = { result?: { value?: unknown }; exceptionDetails?: unknown; data?: string };

class Cdp {
  private next = 0;
  private pending = new Map<number, { resolve: (value: CdpResult) => void; reject: (error: Error) => void }>();
  private ws: WebSocket;

  constructor(ws: WebSocket) {
    this.ws = ws;
    ws.addEventListener("message", (event) => {
      const message = JSON.parse(String(event.data)) as { id?: number; result?: CdpResult; error?: { message: string } };
      if (!message.id || !this.pending.has(message.id)) return;
      const waiter = this.pending.get(message.id)!;
      this.pending.delete(message.id);
      if (message.error) waiter.reject(new Error(message.error.message));
      else waiter.resolve(message.result ?? {});
    });
  }

  send(method: string, params: object = {}): Promise<CdpResult> {
    const id = ++this.next;
    return new Promise((resolve, reject) => {
      const timeout = setTimeout(() => { this.pending.delete(id); reject(new Error(`Chrome timed out: ${method}`)); }, 15000);
      this.pending.set(id, {
        resolve: result => { clearTimeout(timeout); resolve(result); },
        reject: error => { clearTimeout(timeout); reject(error); },
      });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }
}

async function waitJson(url: string, proc: ChildProcess): Promise<unknown> {
  const started = Date.now();
  while (Date.now() - started < 15000) {
    if (proc.exitCode !== null) throw new Error("Chrome exited before the debugging port opened");
    try {
      const response = await fetch(url);
      if (response.ok) return await response.json();
    } catch {
      // Chrome is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("Chrome did not open a debugging port");
}

async function evaluate<T>(cdp: Cdp, expression: string): Promise<T> {
  const result = await cdp.send("Runtime.evaluate", { expression, returnByValue: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result?.value as T;
}

async function navigate(cdp: Cdp, url: string): Promise<void> {
  await cdp.send("Page.navigate", { url });
  const started = Date.now();
  while (Date.now() - started < 8000) {
    const state = await evaluate<string>(cdp, `location.href === ${JSON.stringify(url)} ? document.readyState : "loading"`);
    if (state === "complete" && (await evaluate<boolean>(cdp, "Boolean(document.getElementById('squad-button'))"))) return;
    await new Promise((resolve) => setTimeout(resolve, 40));
  }
  throw new Error(`Page did not load ${url}`);
}

async function setViewport(cdp: Cdp, width: number, height: number): Promise<void> {
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: width < 800,
  });
}

async function shot(cdp: Cdp, name: string): Promise<void> {
  if (process.env.SHELL_SHOTS !== "1") return;
  const folder = fileUrl(SHOTS).replace("file://", "");
  await mkdir(folder, { recursive: true });
  const image = await cdp.send("Page.captureScreenshot", { format: "png" });
  const bytes = Buffer.from(image.data ?? "", "base64");
  if (bytes.length > 1_000_000) throw new Error(`${name} is ${bytes.length} bytes`);
  await writeFile(join(folder, name), bytes);
}

function slug(route: string): string {
  if (route === "/") return "home";
  return route.replace(/^\//, "").replace(/\//g, "-");
}

async function main(): Promise<void> {
  const failures: string[] = [];
  const executable = chromePath();
  const dir = await mkdtemp(join(tmpdir(), "shell-nav-"));
  // Serve only generated fixtures and their repository assets. Managed cloud
  // browsers can prohibit file:// navigation; HTTP exercises the same DOM and
  // font/layout assertions without changing browser security policy.
  const fixtures = new Map<string, string>();
  const workspaceRoot = await realpath(fileURLToPath(new URL("workspace/", ROOT)));
  const fixtureServer = createServer(async (request, response) => {
    try {
      const path = decodeURIComponent(new URL(request.url ?? "/", "http://127.0.0.1").pathname);
      if (fixtures.has(path)) {
        response.writeHead(200, { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" });
        response.end(fixtures.get(path));
        return;
      }
      const asset = path.startsWith("/workspace/") ? path.slice("/workspace/".length) : "";
      if (asset !== "app/globals.css" && !asset.startsWith("public/brand/") && !asset.startsWith("app/fonts/")) {
        response.writeHead(404).end(); return;
      }
      const file = await realpath(resolve(workspaceRoot, asset));
      if (file !== join(workspaceRoot, "app/globals.css") &&
          !file.startsWith(join(workspaceRoot, "public/brand") + sep) &&
          !file.startsWith(join(workspaceRoot, "app/fonts") + sep)) {
        response.writeHead(404).end(); return;
      }
      const mime: Record<string, string> = { ".css": "text/css", ".woff2": "font/woff2", ".png": "image/png", ".svg": "image/svg+xml" };
      response.writeHead(200, { "content-type": mime[extname(file)] ?? "application/octet-stream" });
      response.end(await readFile(file));
    } catch { response.writeHead(404).end(); }
  });
  await new Promise<void>(resolve => fixtureServer.listen(0, "127.0.0.1", resolve));
  const address = fixtureServer.address();
  if (!address || typeof address === "string") throw new Error("Fixture server did not start");
  const fixtureOrigin = `http://127.0.0.1:${address.port}`;
  function fixtureUrl(name: string, html: string): string {
    const path = `/fixtures/${name}`;
    fixtures.set(path, html.replaceAll(new URL("workspace/", ROOT).href, `${fixtureOrigin}/workspace/`));
    return fixtureOrigin + path;
  }
  const port = 9400 + Math.floor(Math.random() * 400);
  const proc = spawn(executable, [
    "--headless=new",
    "--disable-gpu",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--hide-scrollbars",
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${join(dir, "profile")}`,
    "about:blank",
  ], { stdio: "ignore" });
  try {
    await waitJson(`http://127.0.0.1:${port}/json/version`, proc);
    const list = (await waitJson(`http://127.0.0.1:${port}/json/list`, proc)) as { type: string; webSocketDebuggerUrl: string }[];
    const page = list.find((item) => item.type === "page");
    if (!page) throw new Error("Chrome did not open a page");
    const ws = new WebSocket(page.webSocketDebuggerUrl);
    await new Promise<void>((resolve, reject) => {
      ws.addEventListener("open", () => resolve());
      ws.addEventListener("error", () => reject(new Error("Chrome socket failed")));
    });
    const cdp = new Cdp(ws);
    await cdp.send("Page.enable");
    await cdp.send("Runtime.enable");

    async function openRoute(route: string, founder: boolean, reviewer: boolean): Promise<void> {
      const name = `${slug(route)}-${founder ? "founder" : "customer"}.html`;
      await navigate(cdp, fixtureUrl(name, shellHtml(route, founder, reviewer)));
    }

    async function overflow(label: string): Promise<void> {
      const box = await evaluate<{ sw: number; cw: number; main: number; mainCw: number }>(cdp, `(() => { const main = document.querySelector('.shell-main'); return { sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, main: main.scrollWidth, mainCw: main.clientWidth }; })()`);
      if (box.sw > box.cw + 1) failures.push(`${label} scrolls sideways (${box.sw} > ${box.cw})`);
      if (box.main > box.mainCw + 1) failures.push(`${label} content is wider than the page (${box.main} > ${box.mainCw})`);
    }

    // Exercise the real React components, including their actual focus/keyboard effects.
    async function check(expression: string, message: string) {
      const until = Date.now() + 3000;
      while (Date.now() < until) {
        if (await evaluate<boolean>(cdp, expression)) return;
        await new Promise(resolve => setTimeout(resolve, 30));
      }
      failures.push(message);
    }
    async function click(selector: string) {
      await evaluate(cdp, `document.querySelector(${JSON.stringify(selector)}).click()`);
    }
    for (const width of [1440, 375]) {
      await setViewport(cdp, width, width === 1440 ? 900 : 812);
      await navigate(cdp, fixtureUrl(`actual-${width}.html`, actualShellHtml(true)));
      await check('!!document.getElementById("squad-popout")', "React portal did not mount");
      async function capture(state: string) {
        if (!process.env.SQUAD_SHOTS) return;
        await mkdir(process.env.SQUAD_SHOTS, {recursive:true});
        await cdp.send("Page.bringToFront");
        await cdp.send("Runtime.evaluate", {expression:"new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))",awaitPromise:true});
        const image = await cdp.send("Page.captureScreenshot", {format:"png"});
        await writeFile(join(process.env.SQUAD_SHOTS, `shell_${width}-${state}.png`), Buffer.from(image.data!, "base64"));
      }
      await cdp.send("Runtime.evaluate", {expression:"document.fonts.ready",awaitPromise:true});
      await capture("closed");
      if (width === 375) await click("#shell-menu");
      await click("#squad-button");
      await check('document.activeElement?.dataset.squadHref === "/base"', "Opening must focus current member");
      await check('document.querySelectorAll("[data-squad-member]").length === 9', "Founder must see nine members");
      await check('[...document.querySelectorAll(".squad-row img")].every(i=>i.complete && i.naturalWidth && i.getBoundingClientRect().height===22 && Math.abs(i.getBoundingClientRect().width / 22 - i.naturalWidth/i.naturalHeight)<.02)', "Logos must be loaded at equal 22px heights with original proportions");
      await check('[...document.querySelectorAll(".squad-row")].every(i=>i.getBoundingClientRect().height===56)', "Rows must be 56px");
      await check('[...document.querySelectorAll(".squad-job")].every(i=>i.scrollWidth<=i.clientWidth)', "Job descriptions must fit without clipping");
      if (width === 1440) await check('(()=>{const p=document.getElementById("squad-popout");return p.scrollHeight===p.clientHeight && p.getBoundingClientRect().width===360 && p.getBoundingClientRect().bottom<900})()', "Desktop founder panel must fit without scrolling");
      else await check('document.getElementById("squad-popout").getBoundingClientRect().height === innerHeight', "Mobile must be a full-height sheet");
      await check('getComputedStyle(document.querySelector(".squad-dim")).backgroundColor === "rgba(0, 24, 64, 0.3)"', "Dim must be navy at 30 percent");
      await check('(()=>{const b=document.querySelector(".squad-pop-close").getBoundingClientRect();return b.width===44 && b.height===44})()', "X must have a 44px target");
      await check('document.querySelector("[aria-current=page][data-squad-member]")?.getAttribute("aria-current") === "page"', "Current member must be highlighted");
      await capture("open");
      await cdp.send("Input.dispatchKeyEvent", {type:"keyDown",key:"ArrowDown",code:"ArrowDown",windowsVirtualKeyCode:40});
      await check('document.activeElement?.dataset.squadHref === "/tiger"', "ArrowDown must move to Tiger");
      await click('[aria-label="Close"]');
      await check('document.getElementById("squad-popout").hidden && document.activeElement.id === "squad-button"', "X must close and return focus");
      await click("#squad-button");
      await check('!document.getElementById("squad-popout").hidden', "Panel must reopen");
      await cdp.send("Input.dispatchKeyEvent", {type:"keyDown",key:"Escape",code:"Escape",windowsVirtualKeyCode:27});
      await check('document.getElementById("squad-popout").hidden && document.activeElement.id === "squad-button"', "Escape must close and return focus");
      if (width === 1440) {
        await click("#squad-button");
        await check('!!document.querySelector(".squad-dim")', "Dim must appear");
        await cdp.send("Input.dispatchMouseEvent", {type:"mousePressed",x:1000,y:400,button:"left",clickCount:1});
        await cdp.send("Input.dispatchMouseEvent", {type:"mouseReleased",x:1000,y:400,button:"left",clickCount:1});
        await check('document.getElementById("squad-popout").hidden && document.activeElement.id === "squad-button"', "Dim click must close and return focus");
      }
    }
    await navigate(cdp, fixtureUrl("actual-customer.html", actualShellHtml(false)));
    await check('!!document.getElementById("squad-popout")', "Customer portal must mount");
    await click("#squad-button");
    await check('document.querySelectorAll("[data-squad-member]").length===7 && !document.querySelector(".squad-platform")', "Customer must not see platform members");

    for (const route of process.env.SQUAD_ONLY ? [] : SHELL_ROUTES) {
      await setViewport(cdp, 375, 812);
      await openRoute(route, true, false);
      await overflow(`${route} 375 closed`);
      const menu = await evaluate<{ h: number; w: number }>(cdp, `(() => { const r = document.getElementById('shell-menu').getBoundingClientRect(); return { h: r.height, w: r.width }; })()`);
      if (menu.h < 44 || menu.w < 44) failures.push(`${route} menu tap target is ${menu.w}x${menu.h}`);
      await evaluate(cdp, `document.getElementById('shell-menu').click()`);
      const opened = await evaluate<boolean>(cdp, `document.getElementById('app-sidebar').classList.contains('open') && document.getElementById('shell-menu').getAttribute('aria-expanded') === 'true'`);
      if (!opened) failures.push(`${route} menu did not open`);
      await overflow(`${route} 375 menu`);
      await evaluate(cdp, `document.getElementById('shell-side-close').click()`);
      const closed = await evaluate<boolean>(cdp, `!document.getElementById('app-sidebar').classList.contains('open') && document.activeElement.id === 'shell-menu'`);
      if (!closed) failures.push(`${route} menu did not close`);
      await shot(cdp, `${slug(route)}-375-closed.png`);
      const before = await evaluate<number>(cdp, `document.getElementById('app-sidebar').getBoundingClientRect().height`);
      await evaluate(cdp, `document.getElementById('squad-button').click()`);
      const after = await evaluate<number>(cdp, `document.getElementById('app-sidebar').getBoundingClientRect().height`);
      if (Math.abs(before - after) > 1) failures.push(`${route} sidebar height changed from ${before} to ${after}`);
      const expanded = await evaluate<boolean>(cdp, `document.getElementById('squad-button').getAttribute('aria-expanded') === 'true' && document.getElementById('squad-popout').hidden === false`);
      if (!expanded) failures.push(`${route} Squad did not open`);
      const logo = await evaluate<number>(cdp, `document.querySelector(".shell-members img")?.naturalWidth || 0`);
      if (logo < 40) failures.push(`${route} squad logo did not load (naturalWidth ${logo})`);
      await overflow(`${route} 375 squad open`);
      await shot(cdp, `${slug(route)}-375-open.png`);

      await setViewport(cdp, 1440, 900);
      await openRoute(route, true, false);
      const wideBefore = await evaluate<number>(cdp, `document.getElementById('app-sidebar').getBoundingClientRect().height`);
      await shot(cdp, `${slug(route)}-1440-closed.png`);
      await evaluate(cdp, `document.getElementById('squad-button').click()`);
      const wideAfter = await evaluate<number>(cdp, `document.getElementById('app-sidebar').getBoundingClientRect().height`);
      if (Math.abs(wideBefore - wideAfter) > 1) failures.push(`${route} desktop sidebar height changed from ${wideBefore} to ${wideAfter}`);
      await shot(cdp, `${slug(route)}-1440-open.png`);
      await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", key: "Escape", code: "Escape", windowsVirtualKeyCode: 27 });
      const escaped = await evaluate<boolean>(cdp, `document.getElementById('squad-popout').hidden === true && document.activeElement && document.activeElement.id === 'squad-button'`);
      if (!escaped) failures.push(`${route} Escape did not close Squad`);
    }

    await setViewport(cdp, 1440, 900);
    await openRoute("/ledger", false, false);
    await evaluate(cdp, `document.getElementById('squad-button').click()`);
    const names = await evaluate<string>(cdp, `document.getElementById('squad-popout').innerText`);
    if (names.includes("Skala") || names.includes("Tank")) failures.push("A customer Squad list includes Skala or Tank");
    for (const name of ["Base", "Tiger", "Market Lab", "Rig", "Tisan", "Radix", "Zenas"]) {
      if (!names.includes(name)) failures.push(`A customer Squad list is missing ${name}`);
    }
    await openRoute("/ledger", true, false);
    await evaluate(cdp, `document.getElementById('squad-button').click()`);
    const founderNames = await evaluate<string>(cdp, `document.getElementById('squad-popout').innerText`);
    if (!founderNames.includes("Skala") || !founderNames.includes("Tank")) failures.push("A founder Squad list is missing Skala or Tank");
    const first = await evaluate<string>(cdp, `document.activeElement && document.activeElement.textContent || ""`);
    if (!first.includes("Base")) failures.push(`Focus did not move into Squad (got ${first})`);
    await cdp.send("Input.dispatchKeyEvent", { type: "keyDown", key: "ArrowDown", code: "ArrowDown", windowsVirtualKeyCode: 40 });
    const second = await evaluate<string>(cdp, `document.activeElement && document.activeElement.textContent || ""`);
    if (!second.includes("Tiger")) failures.push(`ArrowDown did not move to Tiger (got ${second})`);

  } finally {
    proc.kill("SIGKILL");
    fixtureServer.closeAllConnections();
    await new Promise<void>(resolve => fixtureServer.close(() => resolve()));
    await rm(dir, { recursive: true, force: true, maxRetries: 8, retryDelay: 150 });
  }
  if (failures.length) {
    console.error(failures.join("\n"));
    process.exit(1);
  }
  console.log(`shell browser checks passed for ${SHELL_ROUTES.length} routes`);
}

await main();
