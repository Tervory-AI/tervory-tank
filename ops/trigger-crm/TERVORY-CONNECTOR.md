# API user: tervory-connector (no token in git or chat)

Founder creates this **after** signing in at `https://crm.tervory.com` (Access gate already on). Agents never create or display the personal access token.

## 1. Org user

1. Sign in as the founder admin (`ADMIN_EMAIL`).
2. In the founder organisation, create a member named **`tervory-connector`**.
3. Role: the narrowest org role that may create/edit leads, contacts and estimates (typically a non-admin sales/user role that still has write on those objects — prefer USER with those module permissions over ADMIN).

## 2. Personal access token (founder only)

Path in the product: **Settings → API Tokens** (BottleCRM profile tokens).

Create a token owned by **`tervory-connector`** with **only** these scopes (estimates are under the `invoices` API resource):

```text
leads:read
leads:write
contacts:read
contacts:write
invoices:read
invoices:write
```

Do **not** use empty scopes (`[]` = unrestricted). Do **not** grant `org`, `webhooks`, `automation`, `profile`, or `*:write`.

Store the raw token only in the founder’s secret store / Coolify env if a future connector needs it. **Never paste it into chat, git, PR comments, or screenshots.**

## 3. Auth header shape (for later connectors)

```text
Authorization: Bearer bcrm_pat_…
```

or

```text
Token: bcrm_pat_…
```

Org API keys are read-only and must not replace this PAT.
