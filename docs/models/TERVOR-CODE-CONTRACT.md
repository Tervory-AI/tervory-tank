# Independent verification of bounded expressions

```sh
python3 -m tank.tervor_code_contract --dry-run
```

This follow-up to merged #787 introduces `bounded_int_expression_v1`. It grades
only the declared finite-input semantics of a small expression language. It does
not attest subprocess execution, grade arbitrary Python, or measure a trained
Tervor Code checkpoint or Opli Code UI. Training remains blocked; dry-run exits
2 after measurement or 3 if required isolation is unavailable. To check saved
expressions, add `--predictions expressions.json`, containing exactly
`{"sample-add-one":"number + 1","gold-bug":"0 <= n <= 10"}` with your expressions.
Predictions cannot supply tests, expected values, worker files or transport flags.

## Contract and trusted boundary

Expressions are ASCII text of at most 512 characters, parsed as data by `ast.parse`
and interpreted through an explicit closed dispatcher. There is no Python
`eval`, `exec`, compilation, candidate import or candidate-defined object call.
At most 96 syntax nodes and depth 16 are allowed. Inputs are one or two named
primitive integers/Booleans. Integer magnitude is at most 2^31-1 before and after
every operation. Multiplication therefore has at most a 62-bit intermediate.
There are no loops, recursion, exponentiation or shifts. The allowed operations
are integer +, -, *, // and %, unary +/-, Boolean not/and/or, comparisons and a
conditional expression. Arithmetic requires integers; Boolean operations require
Booleans; comparisons require matching scalar types, with ordering for integers.
Division by zero and out-of-range values are refused.

The complete syntax tree is validated, including unexecuted branches. Imports,
calls, attributes, subscripts, strings/bytes, containers, comprehensions, lambdas,
assignment, introspection and all other Python capabilities are refused. Exact
type checks exclude objects with overloaded methods from the trusted interpreter.
Candidate text cannot acquire a file descriptor, modify a serializer or inspect
a worker frame because this language has no such operations.

The controller independently computes canonical semantics **before transport**,
using only bounded primitive operations in reviewed code. This is data
interpretation on the controller, not execution of candidate Python. It then
uses #787's unchanged mandatory Bubblewrap/seccomp/resource sandbox to run a
fixed copied interpreter on the expression as an argument. No candidate text is
written to an executable/importable source file. Existing Python observations
still return `integrity_unverified`; that interface is not reopened.

The controller checks both (1) canonical semantics against sealed expected values
and (2) the child's untrusted claim against canonical semantics. A transport
claim of the expected value cannot make a wrong program pass. A mismatch fails
closed; missing required isolation also fails closed. There is no separate-FD,
nonce, signature, or same-process marker offered as an integrity guarantee.
The grading authority is the independent bounded semantic calculation, not the
child's exit code, stdout shape or self-reported success.

A transport returning a correct canonical result for a genuinely correct
expression cannot prove how that child produced it. This contract intentionally
does **not** assert that invocation occurred or authenticate transport origin.
An all-powerful malicious transport cannot alter the controller's semantics or
expected values under the threat model; it can cause rejection/denial of service,
but cannot turn incorrect expression semantics into a pass. A coincidentally
correct forged result conveys no more authority than the independent calculation.

Trusted computing base: the reviewed interpreter/controller, sealed test manifest,
controller Python parser/runtime, and isolation implementation/kernel. A verifier
logic bug, compromised controller, or malicious edits to trusted repository files
is outside this boundary. This is not a diverse-implementation proof or a proof
for all possible inputs. A program can overfit the visible finite tests. The
language bounds make all accepted interpretation finite and small; native code
and arbitrary Python remain outside the contract and ungraded.

## Evidence and scope

The two supported source families reuse #781/#787 provenance, source/test hashes
and split checks: the MIT PyPA add-one training-split fixture is a harness control;
the synthetic interval gold fixture is evaluation-only. Other task IDs are
explicitly unsupported; multi-file patches and test-writing are not silently
relabelled as expression verification. There are not 200 independently reviewed
gold cases, and the public control never counts as gold.

The [sanitized measured report](evidence/tervor-code-contract-2026-11-08.json)
contains contract version, source/test/family and interpreter/controller hashes,
probe evidence, per-call timing, and restricted-contract outcomes. Correct controls
pass 2/2; wrong controls pass 0/2. Exact-envelope, early exit, monkeypatch,
introspection and stdout-write programs are refused before transport. Hostile
transport controls returning expected values for wrong programs fail independent
verification; incorrect transport results for correct programs fail closed too.
Focused tests also verify that #787's arbitrary-Python grading remains blocked.
Unsupported CI runners test the fail-closed path without executing candidate code
or adding skips; the recorded Cloud run exercises actual existing isolation.

`verified_contract_pass` is scoped to this versioned language and declared tests.
`arbitrary_python_grading`, `execution_attested`, `model_quality_measured` and
`eligible` remain false. Base checkpoint/revision/licence, coding-capable trainer,
independent Python grading, reviewed gold, calibrated Tank/DeepEval and shadow
promotion gates remain prerequisites. No shared billing/training/serving gate,
runtime Compose, service, production setting, paid/model/GPU job, HF upload or
deployment is changed. The dry-run uses zero provider dollars.
