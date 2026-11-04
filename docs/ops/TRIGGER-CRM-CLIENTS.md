# Bind a client's BottleCRM organisation

Founder decision 33, 3 November 2026: one BottleCRM organisation per client.
The signed-in Tervory tenant selects the binding. Requests cannot select another
organisation, and an unbound tenant receives the existing configuration refusal.

The founder performs these steps; agents handle setting names only and never
inspect, create, copy, log or commit token values.

1. Create the client's organisation in BottleCRM.
2. In that organisation, create its API token.
3. Store the token in Coolify under a new unique setting name matching
   `TRIGGER_CRM_PAT_[A-Z0-9_]{1,60}`. Use a distinct token and setting for each tenant.
4. In `TRIGGER_CRM_TENANT_BINDINGS`, add the signed-in tenant UUID mapped to an
   object with exactly `token_env` and `organization_id`. `token_env` names the
   new setting; `organization_id` is the organisation UUID from BottleCRM.
   Preserve existing entries. Never use a token value in this mapping.
5. Ensure the named token setting is passed to the Tank container. A setting name
   newly wired through Compose belongs in `.env.example` and the relevant Compose
   file, in its own runtime-config PR before relying on it. The founder supplies
   all values in Coolify. This gate introduces no new fixed setting names.
6. Redeploy Tank after the configuration is available. BottleCRM must run the
   organisation-attestation connector image (the separate #601 fix). Tank refuses
   missing or mismatched attestation, including before writes.

Tervory creates neither organisations nor bindings in a database. Duplicate
organisation IDs, setting names or tokens are refused; there is no fallback.
Only the founder and the signed-in tenant's admins receive the CRM tools.
Ordinary members cannot use them.

## Founder browser acceptance

Use the founder's own workspace and test tenant, never a client workspace.
After binding that tenant, sign in as its tenant admin and use `/chats`:

- Enter `trigger.crm.list leads` and confirm its existing pending card. Verify
  that the collection contains only that organisation's leads.
- Enter `trigger.crm.write` followed by a JSON object using the existing
  `resource` and `data` contract for a real contact. Confirm the existing write
  card, then enter `trigger.crm.list contacts` and confirm the read card to
  verify the contact exists in that organisation.
- Sign in to a second tenant of the founder's own with no binding. Confirm its
  CRM list card and verify the existing configuration refusal.

`trigger.crm.get` accepts the resource followed by the record UUID. List commands
accept an optional JSON object of the existing query keys: `page`; contacts also
accept `name`; leads also accept `title` and `status`. All three commands also
accept a JSON arguments object. Explicit CRM commands are planned in code.
Reads retain the existing pending-card confirmation in `/chats`, but require no
write-confirmation dispatch context. Reads and writes record code receipts at
$0 with zero model calls.

No page, labels or visible wording are added. `resource` and `record_id` stay in
data; showing either as a new card label requires an approved Figma frame.
Founder browser screenshots and exact-head hosted CI results must be supplied
with the review evidence. Offline tests do not establish live acceptance.
