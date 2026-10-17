# First live check — lokd.co.za

Checked on 17 October 2026 from a cloud worker, not from the Radix room.
One request: `GET https://lokd.co.za/` returned 200. Nothing else was opened.

## Result

2 findings, both low. None are high. This check does not block a deploy.

| Check | Result |
| --- | --- |
| TLS | TLS 1.3. The certificate name matches `lokd.co.za`. It is valid through 2026-12-25. |
| Strict-Transport-Security | Present. `max-age=31536000; includeSubDomains` |
| Content-Security-Policy | Present. The script nonce was removed before this note was saved. |
| X-Frame-Options | `DENY` |
| X-Content-Type-Options | `nosniff` |
| Referrer-Policy | `no-referrer` |
| Cross-Origin-Resource-Policy | Missing. |
| Cross-Origin-Embedder-Policy | Missing. |

The policy on that response also names other hosts, including `clerk.lokd.co.za`,
`challenges.cloudflare.com`, `img.clerk.com`, `clerk-telemetry.com`, and
`*.protect.clerk.com`. Those names were not requested, and they are not approved.

A DNS TXT record exists for `lokd.co.za`. Its text was not read or stored.
It was not treated as ownership proof.

## What this did not do

No second host. No redirect was followed, because the home page did not redirect.
No page body was stored. No cookie was set on this response. No attack payload
was sent. `www.lokd.co.za` was not requested.

The HTTP request was allowed only after every DNS answer for `lokd.co.za` was a
public address. The HTTP client then resolved the name again, so that connection
was not pinned. The certificate check connected to the first public address and
used `lokd.co.za` as the TLS name.

## Why the room did not run this

The Radix room is still sealed.

- Its corridor `tervory-gw-radix` is an internal Docker network, so the container has no route to this host.
- `RADIX_ALLOWED_HOSTS` in `docker-compose.yml` is still empty. An application allowlist is not the egress proxy the plan requires, and a public network would open the whole internet.
- The `scan` job still accepts only a handed-over archive. `live.py` is a command for a worker that can already reach this one host. It is not a job on the service.
