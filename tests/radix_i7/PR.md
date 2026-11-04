# Radix I7 — private reports from real scan findings

Audit: main `55b2e224` and the inherited #634 work had findings and changes cards, but no `radix.report` tool or downloadable report. This gate adds that read on `codex/radix-w4`, stacked on #634, without merging or rebasing main. Claude opens the PR.

`radix.report <scan UUID>` uses code templates, without a model, and returns an absolute `url` for the existing Result link. It renders every persisted finding from a completed or failed repo, passive, watch or active scan: severity counts, the tool's own title/explanation, location, remediation and evidence. It never invents missing remediation or interprets an incomplete scan as clean. Unknown, pending and foreign scans do not yield reports. Own-repository evidence links bind to the verified commit; other evidence links return the authenticated persisted finding JSON rather than today's mutable page.

Downloads use the existing signed-in Workspace-to-Tank corridor. The active workspace determines the tenant; browser query parameters cannot select one. The private room read carries the trusted actor tenant header and uses tenant-scoped SQL. HTML is escaped, downloadable, private/no-store and has a restrictive CSP; no external assets or network fetches are needed. The read writes a $0 code receipt. No page, email, model, public sharing link or new card wording was added.

HTML is available. **WeasyPrint is not installed in this runtime or declared in Tank requirements, so PDF is unavailable here.** No dependency was installed. If an existing deployment already has WeasyPrint, the optional PDF renderer uses the same template and refuses resource fetches; that installed-PDF path is not claimed as exercised here.

Existing labels used: Scan ID, Status, Tool, Severity, Rule, Location, Explanation, Remediation and Result. Finding headings use the finding's own title/explanation/rule. No extra heading was required; no missing frame.

## Changes by file/line

- `tank/radix_report.py:15`: optional installed-PDF detection; `:33` owned real-scan loader, `:54` immutable/private evidence, `:65` escaped complete template, `:99` $0 receipt/URL, `:109` authenticated routes.
- `agents/radix/passive_store.py:369`: tenant-scoped persisted scan/check/finding read.
- `agents/radix/passive_routes.py:145`: private room report route with tenant-header equality check.
- `tank/ghost_routes.py:51`: optional trusted UUID tenant header for room reads; the actual private HTTP corridor is tested.
- `tank/radix_repo.py:57`: preserve verified repository/commit metadata for immutable evidence links.
- `tank/command.py:47`: catalogue; `:1390` read adapter reusing findings labels; `:2311` router registration.
- `tank/radix_watch.py:28`: explicit report command code plan.
- `workspace/app/chats/api/[...path]/route.ts:46`: authenticated private download/evidence forwarding through existing Tank helpers.
- `tests/test_radix_report.py:24`: complete fixture, escaping, source-kind coverage, tenant isolation, $0 receipt, incomplete/pending behavior and actual private room HTTP integration.
- `tests/radix_i7/workspace.cjs:1`: actual Workspace handler and Result presentation, including ignored browser tenant query and signed-out refusal.

## Validation

Focused report and existing presentation checks: **13 passed, 3 warnings in 20.09s**. After tightening evidence links to persisted observations, the targeted template check passed: **1 passed, 8 deselected, 3 warnings in 1.49s**. Workspace TypeScript check passed. Combined regression: **577 passed, 256 warnings, 437 subtests passed in 777.86s**. Final room source imports in the previously tested I2 image with networking disabled; a redundant full dependency rebuild was cancelled during apt installation. Secret checks: **2 passed**. CI exact lint, changed room lint and whitespace checks pass. PROOF.txt records the evidence. Hosted CI and founder live acceptance remain pending Claude's PR/merge; no production scan, deploy or configuration change was run here.
