/**
 * Saved-page gate for the starter site.
 *
 * Reads the HTML the production build already wrote. It does not fetch a page,
 * follow a link, or open a socket. A deploy is refused until every saved page
 * has a privacy notice, and a cookie notice when that page loads a script or
 * frame from another site. This command does not publish the site.
 */

const fs = require("node:fs");
const path = require("node:path");

const TOOL = "comply.gdpr";
const MAX_BYTES = 1_000_000;
const HOST =
  /^(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$/;
const PRIVACY_TEXT =
  /\b(?:privacy(?:\s+(?:policy|notice))?|popia|protection of personal information)\b/i;
const PRIVACY_HREF = /(?:privacy(?:[-_](?:policy|notice))?|popia|data[-_]protection)/i;
const NOTICE_PAGE =
  /\b(?:privacy(?:\s+(?:policy|notice))?|popia(?:\s+notice)?|protection of personal information)\b/i;
const COOKIE = /\bcookies?\b/i;
const ADDRESS = /^\s*https?:\/\//i;
const NAMED = { amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: "\u00a0" };

class PageRefused extends Error {
  constructor(message) {
    super(message);
    this.name = "PageRefused";
  }
}

function decodeEntities(value) {
  return value.replace(/&(#x?[0-9a-fA-F]+|[a-zA-Z]+);/g, (all, body) => {
    if (body[0] === "#") {
      const hex = body[1] === "x" || body[1] === "X";
      const code = Number.parseInt(body.slice(hex ? 2 : 1), hex ? 16 : 10);
      if (!Number.isInteger(code) || code < 0 || code > 0x10ffff) return all;
      return String.fromCodePoint(code);
    }
    return Object.prototype.hasOwnProperty.call(NAMED, body) ? NAMED[body] : all;
  });
}

function pageName(name) {
  const base = String(name ?? "")
    .replaceAll("\\", "/")
    .split("/")
    .pop()
    .trim()
    .replace(/[\r\n\u0000]/g, "");
  if (!base || base === "." || base === "..") return "page.html";
  return base.slice(0, 200);
}

function pageHost(value) {
  if (value == null) return null;
  if (typeof value !== "string") throw new PageRefused("page host must be a site name");
  const host = value.trim().toLowerCase().replace(/\.+$/, "");
  if (!HOST.test(host)) throw new PageRefused("page host must be a site name");
  return host;
}

function otherSite(src, host) {
  let text = String(src ?? "").trim();
  if (
    !text ||
    text.startsWith("#") ||
    text.startsWith("data:") ||
    text.startsWith("javascript:") ||
    text.startsWith("mailto:")
  ) {
    return null;
  }
  if (text.startsWith("//")) text = `https:${text}`;
  else if (text.startsWith("/") || text.startsWith(".") || !text.includes("://")) return null;
  let parsed;
  try {
    parsed = new URL(text);
  } catch {
    return null;
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return null;
  const name = parsed.hostname.toLowerCase().replace(/\.+$/, "");
  if (!name || name === host) return null;
  return name;
}

function hostPhrase(hosts) {
  const labels = [];
  for (const host of hosts) {
    const label = /^[\x00-\x7F]*$/.test(host) && HOST.test(host) ? host : "another site";
    if (!labels.includes(label)) labels.push(label);
  }
  if (labels.length === 0) return "another site";
  if (labels.length === 1) return labels[0];
  if (labels.length === 2) return `${labels[0]} and ${labels[1]}`;
  return `${labels[0]}, ${labels[1]}, and ${labels.length - 2} more`;
}

function finding(rule, fix, name, line) {
  return { tool: TOOL, severity: "medium", file: name, line, rule, fix };
}

function parseSavedPage(html) {
  const page = { anchors: [], loads: [], visible: [], title: "", h1: "" };
  let index = 0;
  let line = 1;
  const skip = [];
  let anchor = null;
  let title = null;
  let h1 = null;
  let h1Done = false;

  function peek(offset = 0) {
    return html[index + offset] || "";
  }

  function consume() {
    const char = html[index] || "";
    index += 1;
    if (char === "\n") line += 1;
    return char;
  }

  function startsWith(token) {
    return html.startsWith(token, index);
  }

  function skipComment() {
    consume();
    consume();
    consume();
    consume();
    while (index < html.length && !startsWith("-->")) consume();
    if (startsWith("-->")) {
      consume();
      consume();
      consume();
    }
  }

  function readTag() {
    const tagLine = line;
    consume();
    let closing = false;
    if (peek() === "/") {
      closing = true;
      consume();
    }
    if (peek() === "!" || peek() === "?") {
      while (index < html.length && peek() !== ">") consume();
      if (peek() === ">") consume();
      return null;
    }
    let name = "";
    while (index < html.length && /[A-Za-z0-9]/.test(peek())) name += consume();
    name = name.toLowerCase();
    if (!name) return null;
    const attrs = {};
    let selfClosing = false;
    while (index < html.length && peek() !== ">") {
      const char = peek();
      if (char === "/") {
        selfClosing = true;
        consume();
        continue;
      }
      if (/\s/.test(char)) {
        consume();
        continue;
      }
      let key = "";
      while (index < html.length && /[^\s=/>]/.test(peek())) key += consume();
      key = key.toLowerCase();
      let value = "";
      if (peek() === "=") {
        consume();
        const quote = peek();
        if (quote === '"' || quote === "'") {
          consume();
          while (index < html.length && peek() !== quote) value += consume();
          if (peek() === quote) consume();
        } else {
          while (index < html.length && peek() !== ">" && !/\s/.test(peek())) value += consume();
        }
      }
      if (key) attrs[key] = decodeEntities(value);
    }
    if (peek() === ">") consume();
    return { name, closing, attrs, line: tagLine, selfClosing };
  }

  function finishAnchor() {
    if (!anchor) return;
    page.anchors.push([anchor.href, anchor.parts.join(""), anchor.line]);
    anchor = null;
  }

  function takeText(text) {
    if (!text || skip.length > 0) return;
    const decoded = decodeEntities(text);
    if (anchor) anchor.parts.push(decoded);
    if (title) title.push(decoded);
    if (h1) h1.push(decoded);
    page.visible.push(decoded);
  }

  function onTag(tag) {
    if (!tag) return;
    if (skip.length > 0) {
      if (!tag.closing && (tag.name === "script" || tag.name === "style")) skip.push(tag.name);
      else if (tag.closing && tag.name === skip[skip.length - 1]) skip.pop();
      return;
    }
    if (tag.name === "script" || tag.name === "style") {
      if (tag.name === "script" && !tag.closing) page.loads.push([tag.attrs.src || "", tag.line]);
      if (!tag.closing && !tag.selfClosing) skip.push(tag.name);
      return;
    }
    if (tag.name === "iframe" && !tag.closing) page.loads.push([tag.attrs.src || "", tag.line]);
    if (tag.name === "a") {
      if (tag.closing) finishAnchor();
      else {
        anchor = { href: tag.attrs.href || "", line: tag.line, parts: [] };
        if (tag.selfClosing) finishAnchor();
      }
    } else if (tag.name === "title" && !tag.closing && title === null) {
      title = [];
    } else if (tag.name === "title" && tag.closing && title) {
      page.title = title.join("");
      title = null;
    } else if (tag.name === "h1" && !tag.closing && !h1Done) {
      h1 = [];
    } else if (tag.name === "h1" && tag.closing && h1) {
      page.h1 = h1.join("");
      h1 = null;
      h1Done = true;
    }
    if (!tag.closing) {
      for (const key of ["aria-label", "alt", "placeholder"]) {
        if (tag.attrs[key]) page.visible.push(tag.attrs[key]);
      }
    }
  }

  while (index < html.length) {
    if (startsWith("<!--")) {
      skipComment();
      continue;
    }
    if (peek() === "<" && /[A-Za-z!/?]/.test(peek(1))) {
      onTag(readTag());
      continue;
    }
    let text = "";
    while (
      index < html.length &&
      !startsWith("<!--") &&
      !(peek() === "<" && /[A-Za-z!/?]/.test(peek(1)))
    ) {
      text += consume();
    }
    takeText(text);
  }
  finishAnchor();
  if (title) page.title = title.join("");
  if (h1) {
    page.h1 = h1.join("");
  }
  return page;
}

function hasPrivacyLink(page) {
  return page.anchors.some(([href, text]) => PRIVACY_HREF.test(href) || PRIVACY_TEXT.test(text));
}

function isNoticePage(page) {
  return NOTICE_PAGE.test(page.title) || NOTICE_PAGE.test(page.h1);
}

function hasCookieNotice(page) {
  return COOKIE.test(page.visible.join(" "));
}

function otherLoads(page, host) {
  const found = [];
  const seen = new Set();
  for (const [src, srcLine] of page.loads) {
    const hostName = otherSite(src, host);
    if (!hostName || seen.has(hostName)) continue;
    seen.add(hostName);
    found.push([hostName, srcLine]);
    if (found.length === 20) break;
  }
  return found;
}

function scanHtml(html, options = {}) {
  if (typeof html !== "string") throw new PageRefused("saved page must be text");
  const host = pageHost(options.pageHost ?? null);
  const name = pageName(options.name);
  if (Buffer.byteLength(html, "utf8") > MAX_BYTES) throw new PageRefused("saved page is too large");
  if (!html.trim()) throw new PageRefused("saved page is empty");
  if (ADDRESS.test(html) && !html.includes("<")) {
    throw new PageRefused("a web address is not a saved page");
  }
  let parsed;
  try {
    parsed = parseSavedPage(html);
  } catch (error) {
    if (error instanceof PageRefused) throw error;
    throw new PageRefused("saved page could not be read");
  }
  const findings = [];
  if (!hasPrivacyLink(parsed) && !isNoticePage(parsed)) {
    findings.push(
      finding("missing-privacy-notice", "Add a link to the privacy notice.", name, null),
    );
  }
  const others = otherLoads(parsed, host);
  if (others.length > 0 && !hasCookieNotice(parsed)) {
    const fix =
      `This page loads content from ${hostPhrase(others.map((item) => item[0]))}. ` +
      "Add a cookie notice on this page, or load that content from this site.";
    findings.push(finding("missing-cookie-notice", fix, name, others[0][1]));
  }
  return { tool: TOOL, page: name, fetched: false, findings };
}

function savedPageFiles(root) {
  const dir = path.join(root, ".next", "server", "app");
  if (!fs.existsSync(dir)) return [];
  const stat = fs.statSync(dir);
  if (!stat.isDirectory()) return [];
  return fs
    .readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith(".html"))
    .map((entry) => path.join(dir, entry.name))
    .sort();
}

function readSaved(file) {
  const bytes = fs.readFileSync(file);
  if (bytes.length > MAX_BYTES) throw new PageRefused("saved page is too large");
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    throw new PageRefused("saved page is not text");
  }
}

function refuseReason(pages) {
  const parts = ["Deploy refused."];
  for (const page of pages) {
    for (const item of page.findings) {
      if (item.rule === "missing-privacy-notice") {
        parts.push(`${page.page} has no privacy notice.`);
      } else {
        parts.push(`${page.page}: ${item.fix}`);
      }
    }
  }
  return parts.join(" ");
}

function checkSavedPages(root) {
  if (typeof root !== "string" || ADDRESS.test(root)) {
    throw new PageRefused("a web address is not a saved page");
  }
  const files = savedPageFiles(root);
  if (files.length === 0) {
    return {
      ok: false,
      deployed: false,
      reason: "Deploy refused. Build the site first. There is no saved page to check.",
      pages: [],
    };
  }
  const pages = [];
  for (const file of files) {
    const name = path.basename(file);
    let html;
    try {
      html = readSaved(file);
    } catch (error) {
      if (error instanceof PageRefused) {
        return {
          ok: false,
          deployed: false,
          reason: `Deploy refused. ${name}: ${error.message}.`,
          pages: [],
        };
      }
      throw error;
    }
    pages.push(scanHtml(html, { name }));
  }
  const failed = pages.filter((page) => page.findings.length > 0);
  if (failed.length > 0) {
    return { ok: false, deployed: false, reason: refuseReason(failed), pages };
  }
  const noun = pages.length === 1 ? "page" : "pages";
  return {
    ok: true,
    deployed: false,
    reason: `Saved-page checks passed for ${pages.length} ${noun}. Nothing was deployed.`,
    pages,
  };
}

function isWebAddress(value) {
  return ADDRESS.test(String(value));
}

function run(argv, cwd = process.cwd()) {
  const args = argv.map((item) => String(item));
  if (args.some((item) => isWebAddress(item))) {
    return { code: 1, text: "Deploy refused. A web address is not a saved page." };
  }
  if (args.length > 1) {
    return { code: 1, text: "Deploy refused. Check one site at a time." };
  }
  const root = args.length === 1 ? path.resolve(cwd, args[0]) : cwd;
  try {
    const result = checkSavedPages(root);
    return { code: result.ok ? 0 : 1, text: result.reason, result };
  } catch (error) {
    if (error instanceof PageRefused) {
      return { code: 1, text: `Deploy refused. ${error.message}` };
    }
    throw error;
  }
}

if (require.main === module) {
  const outcome = run(process.argv.slice(2));
  const stream = outcome.code === 0 ? process.stdout : process.stderr;
  stream.write(`${outcome.text}\n`);
  process.exit(outcome.code);
}

module.exports = {
  PageRefused,
  TOOL,
  MAX_BYTES,
  checkSavedPages,
  run,
  scanHtml,
  savedPageFiles,
};
