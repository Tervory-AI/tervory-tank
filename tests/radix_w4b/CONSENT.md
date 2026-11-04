# Wave 4b item 1 — client active-scan consent

Audit: fetched main `981ac096` and PR #651 at `d128cc8b`; neither has client consent. Work remains on the explicitly requested `codex/radix-w4`, with no main merge/rebase and no PR mutation.

A Radix-enabled tenant admin can Confirm `radix.active.consent <domain> <written text>` and `radix.active.consent.withdraw <domain>` in /chats. Text is retained verbatim with tenant, domain, user, timestamp and immutable consent id; withdrawal retains the audit row with withdrawing user/time. Both write existing $0 code receipts. Other members cannot see or dispatch these tools. Client active.scan is admin-only, tenant/product checked and exactly Confirm-bound; it uses that tenant/domain's current unwithdrawn consent and own TXT proof. The run binds its consent id. Admission rechecks that id before the TXT lookup, and the TXT proof is rechecked before any target request. No consent or withdrawn consent causes no target request. Withdrawal explicitly revokes a live client lease; maintenance also checks it every 15 seconds. Completion cannot promote a revoked lease.

The founder continues to use the unchanged `active-domains.json` list, currently `["tervory.com"]`. The separate active plan, bounds, findings and one-running database lock remain shared between founder and consented client scans. No new page, label, email, provider, key or paid route.

**Missing frame: approved written client active-scan consent wording.** No such text was found in the repository. The tool requires the admin's supplied written text and does not generate or pre-fill legal copy. It is not claimed to validate that text against an unavailable approved version.

## File/line changes

- `agents/radix/passive_store.py:75`: consent audit table and bound run id; `:202` tenant/domain consent, withdrawal and validation; `:229` bind/create run only with current consent or founder policy.
- `agents/radix/schema.sql:83`: additive idempotent schema above generated memory, joining existing RLS policies.
- `agents/radix/active_routes.py:16`: refuse client scans before gateway requests without consent.
- `agents/radix/active_tools.py:18`: canonical target validation; founder policy or tenant consent is enforced by run admission, not by rewriting the founder list.
- `agents/radix/passive_gateway.py:76`: runtime consent admission; `revoke_withdrawn` closes withdrawn leases and maintenance retries revocation.
- `agents/radix/passive_routes.py:157`: private consent/withdrawal routes and trusted client-mode dispatch.
- `tank/radix_passive_routes.py:47`: tenant admin/product plus exact durable Confirm checks and trusted room headers.
- `tank/command.py:47`: tools, admin visibility, argument models, adapters, confirmed dispatch and $0 receipts.
- `tank/radix_watch.py:10`: explicit code planner preserves supplied consent text, including line breaks.
- `tests/test_radix_active_consent.py:1`: offline consent, isolation, withdrawal, live lease revocation, runtime proof and real Confirm/receipt coverage.
- `tests/test_command_radix_active.py:20`: update previous founder-only expectations for explicitly authorized client admins.

## Verification

Consent plus existing active/passive regression selection: 68 passed, 3 warnings in 7.45s. The final focused selection additionally tests fresh TXT acceptance/refusal; its result is recorded in CONSENT-PROOF.txt. Tests use disposable loopback Postgres, fake DNS/scanners and fake room HTTP. No live domain was scanned. Exact CI lint and changed-room lint run before push. Hosted CI/live acceptance follow review and merge.
