/** Real Shell/Squad components with offline Clerk/navigation adapters; no copied UI handlers. */
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
const root = new URL("../", import.meta.url);
const require = createRequire(new URL("workspace/package.json", root));
const ts = require("typescript");

export function actualShellHtml(founder: boolean): string {
  const modules: Record<string, string> = {};
  for (const [name, path] of Object.entries({
    react: "react/cjs/react.production.js",
    "react/jsx-runtime": "react/cjs/react-jsx-runtime.production.js",
    "react-dom": "react-dom/cjs/react-dom.production.js",
    "react-dom/client": "react-dom/cjs/react-dom-client.production.js",
    scheduler: "scheduler/cjs/scheduler.production.js",
  })) modules[name] = readFileSync(new URL(`workspace/node_modules/${path}`, root), "utf8");
  for (const name of ["shell", "squad-links", "product-nav"]) {
    const extension = name === "product-nav" ? "ts" : "tsx";
    modules[`./${name}`] = ts.transpileModule(readFileSync(new URL(`workspace/app/${name}.${extension}`, root), "utf8"), {
      compilerOptions: { target: ts.ScriptTarget.ES2020, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true },
    }).outputText;
  }
  modules["next/navigation"] = 'exports.usePathname=()=>"/skala/gold";exports.useSearchParams=()=>new URLSearchParams();exports.useSelectedLayoutSegments=()=>["skala","gold"];';
  modules["next/link"] = 'module.exports=(props)=>require("react").createElement("a",props);';
  modules["@clerk/nextjs"] = 'exports.useAuth=()=>({isLoaded:false});exports.SignedIn=({children})=>children;exports.OrganizationSwitcher=()=>"Example workspace";exports.UserButton=()=>null;';
  const fonts = `@font-face{font-family:Inter;src:url(${new URL("workspace/app/fonts/Inter-latin.woff2",root).href});font-weight:100 900}
    @font-face{font-family:Jost;src:url(${new URL("workspace/app/fonts/Jost-300-latin.woff2",root).href});font-weight:300}
    @font-face{font-family:Mono;src:url(${new URL("workspace/app/fonts/JetBrainsMono-latin.woff2",root).href})}
    :root{--font-inter:Inter;--font-jost:Jost;--font-mono:Mono}`;
  const bundle = `const modules={${Object.entries(modules).map(([key, source]) => `${JSON.stringify(key)}:(module,exports,require)=>{${source}\n}`).join(",")}};
    const cache={};function require(name){if(!cache[name]){const m={exports:{}};cache[name]=m;modules[name](m,m.exports,require);}return cache[name].exports;}
    const React=require('react');require('react-dom/client').createRoot(document.getElementById('root')).render(React.createElement(require('./shell').Shell,{founder:${founder},reviewer:false,readAccess:async()=>({founder:${founder},reviewer:false})},React.createElement('section',null,React.createElement('h1',null,'Base'),React.createElement('p',null,'Find and verify businesses for your next list.'))));`;
  // Resolve the unchanged originals locally; production image paths stay untouched.
  return `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><base href="${new URL("workspace/public/", root).href}"><style>${readFileSync(new URL("workspace/app/globals.css", root), "utf8")}${fonts}</style></head><body><div id="root"></div><script>${bundle.replaceAll('"/brand/', '"' + new URL("workspace/public/brand/", root).href).replaceAll("</script", "<\\/script")}</script></body></html>`;
}
