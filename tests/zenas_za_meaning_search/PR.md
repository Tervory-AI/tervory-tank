# Zenas: regional meaning search and South African criminal refusal

Branch: `codex/zenas-za-meaning-search`, started from main `678d47e` (includes Laws.Africa #382).
Claude opens the draft PR; the founder merges.

## Scope and decisions

- Reuse the existing local CPU embedder in Hermes and the box-local Hermes → Qdrant path. No new external embedding service, provider key, or direct agent access to Qdrant.
- Pin the model name and revision; image dependency layers download it before the application code is copied. No model download or inference in this cloud. Offline tests use stub encoders.
- Wire public-law collections law_za / law_us with region enforcement, incremental section indexing, and combined keyword/meaning retrieval that retains stored citation provenance.
- Extend only the criminal scope terms, keeping the existing refusal wording and civil scope rules.

Implementation and verification are in progress. Founder live screenshots and acceptance are pending; no live-success claim is made.
