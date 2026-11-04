# Trusted security comparison bases

## Independently verified defect

On 4 Nov 2026, PR #329's API/event metadata advertised base
`feccd797c598772e0900d82234a784305fb79551`, while its fetched synthetic merge
`9b481be0ce6baafd4389c31129f52e9e8e878701` had parents:

1. Trusted main `fa34a9f0d9e8323358ebb47c82ba5e9f2eed9fab`.
2. PR head `0015cb6c813d4bf95d3298e1a17f25fb206db44a`.

The old workflow scanned the merged tree against the stale advertised base.
Its final-head run 41822645173 reported 3 Gitleaks, 58 Semgrep and 56 OSV
findings, none in #329's changed files. The Gitleaks commits `77b505ae` and
`0dc98c9e` were verified ancestors of current main. This does not clear those
findings: it distinguishes existing-main audit findings from PR-introduced ones.

The new selector was independently run on that actual fetched merge in an owned,
detached proof checkout. It selected `fa34a9f0`, leaving exactly the 13 #329
changed files in the comparison. #329's branch remains fixed at `0015cb6c`.
No scanner rules, ignores, baselines, protection settings or product/runtime
files are changed by this CI PR.

## Selection contract

`ci.security` passes `--event-context` to all three scanner invocations.
The shared selector reads GitHub's event file, validates full commit SHAs and
the checked-out Git graph, and fails closed if the context cannot be verified.

| Event | Comparison |
| --- | --- |
| `pull_request` | Require target `main`, exactly two merge parents, and second parent equal to the event PR head. Require the advertised base to be an ancestor of the first parent and that first parent to belong to fetched `origin/main`. Use that verified first parent, not moving main or the stale event SHA. |
| `merge_group` | Require main as target, checkout equal to event `head_sha`, and explicit `base_sha` to be an ancestor of the checkout and trusted main. Use the explicit group base, never a guessed first parent that could exclude earlier queued PRs. Reject empty ranges. |
| Legacy main `push` | Verify target/after checkout and the before commit's ancestry. Preserve the explicit before/after range; an all-zero before means whole audit. |
| `workflow_dispatch` or `schedule` | Whole audit (`base=null`). Do not fall back to `origin/main`, which could compare a main checkout to itself and hide every finding. |

Missing trusted refs, invalid events, wrong heads, head-only checkouts, swapped or
octopus PR parents and unrelated base parents result in `incomplete` and nonzero
exit before any scanner runs. Status artifacts retain the verified selected base;
raw event contents and exception messages are not printed.

The existing weekly workflow still omits `--base` and is unchanged. Explicit CLI
`--base` remains available separately and cannot be combined with event selection.
GitHub documents the [PR merge checkout and merge-group event SHA semantics](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows).

## Coverage and interpretation

Gitleaks still scans every PR-unique commit in `base..HEAD`; Semgrep still compares
the checked-out tree with that base; OSV still rejects every newly vulnerable
version/advisory identity at any severity. Their actual scan functions, thresholds,
redaction, completeness checks and error behavior are unchanged. A genuine new
finding remains a failed incremental scan.

Whole audits deliberately retain existing repository findings: all Gitleaks hits,
high Semgrep findings, and high/critical or unknown-score OSV findings still fail
under the existing policy. A failing whole audit is not evidence of this stale
incremental-base defect. CI manual dispatch now explicitly performs a whole
security audit rather than silently scanning an empty main-to-main range.

Focused regressions use isolated real Git graphs plus scanner-entrypoint checks.
They cover stale/current bases, trusted-main advancement, invalid graph/context,
merge-group scope, push and whole-audit modes, and findings remaining nonzero for
all three scanners. Existing scanner-policy tests continue to cover genuine
vulnerabilities, scanner/report failures and redaction. No full app suite is run
locally; final-head hosted CI supplies the review evidence. No deployment or
automatic merge is requested.
