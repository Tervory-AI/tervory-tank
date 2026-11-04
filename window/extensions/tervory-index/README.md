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
