# zenas.retrieve

## 1.1.0
- A South African case query can include SAFLII excerpts. Pages already in the payload are read with no network. A live search uses SearXNG, then Brave, then a public web search when that network is missing, then SAFLII's own search. A live fetch opens real Chrome and reuses its cookies. A Cloudflare check, or a 403 after that check, is reported as blocked.

## 1.0.0
- First version. Citation, full text, then meaning, filtered by jurisdiction and as-at date. Code only.
