import { readFile } from "node:fs/promises";
import ts from "../workspace/node_modules/typescript/lib/typescript.js";
export { resolve } from "./market_lab_hooks.mjs";
export async function load(url, context, nextLoad) {
  if (url.endsWith(".tsx")) {
    const source = await readFile(new URL(url), "utf8");
    return { format: "module", shortCircuit: true, source: ts.transpileModule(source, {
      compilerOptions: { module: ts.ModuleKind.ESNext, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
    }).outputText };
  }
  return nextLoad(url, context);
}
