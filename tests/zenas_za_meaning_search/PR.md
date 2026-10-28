# Zenas: regional meaning search and South African criminal refusal

Branch: `codex/zenas-za-meaning-search`, started from main `678d47e` (includes Laws.Africa #382).
Claude opens the draft PR; the founder merges.

## Scope and decisions

- Reuse the existing local CPU embedder in Hermes and the box-local Hermes → Qdrant path. No new external embedding service, provider key, or direct agent access to Qdrant.
- Pin the model name and revision; image dependency layers download it before the application code is copied. No model download or inference in this cloud. Offline tests use stub encoders.
- Wire public-law collections law_za / law_us with region enforcement, incremental section indexing, and combined keyword/meaning retrieval that retains stored citation provenance.
- Extend only the criminal scope terms, keeping the existing refusal wording and civil scope rules.

Implementation and verification are in progress. Founder live screenshots and acceptance are pending; no live-success claim is made.

## Step 1: local encoder and regional vector service

- `hermes/model.json` pins BAAI/bge-small-en-v1.5 to Qdrant/bge-small-en-v1.5-onnx-Q revision `aa8f8b060edb00e03bfdd08813a2949946c8ba55`. Verified with `git ls-remote https://huggingface.co/Qdrant/bge-small-en-v1.5-onnx-Q HEAD`; no model weights downloaded here.
- `hermes/Dockerfile` downloads that snapshot in its dependency RUN before copying application code. `hermes/embeddings.py` loads the fixed local directory with CPUExecutionProvider and local_files_only; no runtime metadata lookup or download. The existing fastembed==0.9.1 dependency is reused.
- Private law routes use the existing Zenas room authentication. Region and model checks precede encoding, reads and writes. The box's existing Qdrant connection owns law_za or law_us; tenant memory routes retain their existing behavior.
- Boston Hermes now explicitly receives TANK_REGION=us-east; ZA already receives za. No Qdrant network exposure or new key is added.

Commands run on the cloud:

```sh
/workspace/.tervory-cloud/venv/bin/python -m pip download --no-deps --dest /tmp/zenas-meaning-deps fastembed==0.9.1
/workspace/.tervory-cloud/venv/bin/python -m pip install qdrant-client==1.20.0
env -u RIG_TEST_DATABASE_URL -u POOL_SCHEMA_DATABASE_URL -u ZENAS_SCHEMA_DATABASE_URL -u GITHUB_ACTIONS PYTHONPATH=. /workspace/.tervory-cloud/venv/bin/python /tmp/zenas-laws-africa-offline.py -q tests/zenas_za_meaning_search/test_hermes_law.py tests/test_hermes_memory.py
/workspace/.tervory-cloud/venv/bin/ruff check hermes/law_store.py hermes/law_routes.py hermes/embeddings.py tests/zenas_za_meaning_search/test_hermes_law.py --output-format concise
git diff --check
```

Results: fastembed **wheel only** inspected for specific_model_path support (not installed; no model weights); Qdrant client installed for its in-memory implementation; **15 passed in 8.20s**, one existing Starlette/AnyIO deprecation warning; Ruff passed; diff check passed. The offline runner rejects all IPv4/IPv6 socket.connect events. Tests stub the encoder and exercise real HTTP routes and Qdrant local queries. The image was not built in this cloud, because its build downloads the model and the brief reserves that download for the box.
