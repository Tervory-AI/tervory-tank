# Tervor Code: isolated behaviour smoke evaluation

From the repository root on supported Linux:

```sh
python3 -m tank.tervor_code_behaviour --dry-run --demonstrate-controls
```

Exit **2** means fixture execution finished and training preflight is blocked.
Exit **3** means required execution infrastructure is unavailable. There is no
host fallback, submit option, trainer, model call, service activation or deployment.
The command never runs answer-provided shell commands. To evaluate saved answers,
add `--predictions answers.json --split gold` (or `validation`), using #781's
complete final `files` map and `commands` array. The manifest/test selection is
fixed by the repository; predictions cannot supply tests or test commands.

This extends #781's public MIT source, evaluation-only synthetic examples,
provenance hashes, split snapshots, platform tenant and registry conventions.
`behaviour.json` declares permitted changes, calls, expected results and mutation
controls for all eight original tasks. Family hashes use stable upstream/source
references, without revisions, and cannot cross train/validation/gold. The
existing loader additionally rejects source/content/provenance overlap and
private data. Tests have their own hashes and cannot cross splits. This is source
family separation, not a claim to detect arbitrary semantic near-duplicates in
future corpora. Synthetic fixtures remain barred from training.

Candidates are applied as text in fresh disposable directories. Bubblewrap
binds only that disposable source and a copied trusted worker, plus the system
Python executable and read-only system libraries. It mounts no checkout, home,
secret, Docker socket or host process filesystem. The root and source are read
only; `/tmp` is a fresh 16 MiB tmpfs. The candidate runs as UID/GID 65534 and PID 1
in new user, PID, network and other namespaces with all capabilities removed,
further user namespaces disabled, an empty inherited environment, no site
packages, and no inherited nonstandard file descriptors. No Docker is needed.
The local rootless Docker daemon had no cgroups, so its limits were not used.

Before any workspace import, the trusted worker installs no-new-privileges,
hard resource limits, and a native-architecture seccomp **allowlist**. Unlisted
syscalls fail with EPERM, including socket/network operations, exec, fork/clone,
IPC, io_uring, ptrace, mount and resource-limit changes. This enforces one process
and no threads without relying on unavailable cgroups. The one process has a
128 MiB address-space limit; `/tmp` storage is separately bounded. CPU soft/hard
limits are 1/2 seconds, wall deadline 3 seconds, open files 32, and core dumps zero.
Stdout and stderr each use a fresh file with a hard 16 KiB file-size limit; only
bounded reads and hashes enter the report. On wall timeout the host kills the
supervisor process group; die-with-parent and PID-namespace teardown kill the
isolated child. Candidate processes cannot exec another interpreter or shell.

A trusted probe must confirm denied network/process/exec, protected writes,
host-path access and limit increases, UID/environment and closed extra file
descriptors. Any missing Bubblewrap feature, libseccomp, library layout, namespace
permission or probe failure blocks candidate execution. The worker also refuses
accidental direct host invocation before reading input. Bubblewrap's separate
status FD identifies namespace setup failures as infrastructure errors; test
failures, exceptions, malformed output, resource exits and wall timeouts remain
candidate outcomes. A signal exit is labelled `cpu_or_signal_limit`, rather than
claiming an unobserved OOM or exact CPU cause. Bootstrap/runtime dependencies are
not installed or enabled automatically. This implementation supports the probed
Debian/Ubuntu system-Python layout; other layouts fail closed.

Expected outputs and the authoritative judge stay outside the candidate process.
For each predeclared call a new sandbox imports the candidate and returns a
bounded JSON result. The host compares that result with the predeclared expected
value; it does not accept an exit code or a candidate's “tests passed” claim.
Mutation tests check that candidate-authored tests pass the correct implementation
and reject a known wrong implementation. Shared-constant mutation checks verify
that a multi-file patch uses the renamed setting. Repository-rule checks protect
unchanged files such as AGENTS.md and the implementation in test-only tasks.
The command-plan fixture is explicitly `contract_only`; it is not counted as an
executed coding function. Four of the five gold tasks execute Python behavior.

The checked-in local measurement is
[evidence/tervor-code-behaviour-2026-11-08.json](evidence/tervor-code-behaviour-2026-11-08.json).
It records source, test, patch, worker, Python executable and Bubblewrap hashes,
actual per-call elapsed times, exit codes, output sizes/hashes and limit outcomes.
The public training-split task is used only as a harness control, separately from
held-out scoring. Reference controls pass 1/1 public, 2/2 validation and 5/5 gold;
no-change controls fail all of them. A syntactically valid wrong patch fails;
an equivalent alternate implementation passes the entire interval test list.
Test-file/path/host-command tampering is refused before launch. Runtime test
writes, host escape, network and process attempts fail within isolation; network
and process attempts report PermissionError. Sleeping times out; infinite-loop,
large allocation and output flood controls show their respective bounded outcomes.

Reproduce the additional public/validation controls with `report(data, spec,
split='train')` and `report(data, spec, split='validation')`, after loading the
baseline and manifest through their existing loaders. Timing values naturally
vary between runs. The report's worker/source/test hashes detect stale evidence.

These are visible fixture/harness controls, **not real model quality**, secret gold,
proof against every kernel exploit, or 200 independently reviewed gold cases.
A candidate can overfit public test inputs; broader independent tests and sandbox
security review are still required before accepting arbitrary external submissions
as a service. No model checkpoint is selected and no promotion is possible:
`eligible` and `model_quality_measured` are always false. Training preflight keeps
base checkpoint/revision/licence and cost null. Founder-approved base evidence,
a coding-capable trainer, reviewed gold, calibrated Tank/DeepEval and shadow gates
remain prerequisites. Pending M7/M14/M8/M9 interfaces are consumed through #781;
this PR changes none of their owners' billing, trainer or serving gates. All
fixture execution costs zero provider dollars and starts no paid/GPU job.

Focused CI contract tests always run. Where a CI runner lacks secure namespaces,
the integration test proves the infrastructure-error path with no candidate
execution or skip; the checked-in Cloud measurement proves actual execution on
the recorded supported backend. Hosted security and existing repository checks
remain unchanged. No runtime Compose configuration belongs to this source PR.
