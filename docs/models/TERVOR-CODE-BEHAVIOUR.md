# Tervor Code: isolated observations, grading blocked

```sh
python3 -m tank.tervor_code_behaviour --dry-run --demonstrate-controls
```

Exit **2** means grading/training is blocked; **3** means required isolation is
unavailable. No successful behavior grade is available from this implementation.
Saved predictions still use #781's final `files` map and `commands` array via
`--predictions answers.json --split gold` (or `validation`). Candidate commands
never execute. There is no host fallback, paid call, trainer, service activation,
model selection, upload, promotion or deployment.

## Result integrity correction

Review of head `73f7e216fcd771b63374db82d5defe14744ec14b` reproduced an exact-envelope
forgery: candidate import code writes `{"kind":"return","value":16}` to stdout
and calls `os._exit(0)` without defining or invoking the requested function. The
old host comparator accepted that envelope. The earlier `{"passed":true}` control
only showed a schema mismatch and did not address this attack.

The worker imports candidate code in the same Python interpreter as invocation
and serialization. Candidate code can also monkeypatch `json.dumps`, inspect
worker frames, modify globals/builtins, or forge expected exception envelopes.
An extra nonce, marker, file descriptor or same-interpreter “trusted” function
would not establish a grading boundary against arbitrary Python introspection.

**All Python results are now untrusted observations.** Matching return/exception
claims are `integrity_unverified`, with `passed=false`. The evaluator also refuses
to grade an adapter that simply reports `completed`. `claim_matches_expected` is
explicitly diagnostic: the exact-envelope attacks set it true and still cannot
pass. Ordinary reference code also cannot earn a trusted behavior pass. The
schema-2 report has `status=grading_blocked`, `grading.available=false`, zero
behavior passes, and separate counts for host-only command-plan contract checks.
It remains `eligible=false` and `model_quality_measured=false`.

The earlier 1/1 public, 2/2 validation and 5/5 gold passing-grade claims are
**retracted**. They were unauthenticated observations, not valid behavior grades.
The replacement [local evidence](evidence/tervor-code-behaviour-2026-11-08.json)
records only focused exact-envelope, early-exit, serializer monkeypatch,
introspection, forged exception, ordinary-reference and wrong-code observations.
It binds current source/test/harness/worker/executable hashes and preserves
elapsed times, exit codes and bounded output hashes. No broader local suite or
limit demonstration was repeated for this correction.

A trustworthy independent grading boundary is now an explicit remaining gate.
This PR does not claim to have built one. Founder-approved checkpoint/revision/
licence, a coding-capable trainer, 200 independently reviewed gold cases,
calibrated Tank/DeepEval and shadow evidence also remain prerequisites. No base
or training cost is inferred; shared billing/trainer/serving owners are unchanged.

## Isolation retained

Only the grading claims changed. Bubblewrap still runs disposable copied source
and worker files with read-only system Python/libraries. No checkout, home,
secret, socket or host process filesystem is mounted. Root/source are read only;
`/tmp` is a fresh 16 MiB tmpfs. The child is UID/GID 65534 and PID 1 in new user,
PID, network and other namespaces, with capabilities removed, further user
namespaces disabled, environment cleared and extra file descriptors closed.

Before candidate import, the bootstrap installs no-new-privileges, hard resource
limits and a native-architecture seccomp allowlist. Network, exec, fork/clone,
IPC, io_uring, ptrace, mount and resource-limit changes remain denied. Limits are
one process/no threads, 128 MiB address space, CPU soft/hard 1/2 seconds, wall
3 seconds, 32 file descriptors, no core dumps, and stdout/stderr each 16 KiB.
The trusted probe still runs without importing candidate code; failure blocks
execution. Direct host invocation is refused. Rootless Docker's unavailable
cgroups are not used. Unsupported system layouts or namespace permissions fail
closed without a host fallback.

Host-observed deadlines, signal exits, output sizes and namespace setup failures
remain separate diagnostics. A Python exception name such as MemoryError or
PermissionError is now explicitly an unauthenticated claim, not proof of that
execution outcome. The trusted pre-import probe, rather than candidate stdout,
checks isolation controls. Source/provenance/test hashes and held-out source
family separation from #781 remain intact; synthetic fixtures remain evaluation
only. Four gold tasks contain Python calls; one is a host command-plan contract.
Five smoke cases are not production gold or real model-quality evidence.
