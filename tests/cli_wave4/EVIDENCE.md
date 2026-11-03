# CLI Wave 4 — offline evidence

Branch `codex/cli-w4`, based on `origin/main`; no main merge, release tag,
production sign-in, model call or deployment performed. CLI version 0.5.0.
The existing review is PR #644, opened before the updated standing rule; no
further PRs are opened, labeled or merged by this thread.

## Changes

- Plain `login --region za` requests #589's Zitadel device approval; absent issuer/legacy Boston responses fail closed. The browser launcher accepts only the pinned approval hosts. The saved Tank credential selects ZA for all code calls.
- Windows CI runs the complete suite, with explicit POSIX-only installer/sandbox skips. Local commands are refused before prompting because no Windows filesystem/network sandbox backend equivalent to Bubblewrap is implemented. File tools, edits, undo and Tervory cards run natively.
- Release builds add x64/arm64 Windows keyring archives and `tervory.cmd`. Native Windows builds use npm's JS entry without a shell, MSYS GNU archive paths and task-owned TMPDIR/TEMP/TMP. Both archives are built twice and the x64 installed launcher runs in CI.
- `cli-v*` releases build all eight archives twice, then sign every archive, manifest and SHA256SUMS with Ed25519. Missing/mismatched signing settings fail before upload. Artifact retention/publication policy remains unchanged. This is detached archive signing, not Authenticode or notarization. The independently deployed Workspace installer/update path remains checksum-only; README distinguishes it from signed archive installation.
- README contains captured US/ZA, code, plugin and /undo output. Install output identifies actual variable fields rather than inventing a fixed hash, device name or home folder.

## Tests actually run on the worker

All local tests used `TMPDIR=/workspace/codex-cli-w3/.tmp`, which is excluded only
in the shared Git info/exclude. No other thread's temporary files were deleted.

1. `TMPDIR=/workspace/codex-cli-w3/.tmp npm test --prefix cli`: **113 passed, 3 Darwin-only skips**, 116 total (25.31 seconds), on `0e9acebd`. Subsequent changes fix Windows GNU paths and quote fixture commands; final-head CI is the test of record.
2. Backend fake OIDC/JWKS, device login, identity stack and backup: **34 passed**, 3 warnings (19.44 seconds). Disposable `cli-w4-oidc-proof` Postgres on loopback only; removed afterward. Initial collection lacked PyJWT; installed the repository-pinned `PyJWT[crypto]==2.15.1` into task-owned `.tmp/w4-python`, without modifying a shared venv, then reran successfully.
3. `tests/test_ci_minutes_workflows.py`: **67 passed** (6.33 seconds).
4. All eight platform archives built twice byte-identically on Linux; 10 files signed with an ephemeral, in-memory offline test key; all eight archives plus the signed manifest/checksum list verified. No release key value was read or generated. Hash evidence below pertains to that offline build before the final README correction; final archives get their own manifest/checksums.
5. Tampering, wrong public key, signature mismatch, checksum/size disagreement and missing platform tests pass. The integrated fake OIDC HTTP fixture approves separately from polling, then exercises ZA code reads/edits, local undo and plugin Confirm without a US call. The backend suite separately verifies real JWT signatures and tenant/role mapping.

Reproduction of the focused backend run (existing venv, task-owned dependencies):

```sh
TMPDIR=/workspace/codex-cli-w3/.tmp PYTHONPATH=/workspace/codex-cli-w3/.tmp/w4-python:/workspace/codex-cli-w3/.tmp/deps:tank:tests POOL_SCHEMA_DATABASE_URL=postgresql://postgres@127.0.0.1:55479/pooltest /home/ammosync/.codex/tervory-audit-20261101/venv312/bin/python -m pytest -q tests/test_identity_za.py tests/test_identity_stack.py tests/test_identity_backup.py tests/test_device_login.py --disable-socket --allow-unix-socket --allow-hosts=127.0.0.1,localhost,::1
```

Disposable SQL must be recreated to rerun this command. No production SQL is involved.

6. The assembled CLI → ZA Tank acceptance fixture now uses the same fake Zitadel discovery/JWKS provider and **real JWT verification**. Both US/ZA login-refresh-revoke cases passed (2 tests, 14.32 seconds); the complete cross-lane file passed **7 tests**, no skips (28.00 seconds). The verified `zitadel:20001` subject, mapped tenant, real SQL credential owner and receipts are asserted; ZA makes zero Workspace approval calls. This replaced the old Boston-only approval expectation exposed by broader CI.

## CI regressions fixed

The first Windows runs found an illegal `*` filename, CRLF-sensitive fixture
assertions, a POSIX approval test that cannot prompt on Windows, and MSYS GNU tar
receiving Win32 backslash paths. Fixtures now use the still-globbing but legal
`.e[n]v`, normalize text for static shell assertions, explicitly skip unavailable
POSIX command behavior, and translate archive paths for GNU tools. Command refusal
itself is tested on Windows and via simulated Windows on POSIX. Linux/macOS passed
on intermediate heads; final-head results belong in the review report.

## Settings and founder decisions

Names only: GitHub Actions secret `CLI_RELEASE_SIGNING_KEY` and repository variable
`CLI_RELEASE_SIGNING_PUBLIC_KEY`. The founder supplies the Ed25519 private/public
PEM pair and distributes the public key independently before a tag release. No
secrets were inspected. ZA deployment/certificates/tenant mapping remain the #589
operator prerequisites; offline proof does not claim founder-browser acceptance.
No new Figma frame is needed for terminal changes.

New production terminal string for founder review:
`Update refused: on Windows, verify and extract the signed release archive again.`

New build/verification tool strings:
- `Release signatures verified.`
- `Release signing failed. Check CLI_RELEASE_SIGNING_KEY and CLI_RELEASE_SIGNING_PUBLIC_KEY.`
- `Release signatures and checksums verified.`
- `Release verification failed. Nothing was installed.`

## Changed file entry lines

| File and first changed line |
| --- |
| `.env.example:544` |
| `.github/workflows/cli-release.yml:2` |
| `.github/workflows/cli.yml:175` |
| `cli/CHANGELOG.md:3` |
| `cli/README.md:3` |
| `cli/bin/tervory.mjs:12` |
| `cli/package-lock.json:3` |
| `cli/package.json:4` |
| `cli/scripts/build-release.mjs:18` |
| `cli/scripts/sign-release.mjs:1` |
| `cli/scripts/verify-release.mjs:1` |
| `cli/src/client.mjs:185` |
| `cli/src/code-tools.mjs:44` |
| `cli/src/update.mjs:78` |
| `cli/test/client.test.mjs:67` |
| `cli/test/code-mode.test.mjs:5` |
| `cli/test/identity-za.test.mjs:36` |
| `cli/test/release.test.mjs:178` |
| `cli/test/sign-release.test.mjs:1` |
| `cli/test/wave4.test.mjs:1` |
| `tests/command_acceptance_20261031/device_edge.cjs:70` |
| `tests/command_acceptance_20261031/test_cross_lane.py:215` |

Exact offline transcripts: [ZA and code](ZA-CODE-OUTPUT.txt), [US and plugins](US-PLUGIN-OUTPUT.txt).

```text
linux-x64-gnu: byte-identical, SHA256=cb498f3909394d1881a3f0ebc7f93b8461bb6a1ecd142d2c79b34c1bc22b12f5
linux-x64-musl: byte-identical, SHA256=83255bee45b1ceec5666fc92f8345fd0d2a9da01b3caac65e0625673404ff681
linux-arm64-gnu: byte-identical, SHA256=0ff998a707defede5bb049fa9b7833d72f3698fa7018e7ac52c9e663822769aa
linux-arm64-musl: byte-identical, SHA256=f03158fb1ded6c9beca623ff9c2692722cc0557d4d4b7a70edcd4848d7c21bb6
darwin-x64: byte-identical, SHA256=d466a7f3e48b7f7608539de136df8d7a80b2451fd4752821137fdecea101741f
darwin-arm64: byte-identical, SHA256=afe20d4f307617623545dd539468a9e88bbc626c0bd1115aa4b6ea7f3883b253
win32-x64-msvc: byte-identical, SHA256=d310937344fda71a861b25a357d3b5d5015c0686f63b3a7f60cfe8eb5bbcbb80
win32-arm64-msvc: byte-identical, SHA256=08c82b14ab2369e075d334a5d5c36fddb10ec44a10d74657dbbb084f02a99d89
10 files signed using an ephemeral offline test key (never release settings).
8 platform archives verified with signed manifest and checksums.
```
