# Tank local semantic cache — shadow first

Started from main `bde4578` on `codex/tank-semantic-cache`.
Reuse pinned FastEmbed CPU embeddings and existing Qdrant. Preserve current cache
serving, tenant/policy/matter/expiry boundaries, and exact-only `command.turn`.
Collect would-be hits against real answers, reuse the judge, require at least
99% over 200 samples and explicit founder approval per task before serving.
Offline tests only, judge stubbed. No paid calls or live acceptance claimed.
Implementation and proof are in progress. Claude opens the PR; founder merges.
