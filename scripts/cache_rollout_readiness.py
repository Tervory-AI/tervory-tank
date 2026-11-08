#!/usr/bin/env python3
"""Bounded offline acceptance against disposable SQL and fixture gateways."""
from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SUITES = (
    'tests/test_engine_exact_cache.py',
    'tests/test_engine_embedding_cache.py',
    'tests/test_engine_prompt_cache.py',
    'tests/test_engine_scheduling.py',
    'tests/test_offpeak_deadline.py',
    'tests/test_engine_layers_off.py',
    'tests/test_cache_rollout_readiness.py',
)


def main():
    # Never accept a caller-supplied DSN or production settings. pgserver starts
    # a new local database; fixtures create and destroy their own child DBs.
    import pgserver
    with tempfile.TemporaryDirectory(prefix='cache-readiness-') as folder:
        server = pgserver.get_server(Path(folder) / 'postgres', cleanup_mode='delete')
        try:
            report = Path(folder) / 'results.xml'
            env = {**os.environ, 'POOL_SCHEMA_DATABASE_URL': server.get_uri(),
                   'ENGINE_C1_ENABLED': '0', 'ENGINE_C4_ENABLED': '0', 'ENGINE_I8_ENABLED': '0',
                   'PYTHONDONTWRITEBYTECODE': '1', 'PYTEST_ADDOPTS': ''}
            result = subprocess.run([sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                '--disable-socket', '--allow-unix-socket', '--allow-hosts=127.0.0.1,localhost,::1',
                '--timeout=60', f'--junitxml={report}', *SUITES],
                cwd=ROOT, env=env, timeout=600, check=False)
            suites = ET.parse(report).getroot().iter('testsuite') if report.exists() else []
            counts = {key: 0 for key in ('tests', 'failures', 'errors', 'skipped')}
            for suite in suites:
                for key in counts:
                    counts[key] += int(suite.get(key, 0))
            passed = result.returncode == 0 and counts['tests'] > 0 and not any(
                counts[key] for key in ('failures', 'errors', 'skipped'))
            print(json.dumps({'ready': passed, 'scope': 'offline-fixtures-only', **counts}))
            return 0 if passed else 1
        finally:
            server.cleanup()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except subprocess.TimeoutExpired:
        print('{"ready": false, "error": "acceptance_timeout"}')
        sys.exit(1)
