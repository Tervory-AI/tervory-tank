# Market Lab supply-chain feed

This is Autumbra's first repository supply-chain feed. Market Lab owns the public
source list in `sources.py`: OSV, GitHub Security Advisories and CISA KEV. No feed
list or client screen is added to Autumbra.

Autumbra can import `inventory` and `scan` from `agents.market_lab.supply_chain`.
`inventory(Path(checkout))` reads committed locks; `scan(inventory, Client())`
returns `market_lab.supply_chain.v1`, with source credits, coverage per lock,
advisory IDs, fixed releases and exact KEV/CVE matches. Imports have no side effects.
The existing `agents.ghost.versions` pure range evaluator is reused.

Every requirements lock and Node lock is read, including inactive Python markers,
optional dependencies and nested Node versions. Forge's source locks are queried
by commit; release asset tags are resolved to commits first. Model weight locks
are recorded as data-only, not as vulnerability-free software. Unknown formats,
unresolved identities, truncated responses and unavailable sources fail the scan.
A GitHub source advisory that cannot be checked against its pinned commit also
fails coverage. A missing advisory feed never means there are no vulnerabilities.

Run the read-only scan from the repository root:

```
python3 -m agents.market_lab.supply_chain --report /tmp/supply-chain.json
```

The `supply-chain` workflow runs nightly at 02:23 UTC and can be dispatched on the
default branch. It installs no Python dependencies. It uses the Python 3.12,
Node 22 and Actions v7 choices made in #341; action revisions are immutable.

Adding `--publish` opens real dependency-fix draft PRs. Set the GitHub Actions
secret **`SUPPLY_CHAIN_GITHUB_TOKEN`** to a repository-scoped App token or fine-grained
PAT with Contents and Pull requests write access. Its value is never stored in
this repository. Normal `GITHUB_TOKEN` is used for read-only scans when that secret
is absent. Publication with missing credentials fails explicitly when fixes exist;
it does not silently create PRs whose CI cannot run. The repository must allow the
configured identity to create branches and draft PRs.

Each fix is isolated in a temporary checkout. Python fixes replace the release's
complete hash set from PyPI, update matching inputs/constraints and resolve wheels
with `pip download --require-hashes --only-binary=:all:`. Node fixes change the
manifest/override, resolve lock metadata with scripts disabled, and run
`npm ci --ignore-scripts`. The changed locks are scanned again before publication; a newly vulnerable
transitive dependency blocks the proposed fix.
No source build hooks or npm lifecycle scripts run during this process.

A package/fixed-version pair gets one deterministic branch and one draft PR across
all affected locks. Existing review branches and closed decisions are preserved.
A failed resolver does not prevent other fixes from being attempted. Source/tool
archive changes that require a reviewed rebuild, unresolvable dependency graphs,
and advisories without a verified fixed version remain in the report; the watcher
does not invent a fix. Resolver/publication failures fail the nightly run.
The watch has no merge, deployment or force-push operation.

For proof, open Actions → supply-chain → the nightly run summary. Inspect every
lock's coverage and each advisory's source IDs. Open the resulting draft PR →
Files changed for the updated versions/hashes, then Checks for install-pins,
gitleaks and the application tests. No live client page changes in this feature.

The PR gate in `secrets.yml` runs on every PR, including docs-only changes. It
checks shell commands, Python command lists and package scripts. It rejects every
new mutable install relative to the trusted PR base and prints the
inherited migration count. Running `check_install_pins.py` without `--base` is the
full-repository audit. #341 owns clearing existing migration debt.

Gitleaks scans full history with an exact fingerprint baseline of main `417eaad`:
28 existing historical findings, no secret values. Baseline validation refuses
fingerprints from commits outside the PR base. Gitleaks has a verified binary
checksum. A redacted scan is filtered against exact fingerprints; the gate exits
nonzero on a new hit or scanner failure. The wrapper forces the built-in rules and
disables repository ignore files and inline allow comments. Repository protection should require
`gitleaks` and `install-pins`; this PR does not change branch-protection settings.
