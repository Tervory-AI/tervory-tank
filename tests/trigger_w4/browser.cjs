/* Actual Trigger React views and public widget, isolated placeholder HTTP fixtures. */
const fs = require("node:fs"),
  path = require("node:path"),
  assert = require("node:assert/strict");
const { createServer } = require("node:http");
const root = path.resolve(__dirname, "../.."),
  base = path.join(root, "workspace");
const tools =
  process.env.TRIGGER_BROWSER_TOOLS ||
  path.join(root, ".wave4-tools/node_modules");
const { build } = require(path.join(tools, "esbuild")),
  { chromium } = require(path.join(tools, "playwright"));
const id = "00000000-0000-0000-0000-000000000411",
  visitor = "00000000-0000-0000-0000-000000000412";
const record = {
  id,
  first_name: "placeholder first",
  last_name: "placeholder last",
  company_name: "placeholder company",
  email: "contact@placeholder.invalid",
  status: "placeholder status",
  source: "placeholder source",
  next_follow_up: "2026-11-04",
  assigned_to: "placeholder person",
  invoice_number: "placeholder invoice",
  estimate_number: "placeholder quote",
  client_name: "placeholder client",
  total_amount: "123.45",
  currency: "ZAR",
};
const post = {
  id,
  channel: "facebook",
  text: "placeholder post",
  state: "approved",
  approved_revision: 1,
  time_zone: "Africa/Johannesburg",
  planned_at: "2026-11-03T08:00:00Z",
  report: {
    complete: true,
    length: { count: 16, limit: 63206, unit: "Unicode code points" },
    issues: [],
  },
};
let proposed = [],
  confirmed = 0,
  sends = 0,
  capture = false,
  contacts = [];
let releaseMessage;
const entry = `import React from 'react';import {createRoot} from 'react-dom/client';import Shell from './app/trigger/shell';import CRMView from './app/trigger/records';import View from './app/trigger/view';const params=new URLSearchParams(location.search),kind=params.get('kind')||'leads',detail=params.has('detail');const record=${JSON.stringify(record)},post=${JSON.stringify(post)};let child;
if(['leads','contacts','estimates','invoices'].includes(kind))child=<CRMView resource={kind} detail={detail} data={detail?{item:record}:{items:[record]}}/>;
else{const data=kind==='channels'?{facebook:{status:'connected',page_id:'placeholder-page',page_name:'placeholder page',choices:[{page_id:'placeholder-page',name:'placeholder page'}]}}:kind==='settings'?{settings:{name:'placeholder store',enabled:true,time_zone:'Africa/Johannesburg',greeting:'placeholder greeting'},sources:[]}:kind==='inbox'?{conversations:[{...record,visitor_id:'placeholder visitor',last_message:'placeholder message',updated_at:'2026-11-03'}],conversation:{id:record.id,visitor_id:'placeholder visitor',status:'handed_over'},messages:[{id:record.id,question:'placeholder question',answer:'placeholder answer',cited:[],outcome:'sources'}]}:kind==='reviews'?{reviews:[{id:record.id,review_id:'placeholder-review',text:'placeholder review',rating:'FIVE',location:'placeholder profile'}]}:{posts:[post],post:detail?post:undefined};child=<View area={['inbox','settings'].includes(kind)?'bot':'marketing'} section={kind} id={detail?record.id:undefined} data={data}/>;}createRoot(document.getElementById('root')).render(<Shell>{child}</Shell>);`;
(async () => {
  const bundle = await build({
    stdin: { contents: entry, loader: "tsx", resolveDir: base },
    bundle: true,
    write: false,
    jsx: "automatic",
    outfile: "/placeholder-ui.js",
    define: { "process.env.NODE_ENV": '"production"' },
    plugins: [
      {
        name: "placeholder-boundaries",
        setup(b) {
          b.onResolve({ filter: /^next\/navigation$/ }, () => ({
            path: "navigation",
            namespace: "placeholder",
          }));
          b.onResolve({ filter: /^next\/link$/ }, () => ({
            path: "link",
            namespace: "placeholder",
          }));
          b.onResolve({ filter: /^@clerk\/nextjs$/ }, () => ({
            path: "clerk",
            namespace: "placeholder",
          }));
          b.onResolve({ filter: /^\.\/actions$/ }, () => ({
            path: "actions",
            namespace: "placeholder",
          }));
          b.onLoad({ filter: /.*/, namespace: "placeholder" }, (args) => ({
            loader: "jsx",
            resolveDir: base,
            contents:
              args.path === "navigation"
                ? `export const usePathname=()=>'/trigger/crm/leads';export const useRouter=()=>({push:href=>location.assign(href),refresh:()=>{}});`
                : args.path === "link"
                  ? `import React from 'react';export default function Link({children,...props}){return <a {...props}>{children}</a>}`
                  : args.path === "clerk"
                    ? `import React from 'react';export function OrganizationSwitcher(){return <span aria-label="placeholder business">⌄</span>}`
                    : `export async function proposeTrigger(tool,arguments_){return(await fetch('/placeholder/propose',{method:'POST',body:JSON.stringify({tool,arguments_})})).json()}export async function confirmTrigger(thread,card,action='confirm'){return(await fetch('/placeholder/confirm',{method:'POST',body:JSON.stringify({action})})).json()}`,
          }));
        },
      },
    ],
  });
  const output = bundle.outputFiles[0].contents,
    css = fs.readFileSync(path.join(base, "app/trigger/trigger.css"), "utf8");
  const html = `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><style>@font-face{font-family:Inter;src:url('/fonts/Inter-latin.woff2')}@font-face{font-family:Jost;src:url('/fonts/Jost-300-latin.woff2');font-weight:300}body{margin:0;--font-inter:Inter;--font-jost:Jost}${css}</style></head><body><main id="root"></main><script src="/placeholder-ui.js"></script></body></html>`;
  const server = createServer(async (req, res) => {
    res.setHeader("Access-Control-Allow-Origin", req.headers.origin || "*");
    if (req.method === "OPTIONS") {
      res.setHeader("Access-Control-Allow-Methods", "POST");
      res.setHeader("Access-Control-Allow-Headers", "content-type,x-bot-key");
      res.statusCode = 204;
      res.end();
      return;
    }
    const url = new URL(req.url, "http://placeholder"),
      json = (data) => {
        res.setHeader("content-type", "application/json");
        res.end(JSON.stringify(data));
      };
    if (url.pathname === "/placeholder-ui.js") {
      res.setHeader("content-type", "text/javascript");
      return res.end(output);
    }
    if (
      url.pathname.startsWith("/trigger/") &&
      !url.pathname.includes("/crm/")
    ) {
      const target = path.join(base, "public", url.pathname);
      if (fs.existsSync(target) && fs.statSync(target).isFile()) {
        res.setHeader(
          "content-type",
          url.pathname.endsWith(".css")
            ? "text/css"
            : url.pathname.endsWith(".js")
              ? "text/javascript"
              : url.pathname.endsWith(".svg")
                ? "image/svg+xml"
                : url.pathname.endsWith(".png")
                  ? "image/png"
                  : "font/ttf",
        );
        return res.end(fs.readFileSync(target));
      }
    }
    if (url.pathname.startsWith("/fonts/"))
      return res.end(fs.readFileSync(path.join(base, "app", url.pathname)));
    let body = "";
    for await (const part of req) body += part;
    const data = body ? JSON.parse(body) : {};
    if (url.pathname === "/placeholder/propose") {
      proposed.push(data);
      return json({
        thread_id: id,
        card: { card_id: id },
        preview: [["Text", "placeholder server-captured preview"]],
      });
    }
    if (url.pathname === "/placeholder/confirm") {
      if (data.action === "confirm") confirmed++;
      return json({
        status: data.action === "confirm" ? "confirmed" : "cancelled",
      });
    }
    if (url.pathname.startsWith("/v1/bot/widget/")) {
      const op = url.pathname.split("/").pop();
      if (op === "config")
        return json({
          name: "placeholder store",
          greeting: "placeholder greeting",
          no_source_message: "placeholder no source",
          handover_message: "placeholder hand-over",
          available: true,
          enabled: true,
          capture,
          quote: capture,
          privacy_notice: capture ? "placeholder approved notice" : "",
          notice_version: capture ? "placeholder-v1" : "",
        });
      if (op === "message") {
        sends++;
        if (data.contact) {
          contacts.push(data);
          return json({
            conversation_id: id,
            visitor_id: visitor,
            state: "handed_over",
            ...(data.quote_product_id
              ? { quote_draft_id: id }
              : { lead_draft_id: id }),
          });
        }
        await new Promise((resolve) => { releaseMessage = resolve; });
        return json({
          conversation_id: id,
          visitor_id: visitor,
          state: "bot",
          answer: "placeholder grounded answer",
          sources: [0, 1, 2].map((n) => ({
            title: "placeholder source " + n,
            url: "https://source.placeholder.invalid/" + n,
          })),
        });
      }
      if (op === "handover")
        return json({
          conversation_id: id,
          visitor_id: visitor,
          state: "handed_over",
        });
      if (op === "poll") return json({ messages: [] });
    }
    if (url.pathname === "/placeholder-widget") {
      capture = url.searchParams.has("capture");
      res.setHeader("content-type", "text/html");
      return res.end(
        `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><script src="http://localhost:${server.address().port}/trigger/widget.js" data-bot-key="tb1.us-east.${"a".repeat(32)}.rk_pub_${"b".repeat(48)}"></script></body></html>`,
      );
    }
    res.setHeader("content-type", "text/html");
    res.end(html);
  });
  await new Promise((r) => server.listen(0, "127.0.0.1", r));
  const origin = `http://127.0.0.1:${server.address().port}`,
    browser = await chromium.launch({
      executablePath: "/usr/bin/google-chrome",
      args: ["--no-sandbox"],
    }),
    page = await browser.newPage(),
    errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const evidence = path.join(__dirname, "evidence");
  fs.mkdirSync(evidence, { recursive: true });
  try {
    for (const width of [1440, 375]) {
      await page.setViewportSize({ width, height: width === 1440 ? 900 : 812 });
      for (const kind of [
        "leads",
        "contacts",
        "estimates",
        "invoices",
        "channels",
        "calendar",
        "composer",
        "reviews",
        "inbox",
        "settings",
      ]) {
        await page.goto(origin + "/?kind=" + kind);
        await page.locator("h1").waitFor();
        await page.evaluate(() => document.fonts.ready);
        assert(await page.locator("h1").textContent());
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
          true,
          kind + " overflow " + width,
        );
        if (["leads", "channels", "settings"].includes(kind))
          await page.screenshot({
            path: path.join(evidence, kind + "-" + width + ".png"),
            fullPage: false,
          });
      }
      await page.goto(origin + "/?kind=leads&detail=1");
      await page
        .getByRole("heading", { name: "placeholder first placeholder last" })
        .waitFor();
      assert.equal(
        await page
          .getByRole("button", { name: "Delete", exact: true })
          .isDisabled(),
        true,
      );
      await page.screenshot({
        path: path.join(evidence, "detail-" + width + ".png"),
      });
      if (width === 375) {
        await page.getByRole("button", { name: "Menu", exact: true }).click();
        await page
          .getByRole("button", { name: "Close", exact: true })
          .last()
          .waitFor();
        await page.keyboard.press("Escape");
        assert.equal(
          await page
            .getByRole("button", { name: "Menu", exact: true })
            .getAttribute("aria-expanded"),
          "false",
        );
      }
      await page.goto(origin + "/?kind=settings");
      await page
        .getByRole("button", { name: "Save settings", exact: true })
        .click();
      await page.getByRole("heading", { name: "Confirm · Settings" }).waitFor();
      await page
        .getByText("placeholder server-captured preview", { exact: true })
        .waitFor();
      assert.equal(confirmed, width === 1440 ? 0 : 1);
      await page.getByRole("button", { name: "Confirm", exact: true }).click();
      await page
        .getByRole("heading", { name: "Settings", exact: true })
        .waitFor();
      await page.goto(origin + "/placeholder-widget");
      await page.getByRole("button", { name: "Chat", exact: true }).click();
      await page
        .getByRole("button", { name: "Start chat", exact: true })
        .click();
      await page
        .getByLabel("Message", { exact: true })
        .fill("placeholder enquiry");
      await page.getByRole("button", { name: "Send", exact: true }).click();
      assert.equal(
        await page
          .getByRole("button", { name: "Send", exact: true })
          .isDisabled(),
        true,
      );
      assert.equal(typeof releaseMessage, "function");
      releaseMessage();
      releaseMessage = undefined;
      await page
        .getByText("placeholder grounded answer", { exact: true })
        .waitFor();
      assert.equal(await page.locator('a[target="_blank"]').count(), 3);
      assert.equal(
        await page
          .getByRole("button", { name: "Leave details", exact: true })
          .isDisabled(),
        true,
      );
      const panel = await page.locator(".panel").boundingBox();
      assert.equal(Math.round(panel.width), 343);
      assert.equal(Math.round(panel.height), 640);
      await page.waitForFunction(() =>
        ["TriggerWidgetAtkinson", "TriggerWidgetLiterata"].every((family) =>
          [...document.fonts].some(
            (face) => face.family === family && face.status === "loaded",
          ),
        ),
      );
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({
        path: path.join(evidence, "widget-" + width + ".png"),
      });
      await page
        .getByRole("button", { name: "Talk to a person", exact: true })
        .click();
      await page
        .getByText("Connecting you to a person", { exact: true })
        .waitFor();
    }
    assert.equal(sends, 2);
    await page.goto(origin + "/placeholder-widget?capture=1");
    await page.getByRole("button", { name: "Chat", exact: true }).click();
    await page.getByRole("button", { name: "Start chat", exact: true }).click();
    await page
      .getByRole("button", { name: "Leave details", exact: true })
      .click();
    await page
      .getByLabel("First name", { exact: true })
      .fill("placeholder first");
    await page
      .getByLabel("Last name", { exact: true })
      .fill("placeholder last");
    await page.getByLabel("Phone", { exact: true }).fill("+12025550123");
    await page.getByLabel("Notes", { exact: true }).fill("placeholder notes");
    await page
      .getByRole("button", { name: "Send my details", exact: true })
      .click();
    await page.getByText("Details sent", { exact: true }).waitFor();
    assert.equal(
      contacts[0].contact.name,
      "placeholder first placeholder last",
    );
    assert.equal(contacts[0].contact.email, undefined);
    assert.equal(contacts[0].notice_version, "placeholder-v1");
    await page
      .getByRole("button", { name: "Request a quote", exact: true })
      .click();
    await page.getByLabel("Title", { exact: true }).fill("placeholder title");
    await page.getByLabel("Product", { exact: true }).fill("placeholder-sku");
    await page.getByLabel("Quantity", { exact: true }).fill("3");
    await page
      .getByLabel("Your request", { exact: true })
      .fill("placeholder request");
    await page
      .getByLabel("Contact", { exact: true })
      .fill("placeholder name <contact@placeholder.invalid>");
    await page
      .getByRole("button", { name: "Send request", exact: true })
      .click();
    await page.getByText("Request sent", { exact: true }).waitFor();
    assert.equal(contacts[1].contact.name, "placeholder name");
    assert.equal(contacts[1].contact.email, "contact@placeholder.invalid");
    assert.equal(contacts[1].quote_quantity, 3);
    assert.equal(contacts[1].quote_title, "placeholder title");
    assert.equal(sends, 4);
    assert.equal(confirmed, 2);
    assert.deepEqual(errors, []);
    console.log(
      "PASS actual CRM/Marketing/bot views at 1440 and 375, menu, server-captured Confirm, pending send, three source links, privacy gate, hand-over; no overflow or runtime errors. Placeholder fixtures only.",
    );
  } finally {
    await browser.close();
    await new Promise((r) => server.close(r));
  }
})().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
