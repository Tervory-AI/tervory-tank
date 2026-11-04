# Local window index

Owns `window/extensions/tervory-index/`. No server, API key or model service is used.
`npm ci && npm run model && npm test` prepares a development checkout. Ship the
`models/` directory in the extension: runtime refuses remote models. Model assets
are pinned to a Hub commit and verified against SHA-256 in `scripts/model-lock.json`.
Missing assets fail closed; they never trigger downloads. Build-time downloads
contain no project source or queries.

The Apache-2.0 MiniLM model runs on CPU in a worker thread through pinned
Transformers.js (Apache-2.0); Orama (Apache-2.0) stores vectors in workspace-private
local extension storage. Dependencies and transitive versions are locked. No
external executable, Python installation or vector server is required.

Only trusted local file workspaces are indexed. Remote hosts run this workspace
extension where their filesystem lives; virtual workspaces are unsupported.
JS/TS uses the TypeScript AST, Python uses definition boundaries, other languages
use bounded text chunks (the chunker also accepts document-symbol spans). Large
files, binary files, symlinks, generated directories, secret paths and recognizable
credential assignments are excluded. `.gitignore` and `.tervoryignore` are read
at each directory. No heuristic can identify every possible secret; put other
sensitive paths in `.tervoryignore`. The local cache contains source snippets.

Create/change/delete events debounce a serialized refresh, including ignore-file
changes; content hashes avoid embedding unchanged files. Removed, newly ignored
or newly sensitive files are evicted. Cache state is atomically replaced and
reconciled against disk on startup. Unsaved editor buffers are not persisted.

## Frames needed

`docs/figma/window/REGISTER.md` was absent on the starting main. All visible strings
are bracketed placeholders pending those frames. No final product wording is authored.
Required frames: project-index initial/empty, indexing progress, ready, missing
model/error/retry, search input with meaning/exact mode, results with file and line
references, no matches, context attachment preview/removal, untrusted project,
and multi-root project selection. The panel owner should map approved frame IDs
before replacing placeholders. Industry terms do not enter this general index.

## Panel API (version 1)

The panel in `window/extension/` calls
`await vscode.extensions.getExtension<IndexApi>('tervory.tervory-index')?.activate()`.
`src/api.ts` is the contract: `search(query, {mode:'meaning'|'exact', limit,
workspaceUri})` and `getRelevantCode(query, {maxCharacters, limit, workspaceUri})`.
Results contain URI, relative path, 1-based inclusive start/end lines, text and score.
Use `Uri.toString()` for workspace selection; omitted selection searches all open
local roots. Context selection uses meaning search, removes overlapping spans,
and enforces a content-character budget without truncating source lines. Snippets
are untrusted source, not instructions. This API never sends a request: the panel
owns attachment display and request submission. Refresh reconciles disk before
retrieval so a changed ignore rule cannot expose stale cached code.

The `[Search project]` command provides a native window Quick Pick for meaning or
literal case-sensitive matching, then opens the selected file at its source lines.

Test host: stock VSCodium 1.143.17232, downloaded and SHA-256 verified by
`scripts/electron.mjs`, launched through pinned `@vscode/test-electron`.
`npm run test:electron` uses an isolated profile and fixture. Linux needs Xvfb
(`xvfb-run -a npm run test:electron`); Windows/macOS use the same runner directly.

## Performance gate

`npm run benchmark` creates 10,000 unique source files and embeds all chunks with
the real packaged CPU model. It checks three paraphrased queries against known
files and a punctuation-sensitive literal query. Cold indexing (including local
persistence) must finish in 600 seconds. Each search, including disk refresh as
used by the panel API, must finish in 35 seconds; an unchanged refresh must finish
in 30 seconds. `benchmark-results.json` records OS, architecture, Node version,
CPU, measured times, budgets, expected files and returned paths. CI uploads one
record per OS. These are fixture budgets, not a claim about every project or CPU.

The three-OS workflow is the only integration file outside this extension's
ownership lane. It changes no deployment or paid routes. Model downloads occur
only during build/test preparation and are checksum-verified before indexing.
