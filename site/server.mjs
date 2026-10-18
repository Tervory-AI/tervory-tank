import { createReadStream, existsSync, statSync } from "node:fs";
import { createServer } from "node:http";
import { extname, join, normalize, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { storeAddress } from "./release-store.mjs";

const here = fileURLToPath(new URL(".", import.meta.url));

function arg(name, fallback) {
  const index = process.argv.indexOf(name);
  if (index === -1 || process.argv[index + 1] == null) return fallback;
  return process.argv[index + 1];
}

const root = resolve(arg("--root", join(here, "out")));
const file = resolve(arg("--file", "/data/release-signups.jsonl"));
const port = Number(arg("--port", "3000"));

const types = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
  ".xml": "application/xml; charset=utf-8",
  ".woff2": "font/woff2",
  ".webp": "image/webp",
};

function insideRoot(path) {
  const resolved = resolve(path);
  return resolved === root || resolved.startsWith(root + sep);
}

function pagePath(urlPath) {
  const decoded = decodeURIComponent(urlPath.split("?")[0]);
  const safe = normalize(decoded).replace(/^(\.\.(\/|\\|$))+/, "");
  const candidate = join(root, safe);
  if (!insideRoot(candidate)) return null;
  const tries = [candidate];
  if (!extname(candidate)) {
    tries.push(`${candidate}.html`, join(candidate, "index.html"));
  }
  for (const path of tries) {
    if (!insideRoot(path) || !existsSync(path)) continue;
    const stat = statSync(path);
    if (stat.isFile()) return path;
  }
  return null;
}

function wantsHtml(req) {
  const type = req.headers["content-type"] || "";
  if (type.includes("application/json")) return false;
  return (req.headers.accept || "").includes("text/html");
}

function readBody(req) {
  return new Promise((resolveBody, reject) => {
    const chunks = [];
    let size = 0;
    req.on("data", (chunk) => {
      size += chunk.length;
      if (size > 4096) {
        reject(new Error("too large"));
        req.destroy();
        return;
      }
      chunks.push(chunk);
    });
    req.on("end", () => resolveBody(Buffer.concat(chunks).toString("utf8")));
    req.on("error", reject);
  });
}

function emailFrom(req, raw) {
  const type = req.headers["content-type"] || "";
  if (type.includes("application/json")) {
    const body = JSON.parse(raw);
    return body && typeof body.email === "string" ? body.email : "";
  }
  return new URLSearchParams(raw).get("email") || "";
}

function page(result) {
  const saved = result.stored === true;
  const title = saved ? "Saved" : "Not saved";
  const message = saved
    ? "Saved. We'll email this address when we release."
    : "That address was not saved. Try again.";
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>${title} — Tervory AI</title>
</head>
<body style="margin:0;background:#fff;color:#001840;font-family:Inter,system-ui,sans-serif">
<main style="max-width:40rem;padding:4rem 1.5rem">
<p style="margin:0 0 1rem;font-family:ui-monospace,monospace;font-size:12px;letter-spacing:.08em;text-transform:uppercase">Tervory</p>
<h1 style="margin:0 0 1rem;font-weight:300;font-size:2.5rem">${title}.</h1>
<p style="margin:0 0 1.5rem;font-size:1.05rem;line-height:1.5">${message}</p>
<p style="margin:0"><a href="/" style="color:#001840">Back to the homepage</a></p>
</main>
</body>
</html>`;
}

function sendResult(res, result, html) {
  if (html) {
    res.writeHead(result.status, {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
      "x-robots-tag": "noindex, nofollow",
    });
    res.end(page(result));
    return;
  }
  res.writeHead(result.status, {
    "content-type": "application/json; charset=utf-8",
    "cache-control": "no-store",
  });
  res.end(JSON.stringify({ stored: result.stored === true }));
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url || "/", "http://127.0.0.1");
  try {
    if (url.pathname === "/api/release-notice") {
      if (req.method !== "POST") {
        sendResult(res, { status: 405, stored: false }, wantsHtml(req));
        console.log(`${req.method} ${url.pathname} 405`);
        return;
      }
      let email = "";
      try {
        email = emailFrom(req, await readBody(req));
      } catch {
        sendResult(res, { status: 400, stored: false }, wantsHtml(req));
        console.log(`POST ${url.pathname} 400`);
        return;
      }
      const result = await storeAddress(file, email);
      sendResult(res, result, wantsHtml(req));
      console.log(`POST ${url.pathname} ${result.status}`);
      return;
    }

    if (req.method !== "GET" && req.method !== "HEAD") {
      res.writeHead(405, { "content-type": "text/plain; charset=utf-8" });
      res.end("Method not allowed");
      return;
    }

    const path = pagePath(url.pathname === "/" ? "/index.html" : url.pathname);
    if (!path) {
      res.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
      res.end("Not found");
      console.log(`${req.method} ${url.pathname} 404`);
      return;
    }
    const headers = { "content-type": types[extname(path)] || "application/octet-stream" };
    if (url.pathname.startsWith("/internal")) headers["x-robots-tag"] = "noindex, nofollow";
    res.writeHead(200, headers);
    if (req.method === "HEAD") {
      res.end();
      return;
    }
    createReadStream(path).pipe(res);
  } catch {
    if (!res.headersSent) {
      sendResult(res, { status: 500, stored: false }, wantsHtml(req));
    }
    console.log(`${req.method} ${url.pathname} 500`);
  }
});

server.listen(port, "0.0.0.0", () => {
  console.log(`site listening on ${port}`);
});
