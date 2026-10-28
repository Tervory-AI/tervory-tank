"""Run the real CI typecheck command clean, with a temporary error, then clean.

This is a local compiler proof, not a GitHub Actions run. The probe is removed
even if the expected rejection fails; no page or existing source is modified.
"""
from pathlib import Path
import subprocess

import yaml


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    job = yaml.safe_load((root / '.github/workflows/ci.yml').read_text())['jobs']['workspace']
    steps = job['steps']
    names = [step.get('name') for step in steps]
    assert names.count('typecheck') == 1
    index = names.index('typecheck')
    assert names.index('Install') < index < names.index('Build')
    step = steps[index]
    assert step['working-directory'] == 'workspace'
    assert step['run'].strip() == 'npx tsc --noEmit'
    assert not job.get('continue-on-error')
    assert not step.get('continue-on-error') and 'if' not in step
    assert 'if' not in steps[names.index('Build')]
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
    print(f'Revision: {revision}', flush=True)
    print('Workflow order: Install -> typecheck -> Build; failure is not suppressed.', flush=True)

    def run(label: str) -> subprocess.CompletedProcess:
        print(f'\n{label}\n$ (cd workspace && {step["run"]})', flush=True)
        result = subprocess.run(
            ['bash', '--noprofile', '--norc', '-e', '-o', 'pipefail', '-c', step['run']],
            cwd=root / step['working-directory'], text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=120, check=False,
        )
        print(result.stdout or '(no compiler output)', end='' if result.stdout else '\n', flush=True)
        print(f'Exit code: {result.returncode}', flush=True)
        return result

    assert run('Clean branch').returncode == 0
    probe = root / 'workspace/typecheck-proof.ts'
    # Exclusive creation protects any pre-existing local file.
    with probe.open('x') as file:
        file.write('export const typecheckProbe: number = "intentional type error";\n')
    try:
        failed = run('Planted error: typecheck-proof.ts assigns a string to a number')
        assert failed.returncode == 2
        assert 'typecheck-proof.ts(1,14): error TS2322' in failed.stdout
    finally:
        probe.unlink()
    assert run('Probe removed').returncode == 0
    print('\nPASS: clean=0, planted=2 (TS2322), removed=0; probe absent.', flush=True)


if __name__ == '__main__':
    main()
