# Tank local semantic cache — stopped at encoder artifact access

**Blocked under founder rule 9. No cache implementation changes.**

The managed cloud environment rejected the request to the public Hugging Face
model repository with a CONNECT-tunnel HTTP 403. No cached ONNX encoder/tokenizer
files were found in the checked cloud workspace/cache locations. A real local
encoder cannot be proved without those artifacts; substituting hashed vectors or
mock embeddings would not satisfy this job.

Missing: the pinned local encoder artifacts (ONNX weights, tokenizer and model
configuration) and a verifiable immutable revision, accessible in this managed
cloud environment. No alternative route, proxy, owner laptop or production service
was used to get around the blocked request. No retry was made.

## Scope and completed work

Started fresh from main `bde4578` on `codex/tank-semantic-cache`.
Read `AGENTS.md`, `docs/cursor/CONTEXT.md`, the milestone rules block, the cache,
existing judge/graduation paths, Hermes embeddings/Qdrant wiring and savings report.

Existing components identified for reuse:

- `hermes/requirements.txt:7` pins `qdrant-client==1.20.0`; line 9 pins
  `fastembed==0.9.1`.
- `hermes/embeddings.py:17` wraps CPU FastEmbed with
  `BAAI/bge-small-en-v1.5`, 384 dimensions. The Hermes image downloads model files
  at build time; those files are not in this source checkout.
- `tank/main.py:1006` binds cache identity to tenant/region, policy revision,
  system context, matter, skill and generation limits.
- `tank/main.py:1510` contains the existing shadow comparator/judge path.
- `tank/proof.py:123` and `workspace/app/tank/proof/view.tsx:63` already expose
  per-task shadow comparisons, so the implementation should reuse existing
  reporting before considering any new page text.

The existing pinned FastEmbed and Qdrant Python packages installed successfully
into the cloud-only test virtual environment. Model weights are not included in
those Python packages. No real encoder was loaded or exercised.

## Exact commands and observed results

Setup (managed cloud `/workspace/tervory-tank`):

```sh
git status --short
git fetch origin main
git switch -c codex/tank-semantic-cache origin/main
```

Clean starting tree, main advanced to `bde4578`, branch created. Initial scope was
committed as `107c785` and pushed immediately:

```sh
git add tests/tank_semantic_cache/PR.md
git commit -m 'Record shadow semantic cache scope and acceptance requirements'
git push -u origin codex/tank-semantic-cache
```

Package setup:

```sh
/workspace/worker-venv/bin/pip install --cache-dir /workspace/scratch/pip-cache fastembed==0.9.1 qdrant-client==1.20.0 > tests/tank_semantic_cache/install.txt 2>&1
```

Exit 0. [Complete package-install output](install.txt). This changed only the cloud
virtual environment, not repository requirements or any production image.

Model revision lookup:

```sh
git ls-remote https://huggingface.co/Qdrant/bge-small-en-v1.5-onnx-Q HEAD
```

Observed stderr, transcribed from the tool output:

```text
fatal: unable to access 'https://huggingface.co/Qdrant/bge-small-en-v1.5-onnx-Q/': CONNECT tunnel failed, response 403
```

No revision was returned. This command was in a shell cell with subsequent source
reads; the cell's final exit code reflected those reads, not a successful git lookup.
The failed operation was the remote model-repository lookup, and it did not execute
any download, model inference or remote write.

Cached-file checks:

```sh
rg --files /workspace /opt -g 'model_optimized.onnx' -g 'model.onnx' -g 'tokenizer.json' -g '*fastembed*' -g '!node_modules/**' 2>/dev/null | head -30
ls -d /home/agent/.cache/fastembed /home/agent/.cache/huggingface/hub/models--Qdrant--bge-small-en-v1.5-onnx-Q /opt/fastembed 2>/dev/null || true
```

No files/directories returned at the time of these checks. These paths are on the
provisioned cloud machine, not the founder's laptop.

Final evidence check and push:

```sh
git diff --check
git add tests/tank_semantic_cache/PR.md tests/tank_semantic_cache/install.txt
git commit -m 'Record semantic encoder artifact access blocker'
git push -u origin codex/tank-semantic-cache
```

## Files changed

- `tests/tank_semantic_cache/PR.md:1`: scope, observed blocker and command proof.
- `tests/tank_semantic_cache/install.txt:1`: package-install output.

No Tank, Hermes, Qdrant, policy, schema, UI, dependency manifest or compose source
was changed. Today's served cache and exact-only `command.turn` remain untouched.

## Acceptance not performed

No paraphrase, number/negation, isolation or graduation tests were run, because the
real encoder required by this brief is unavailable. No judge/model API calls,
production SQL, secret access, GitHub API, deployments, merges or live promotions
were performed. There are no founder-browser screenshots or live savings results;
none are claimed. Claude opens the PR; the founder merges.
