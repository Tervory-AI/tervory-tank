# Tiger TG3: memory-measurement prerequisite

Branch: `codex/tiger-brain`, based on main
`19ff60f91572783e978d95e252a0fed8c64b7a80`. Work is confined to
`/workspace/codex-tiger-w3b`. No main merge or PR creation was performed.

## Changes

- `ops/box-memory.sh:7`: read host total, used and available bytes with `free -b`.
- `ops/box-memory.sh:30`: enumerate all containers through one non-streaming,
  formatted `docker stats --all --no-stream` call.
- `ops/box-memory.sh:38`: inspect only running state and numeric memory limit;
  never inspect or print environment values.
- `ops/box-memory.sh:48`: sum all container limits, including stopped containers;
  separately print running usage, running limits, and the count of unlimited
  containers. A zero Docker limit means unlimited, not zero memory use.
- `tests/box_memory/test_box_memory.py:53`: eight offline tests with fake free
  and Docker executables. They check totals, stopped/unlimited containers,
  empty hosts, exact permitted command arguments and failure propagation.

The script uses shell builtins plus only `free -b`, `docker stats --no-stream`
(with `--all` and `--format`) and formatted `docker inspect`. It runs no Docker
exec, ps, restart, stop, update, network or environment-inspection command.

## Commands and results

The assigned clone/fetch/checkout/configuration command succeeded. `ls` found
every existing file named in the TG3 brief. The required brain, room and
isolation documents were read before implementation.

```sh
chmod +x ops/box-memory.sh
bash -n ops/box-memory.sh
python3 -m unittest discover -s tests/box_memory -v
git diff --check
git diff origin/main --check
```

Shell syntax passed. **Eight tests passed in 0.421s** on Python 3.14.4.
Tests execute only fake commands and do not contact a Docker daemon or measure
the host. All eight test names and their outcomes were printed in the chat's
command output. The whitespace checks pass.

Each finished file was committed and pushed separately with `git add`,
`git commit`, and `git push origin codex/tiger-brain`; the first push used `-u`.
No push to main was made.

## Exact missing input

The brief says **Measure first**, assigns the Boston measurement to the
founder's ops thread, and requires its dated numbers in the PR and ROOMS.md.
That dated Boston output has not been supplied. Recent chat metadata and the
review-lead history contained no such output; no message was sent to another chat.

The ops thread can run the committed script on Boston:

```sh
bash /workspace/codex-tiger-w3b/ops/box-memory.sh
```

Record the measurement date with the output. The output must include host
total/used/available bytes, each running container's use, and aggregate memory
limits. It can then be recorded verbatim in the PR and `docs/cursor/ROOMS.md`.
No measurement or capacity claim has been invented.

The Tiger brain/sandbox Compose additions, Tank allowlist, isolation-check
changes and their tests remain pending this prerequisite. No runtime config
was changed or deployed. The eventual Compose change will redeploy the Tiger
room under AGENTS.md rule 11. The intended brain remains optional, off by
default, and has no caller: Tiger's three current extraction skills are code.
No model call or new escalation was added.

Final-head CI, Boston seal output, default-deploy proof and founder-browser
acceptance/screenshots are not claimed for this prerequisite-only increment.
