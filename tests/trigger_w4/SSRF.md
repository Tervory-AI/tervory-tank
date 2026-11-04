# PR #654: request-to-Tank URL audit

The reported sink is the shared `boundedFetch` in `workspace/lib/tank.ts:44`. The fix is at every new request-driven caller in this PR; the shared transport and its identity, regional and timeout protections are unchanged. No security suppression is added.

| Call | Validation and construction |
|---|---|
| `workspace/app/trigger/actions.ts:75` — CRM leads, contacts, estimates and invoices, lists and details | `READ_ROUTES` supplies a literal upstream route. Area/resource strings are own-property lookup keys only, never upstream URL text. Optional record IDs must match the full 8-4-4-4-12 hex UUID format and exact length, then pass through `encodeURIComponent`. |
| `workspace/app/trigger/actions.ts:75` — Marketing channels/posts/composer/calendar/reviews and bot settings/inbox | Literal routes come from the same const lookup. Only posts/composer/calendar/reviews/inbox accept the constant `record_id` query key; its value must be a canonical UUID and is encoded. Channels/settings refuse any record ID. No raw query or path argument remains. |
| `workspace/app/trigger/actions.ts:106` — card confirmation/cancellation | Both thread and card IDs require canonical UUID format and exact length before identity resolution. The card path segment uses `encodeURIComponent`. The action remains JSON body data. |
| `workspace/app/v1/bot/widget/[operation]/route.ts:78` — config/message/handover/poll | Own-property lookup in the const `OPERATIONS` object returns the literal operation used in the URL. That constant is encoded. Unknown operations are refused before body consumption or fetch. The existing validated embed key chooses between server-configured regional Tank origins. |
| `workspace/app/trigger/[[...segments]]/page.tsx:28` and `:44` — page callers | Pass area, section and ID separately to the validated action. They no longer concatenate a request path/query. Page IDs also use the strict UUID format; CRM membership uses an own-property check rather than `in`, rejecting prototype keys. |

Other new calls audited: `proposeTrigger` always uses the literal `trigger/console/propose`; tool names/arguments are JSON body data. The visitor script calls only fixed internal operation names on the Workspace public bridge, not a user-provided Tank origin or URL. Browser navigation, source/receipt links and OAuth navigation are not server-side Tank fetches. There is no new list-ID URL call elsewhere in this PR.

## Regression proof

`tests/trigger_w4/ssrf.cjs` loads the actual server actions **and** `workspace/lib/tank.ts`, with a fetch spy at the transport boundary. Every CRM resource, each query-bearing route, both confirmation IDs, both page call sites and the widget operation route are tested with:

- `../admin`
- `%2e%2e/`
- `x?y`
- an over-long placeholder value

It also checks `/`, `..`, `#`, prototype keys, malformed 36-character UUIDs, a trailing newline and wrong runtime types. Every rejection leaves fetch counts unchanged. Server-action rejections also leave identity lookup counts unchanged, so malformed values cannot reach Clerk's identity network lookups either. Valid list/detail/query/confirm requests and all four widget operations retain their exact intended upstream URLs.

Local verification: both Workspace contract tests pass with socket blocking; TypeScript and CI's exact Ruff lint pass; `git diff --check` passes. Pushing the changes reruns PR CI and CodeQL; their actual final-head results are reported in the task handoff rather than assumed here.
