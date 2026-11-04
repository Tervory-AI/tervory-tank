# Seal check: exact Trigger and Radix placements

Branch: `codex/seal-check-trigger-radix`; base `2b4d6a80` from origin/main.
Claude opens the PR; founder merges. No networks, compose files, runtime
settings or running services were changed.

The check now accepts exactly the attachments the existing compose files declare:

| Service | Required networks | Required internal networks |
| --- | --- | --- |
| agent-trigger | tervory-gw-trigger, `<project>_checkers` | `<project>_checkers` |
| trigger-languagetool | `<project>_checkers` | `<project>_checkers` |
| passive-egress | tervory-gw-radix, `<project>_proxy-link`, `<project>_egress` | tervory-gw-radix, `<project>_proxy-link` |

Any additional attachment, including an additional internal network, remains a
LEAK. Missing declared attachments fail, and the private networks must remain
internal. LanguageTool cannot join even Trigger's permitted gateway corridor.
Project names come from Docker labels, not container names.
`EXPECTED_SEALED` remains exactly Base, Radix, Tiger and Rig.

## Changed files and lines

- `ops/seal-check.sh:121`: exact compose-network checking now includes the three
  named services, even when their internal attachment is missing.
- `ops/seal-check.sh:126`: Trigger room and LanguageTool exact lists.
- `ops/seal-check.sh:128`: Radix passive-egress exact list.
- `ops/seal-check.sh:146`: only Trigger's declared corridor and passive-egress's
  declared outbound network are exempt from the private-network Internal check.
- `tests/test_room_seal.py:433`: sample Docker output with the four existing
  sealed rooms plus the declared Trigger/LanguageTool/passive-egress placements.
- `tests/test_room_seal.py:456`: samples checked against both compose files and
  the four-room EXPECTED_SEALED list.
- `tests/test_room_seal.py:469`: exact placements pass.
- `tests/test_room_seal.py:481`: extra outward/internal network on each fails.
- `tests/test_room_seal.py:500`: missing attachments fail.
- `tests/test_room_seal.py:512`: changing private networks to non-internal fails.
- `tests/test_room_seal.py:522`: LanguageTool on Trigger's corridor fails.

## Commands and results

Working directory: `/workspace/codex-autumbra-seal`.

```bash
bash -n ops/seal-check.sh
PYTHONPATH=tank TMPDIR=/workspace/codex-autumbra-seal/.proof/tmp /tmp/base-reliability-venv/bin/python -m pytest -q tests/test_room_seal.py
PYTHONPATH=/workspace/codex-autumbra-edge/.proof/python /tmp/base-reliability-venv/bin/python -m ruff check tests/test_room_seal.py --select E9,F
git diff --check
```

All exit 0. Pytest: **89 passed in 57.91 s**. Ruff: `All checks passed!`.
Bash syntax and whitespace checks pass. The complete existing room-seal suite
includes the prior Rig exact-network regressions and read-only Docker checks.

An earlier broader attempt also included `tests/test_rig_forge_seal.py`; it
stopped at collection because the existing Python environment lacks
`huggingface_hub`. No Forge implementation is changed, and no Forge test pass
is claimed. The complete relevant room-seal suite above passes.

The sample-output run used the same existing fake-Docker helper as the tests:

```bash
PYTHONPATH=tank /tmp/base-reliability-venv/bin/python - <<'PY'
import json
import runpy
import tempfile
from pathlib import Path

helpers = runpy.run_path('tests/test_room_seal.py')
with Path('.proof/samples.txt').open('w') as proof:
    for service in (None, 'agent-trigger', 'trigger-languagetool', 'passive-egress'):
        data = helpers['trigger_radix_placements']()
        if service:
            data['networks']['unexpected'] = False
            data['containers'][service]['networks'].append('unexpected')
        with tempfile.TemporaryDirectory(dir='.proof/tmp') as temporary:
            directory = Path(temporary).resolve()
            fixture = directory / 'sample.json'
            fixture.write_text(json.dumps(data))
            result = helpers['run_seal_check'](directory, str(fixture))
            proof.write(f"Sample: {service or 'exact declared placements'}, exit {result.returncode}\n")
            proof.write(result.stdout + result.stderr + '\n')
            assert result.returncode == (1 if service else 0)
print(Path('.proof/samples.txt').read_text())
PY
```

Exit 0. Exact placement returns 0; the three extra-network samples each return 1.

## Real host check

```bash
bash ops/seal-check.sh
```

**Exit 1. Radix, Base, Tiger and Rig pass.** Trigger and LanguageTool still have
an extra Coolify app network `yzq4jrwa6fipvwb7lzcx4nmo`, which is absent from their
compose file. The checker correctly continues to call that a LEAK; it has not
been added to an allowlist. Trigger's corridor and declared checker network are
accepted. No corrective deployment or live network mutation was made.

This is a command-line checker change, with no browser UI or screenshot claim.
The following sections contain the actual test, sample and live-host output.

## Room-seal tests

```text
........................................................................ [ 80%]
.................                                                        [100%]
89 passed in 57.91s
```

## Sample docker output

```text
Sample: exact declared placements, exit 0
tervory-tankmain (tankuuid): not a room, skipped
agent-base (baseuuid): sealed
agent-radix (radixuuid): sealed
agent-tiger (tigeruuid): sealed
agent-rig (riguuid): sealed
agent-trigger (triggeruuid): sealed
autumbra: no Watch/Enforce rooms running (ok until dogfood; pin EXPECTED_SEALED after first clean run)

Sample: agent-trigger, exit 1
tervory-tankmain (tankuuid): not a room, skipped
agent-base (baseuuid): sealed
agent-radix (radixuuid): sealed
agent-tiger (tigeruuid): sealed
agent-rig (riguuid): sealed
agent-trigger (triggeruuid): LEAK: triggerproject-agent-trigger-1 on unexpected
autumbra: no Watch/Enforce rooms running (ok until dogfood; pin EXPECTED_SEALED after first clean run)

Sample: trigger-languagetool, exit 1
tervory-tankmain (tankuuid): not a room, skipped
agent-base (baseuuid): sealed
agent-radix (radixuuid): sealed
agent-tiger (tigeruuid): sealed
agent-rig (riguuid): sealed
agent-trigger (triggeruuid): LEAK: triggerproject-trigger-languagetool-1 on unexpected
autumbra: no Watch/Enforce rooms running (ok until dogfood; pin EXPECTED_SEALED after first clean run)

Sample: passive-egress, exit 1
tervory-tankmain (tankuuid): not a room, skipped
agent-base (baseuuid): sealed
agent-radix (radixuuid): LEAK: radixuuid-passive-egress-1 on unexpected
agent-tiger (tigeruuid): sealed
agent-rig (riguuid): sealed
agent-trigger (triggeruuid): sealed
autumbra: no Watch/Enforce rooms running (ok until dogfood; pin EXPECTED_SEALED after first clean run)

```

## Real host output (exit 1)

```text
tervory-tankmain-xnmc0jkz8j9i5jh1jwanbsfv (xnmc0jkz8j9i5jh1jwanbsfv): not a room, skipped
trigger-crm (aty7tukal0rlksfpet1mzplb): not a room, skipped
agent-trigger (yzq4jrwa6fipvwb7lzcx4nmo): LEAK: agent-trigger-yzq4jrwa6fipvwb7lzcx4nmo-20261101T220549 on yzq4jrwa6fipvwb7lzcx4nmo; LEAK: trigger-languagetool-yzq4jrwa6fipvwb7lzcx4nmo-20261101T220549 on yzq4jrwa6fipvwb7lzcx4nmo
agent-tisan (lblbn0wjaz30hhdur9l3pylg): no sealed containers
agent-tiger (fro6z8xlh579owlp1wwrjr8n): sealed
agent-rig (59f8cnpelzwsyte1atyjc4fv): sealed
agent-radix (liv4x7vshraiwnnowjv0kgfd): sealed
agent-market-lab (xt0vc7rnr45flw2wg3iyjpmn): no sealed containers
agent-base (r8aprclj8nooe9keywrp9dmb): sealed
agent-zenas (r7qzm460bc4scnskurlowbvn): no sealed containers
agent-ghost (nypsvvcxjpdebaa204smtqtd): no sealed containers
agent-template (jodjyt6vsyoyhfr6axtuc8ij): no sealed containers
autumbra: no Watch/Enforce rooms running (ok until dogfood; pin EXPECTED_SEALED after first clean run)
```

