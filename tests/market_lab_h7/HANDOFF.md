# Market Lab H7

The existing ML3 briefs read accepts an optional report_id. Detail returns saved
text, citations, original signal confidence, verified stored-passage links and
recorded delivery history. Reports, predictions and document rows are tenant
scoped. Deleted/foreign/unavailable passages have no Open stored source link.
History starts with this deployment; historic sends are not reconstructed.
The additive history table precedes the generated memory-schema block so the
canonical generated suffix stays intact. Claims and history writes are atomic.
Calibration retains kind, feed, frozen horizon and bins and adds measured
confidence, actual rate, hits and misses. Existing $0 code receipts are reused.
No new Tank route, tool, model call, paid service or founder setting.

Workspace: /market-lab/briefs/<report-id> and /market-lab/calibration, with a
supporting /market-lab/briefs list for real report IDs. Existing authenticated
Tank reads and Workspace tenant identity are reused server-side. Pagination
includes later cohorts; unknown metrics are em dashes and only returned bins
are plotted. Frozen periods stay separate.

Frames: codex/figma-w5, file ZnphBOJU6657tohGLD3IzS; brief 566:395 / 566:2140;
calibration 567:941 / 567:1726. These remain Proposed in the register. Native
assets are in workspace/public/market-lab/h7. Dedicated brief confidence and
history sections have no frame slots; both are ready in the structured read.
No new visible section wording is invented.

R44–R47 extend the acceptance sheet to 47 rows. Offline SQL/ASGI tests use real
handlers and code receipts. Node tests use real loaders/views, including 101
cohorts across pages. Browser fixtures use actual components at 1440/375 across
16 page/state combinations, stored-source navigation, cohort switching and
mobile menu/Escape focus. Only the fixture replaces Clerk's organization
switcher. Four populated fixture screenshots and proof.json are retained;
they are not a deployed founder-session claim. Axis labels are checked against
their true positions and native data dots remain 8px.

Local results: direct SQL/ASGI 2 passed; loader/render wrapper 1 passed (4 Node
cases); TypeScript noEmit and exact CI Ruff passed; direct browser 1 passed in
118.40s. Later acceptance R44–R46 passed, while R47's isolated Next compiler
failed to finish startup on the overloaded shared host. A bounded-worker retry
failed at that same stage, before page assertions. Fixture-only cpus=1,
RAYON_NUM_THREADS=1 and UV_THREADPOOL_SIZE=2 prevent excess compiler workers;
no production setting or test deadline changed.

Hosted run 41890503967 on published 717da4f3 passed Workspace, command acceptance,
lint, savings-page and nine Python shards. The sole Python failure was the
history table following the generated schema suffix. That ordering is now
corrected; its exact existing test passed (1 passed, 34.61s). Final CI for the
correction remains required. That manual run audited the entire repository
(base=null): 3 Gitleaks history findings, none in H7 commits; 207 Semgrep
findings, none intersecting H7 additions; 203 OSV findings on unchanged
manifests. No scanner policy, dependency pin or allowlist was changed. The
normal PR comparison audit remains required when Claude opens the one PR.

Semgrep is disabled locally under the founder's 4 Nov instruction, and no own
scan/container remains. Precheck was run with PRECHECK_SKIP_SEMGREP=1. Its
lint/Gitleaks/OSV stages pass; broad local attempts encountered SIGTERM, an
unchanged 30-second seal-check fixture timeout and filesystem journal waits.
A local runner hook stops default-stop pgserver instances only after each
function's own fixture teardown; a local Docker wrapper applies this folder's
container names, --rm and tervory.test=1 label. No other checkout was cleaned.
The current broad local precheck must be reported separately from hosted CI;
no all-green local acceptance or CI claim is made here.

Deploy Market Lab room, Tank and Workspace together. No live data, recipient,
credential, approved skill version or runtime YAML was changed. Founder frame
approval and post-deploy checks with actual saved briefs, citation passages
and outcomes remain outstanding.
