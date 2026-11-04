import ts from 'typescript';
import path from 'node:path';
export interface Chunk { path: string; startLine: number; endLine: number; text: string }
export interface Span { startLine: number; endLine: number }
// Language providers can supply document-symbol spans for any installed language.
// TypeScript's parser supplies offline structure for JS/TS without a language server.
export function chunks(file: string, text: string, symbols?: Span[]): Chunk[] {
  const lines = text.split('\n');
  const starts = new Set<number>([0]);
  if (symbols?.length) {
    for (const s of symbols) { starts.add(s.startLine); starts.add(s.endLine + 1); }
  } else if (/\.[cm]?[jt]sx?$/.test(file)) {
    const source = ts.createSourceFile(file, text, ts.ScriptTarget.Latest, true,
      /tsx$/.test(file) ? ts.ScriptKind.TSX : /jsx$/.test(file) ? ts.ScriptKind.JSX : /[cm]?js$/.test(file) ? ts.ScriptKind.JS : ts.ScriptKind.TS);
    const visit = (node: ts.Node): void => {
      if (ts.isFunctionDeclaration(node) || ts.isClassDeclaration(node) || ts.isMethodDeclaration(node) ||
          ts.isInterfaceDeclaration(node) || ts.isVariableStatement(node)) {
        starts.add(source.getLineAndCharacterOfPosition(node.getStart(source)).line);
        starts.add(source.getLineAndCharacterOfPosition(node.end).line + 1);
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
  } else if (path.extname(file) === '.py') {
    lines.forEach((line, i) => { if (/^\s*(?:async\s+)?(?:def|class)\s+/.test(line)) starts.add(i); });
  }
  const boundaries = [...starts, lines.length].filter(n => n >= 0 && n <= lines.length).sort((a,b) => a-b);
  const result: Chunk[] = [];
  for (let i = 0; i < boundaries.length - 1; i++) {
    // Bound long symbols by characters as well as lines: model context is finite.
    let start = boundaries[i];
    while (start < boundaries[i+1]) {
      let end = start, size = 0;
      while (end < boundaries[i+1] && end - start < 40 && (size < 900 || end === start)) {
        size += lines[end].length + 1; end++;
      }
      const body = lines.slice(start, end).join('\n');
      // Extremely long generated/minified lines are deliberately excluded.
      if (body.trim() && body.length <= 4000) result.push({path:file, startLine:start+1, endLine:end, text:body});
      start = end;
    }
  }
  return result;
}
