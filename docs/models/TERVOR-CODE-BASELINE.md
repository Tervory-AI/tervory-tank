# Tervor Code offline baseline for Opli Code

Run from the repository root, with Python 3.12 and no credentials:

```sh
python3 -m tank.tervor_code --dry-run
```

The command emits one deterministic JSON comparison and reaches local training
preflight. Exit **2** means blocked before submission. It has no submit option,
HF client, network operation, model download, shell execution or database write.
`--predictions answers.json --split gold` scores externally obtained answers;
the JSON maps every selected case ID to `{"files": {"relative/path": "content"},
"commands": [["git", "diff", "--check"]]}`. Commands are inspected, never run.
The answer contains the complete final file map. Missing/extra files fail exact
comparison, so repository rules and changes across files are visible.

The checked-in smoke set contains one training task derived from public PyPA
sampleproject MIT code, two synthetic validation tasks, and five synthetic gold
tasks: multi-file patch, bug fix, test addition, command safety and repository
rules. Upstream commit is `621e4974ca25ce531773def586ba3ed8e736b3fc`;
`src/sample/simple.py` and `LICENSE.txt` were retrieved at that commit. Unmodified
source and full copyright/licence notice are retained beside the fixtures, with
raw SHA-256 evidence. The training input deliberately mutates subtraction; its
completion restores the public upstream implementation. No teacher completion,
private tenant data or provider-generated answer enters training. Synthetic
fixtures are explicitly evaluation-only and may not move into training.

Every record carries source-content and provenance hashes. Cross-split source,
provenance, input, expected answer and individual file overlap is refused;
duplicate inputs are refused even within a split. Splits are assigned explicitly,
never by random row sampling. This protects this small sealed corpus against
copies and rewrapped sources, not arbitrary semantic paraphrases in future
corpora. New public sources need independent licence evidence and review.

`no_change` and `reference_oracle` are deterministic controls, not trained models.
The score is exact final patch plus Python syntax and an explicit command
allowlist. Equivalent alternate implementations can fail; code is never executed,
so passing does not prove behavior or security. Gold answers are visible review
fixtures, not a secret production benchmark. The report is always offline-only
and ineligible for promotion, even with a perfect oracle score. Five fixtures do
not satisfy the 200 independently reviewed gold cases or calibrated DeepEval and
shadow gates. Cost of this command is zero provider dollars; real training cost
is unknown. The founder's $100 ceiling does not authorize launching a job.

Integration uses current-main `tervor_registry.digest`, `encoded` and `identity`.
`shared_bundle()` consumes M7 `build()` and M14 `verify()` when those modules land,
with the existing platform tenant, `opli` product, row tags, held-out flags and
bundle hashes. It passes validation and gold inputs into M7's exclusion guard.
It does not persist fixtures as reviewed gold or forge model-card/DeepEval scores.
M8's paid current-rung evaluation remains a separate gate. M9's coding agent
support and a larger reviewed gold set are still required; this PR does not edit
shared training, billing, serving or promotion gates. PRs #751/#752/#753/#756/
#759/#760/#761 remain owned by their existing branches.

`tervory-build/MODEL.md` names only “a Qwen coder base” for Tervor Code. There is
no approved exact coding base ID, immutable revision or licence evidence to copy.
The legacy Qwen3-4B training default and M3's tiny CPU fixture are not coding base
approval. Preflight therefore reports those fields as null, ignores ambient HF
settings, and cannot create a registry manifest. The exact missing choice is the
founder's coding checkpoint ID plus immutable revision and commercial licence
proof. Hardware fit, current quote, run duration and explicit launch approval
must follow that choice. No base, endpoint, upload, promotion or deployment is
selected here.
