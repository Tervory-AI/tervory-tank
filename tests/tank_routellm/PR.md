# RouteLLM shadow candidate — blocked before implementation

Branch: `codex/tank-routellm`, created from `origin/main` at
`a99f3cb0662516c8fe1b3f27d5b5dcbb90e94fa0`.

This is an audit and blocker record, not a completed implementation or a request
to merge. No application code, schema, dependency, policy or live data changed.
Do not open the implementation PR from this documentation-only commit.

## What changed

- `tests/tank_routellm/PR.md:1`: records the existing integration points, the
  dependency inspection and the network blocker. This is the only changed file.

## Existing behavior inspected

- `tank/main.py:1059`: `run_route` loads a policy and returns the primary model's
  answer. The existing candidate shadow is scheduled after the primary ledger
  write; it does not replace the answer.
- `tank/main.py:1507`: `_shadow` executes the candidate through Tank, uses
  `graduate.compare` for structured answers or the existing judge for text,
  stores agreement in `tank.shadow`, and writes the shadow cost to the ledger.
  Evidence belongs to the request tenant; paid shadow spend belongs to the
  platform tenant. Candidate cost currently includes judge cost. A future
  hypothetical saving must distinguish model cost from evaluation overhead.
- `tank/graduate.py:23`: the default agreement threshold is 0.99 and minimum
  sample count is 200. `promote_if_proven` at line 436 holds an automatically
  evaluated candidate even after it is proven. The explicit promotion endpoint
  in `tank/main.py:2084` requires founder administration permission.
- `tank/main.py:1616`: graduation loads candidate evidence by task and candidate.
  RouteLLM-selected easy-turn samples must not silently qualify an unconditional
  weak model for every turn. Their scope needs to remain explicit.
- `tank/proof.py:131`: existing proof comparisons aggregate primary/candidate
  costs and agreement per task. `workspace/app/tank/proof/view.tsx:63` already
  renders comparison figures on the founder's proof page. This is the existing
  display surface to reuse without adding wording.

## RouteLLM inspection

Read the public upstream repository at
`0b64fdafe049e596a3f5657c219329f24af24198` and the PyPI metadata for release
`0.2.0`. Its BERT implementation is `BERTRouter` in
`routellm/routers/routers.py:106`; the default checkpoint is
`routellm/bert_gpt4_augmented`. It calculates a strong-model win probability
locally using a sequence-classification model and tokenizer.

Importing the upstream router module also imports an unrelated router utility
that constructs `OpenAI()` at module scope
(`routellm/routers/similarity_weighted/utils.py:11`). The CPU-only integration
must avoid requiring a provider key or running that embedding router. No
dependency adaptation has been implemented or tested.

## Blocker and observed result

The managed cloud environment has enforced restricted HTTP access, and
`huggingface.co` is not allowed. A Python `urllib.request` request through the
inherited proxy to the public checkpoint configuration at
`https://huggingface.co/routellm/bert_gpt4_augmented/resolve/main/config.json`
failed with:

```text
OSError: Tunnel connection failed: 403 Forbidden
urllib.error.URLError: <urlopen error Tunnel connection failed: 403 Forbidden>
```

Missing: cloud network access to `huggingface.co` to inspect and download the
required open checkpoint. Its immutable revision, artifact downloads and CPU
execution have not been verified. Any download redirect destinations must also
be permitted through the supported cloud environment settings.

Stopped under rule 9 in `docs/build/MILESTONES-28OCT-1NOV.md:57`: “If something
blocks you ... stop at that point and report exactly what is missing.” No
alternate host, proxy bypass, paid router or invented checkpoint pin was used.

## Commands and validation

Executed in the cloud worktree `/workspace/tank-routellm`:

```sh
git rev-parse HEAD
# a99f3cb0662516c8fe1b3f27d5b5dcbb90e94fa0
git -C /workspace/routellm-upstream rev-parse HEAD
# 0b64fdafe049e596a3f5657c219329f24af24198
git ls-remote --heads origin codex/tank-routellm
# a99f3cb0662516c8fe1b3f27d5b5dcbb90e94fa0 refs/heads/codex/tank-routellm
```

These establish the audit bases and the initial branch push, not working
RouteLLM integration. Application tests, image build, real-Tank RouteLLM run,
browser proof and founder screenshots have **not** been completed. No CI result
is claimed. The GitHub API was not used.

## Decisions I made

- Preserve the existing shadow runner, judge, ledger and founder graduation
  gate as the integration points; do not implement a competing router.
- Keep the branch at audit-only scope when checkpoint access was denied.
- Record the blocker here without adding product text or changing live policy.

## Browser proof still required

After implementation and review, enable RouteLLM for one policy using the
founder's chosen weak model and threshold. On the founder's existing
`/tank/proof` page, verify that the task's comparison figures reconcile with
its real ledger costs. Verify the original policy model still answers live,
and that evidence and samples remain tenant-scoped. Capture the founder's
browser proof then; no such screenshot exists for this audit-only branch.
