# Privacy policy — Tervory for Claude

This policy covers the Tervory connector at `https://mcp.tervory.com/mcp`. It is the same text as the Privacy section of the documentation page.

## What we collect

We collect the Clerk user id and the organization id of the account you sign in with. We collect the arguments of each tool call you make from Claude, and we receive the result Tank produces for that call.

We do not ask you for an API key. The keys that reach Tank and Clerk stay on the Tervory server.

## How we use it, and storage

We use the organization id to keep every call inside that organization’s data. We use the tool arguments only to perform the tool you invoked.

Sign-in state is stored so Claude can stay connected: an authorization code for a few minutes, and a refresh token for 30 days. Refresh tokens are stored as a hash. Enriched business rows and price watches are stored in that organization’s Tervory account.

## Third parties

Clerk confirms your identity. Claude, the product you connected, sends the tool call and receives the answer. Tank, operated by Tervory, runs the catalogue search, the record lookup, the enrichment, the legal scope check and retrieval, the market brief, and the price watch. Answering a market brief or a legal question may cause Tank to read a public page or call a model that Tervory has configured.

We do not sell this data.

## Retention

Authorization codes expire within minutes. Refresh tokens expire after 30 days. If an old refresh token is presented again after it has been replaced, that connection is signed out. Access tokens expire after one hour. Records you enrich, and prices you watch, remain in the Tervory account until they are removed in the app.

## Contact

Email support@tervory.com. Do not include access tokens or passwords.
