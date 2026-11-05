"""Opt-in proof with the real Tank, actual room and local Postgres."""
import os
import json
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit

import pytest


def test_uploaded_documents_on_real_tank(tmp_path):
    target = urlsplit(os.environ.get('DATABASE_URL', ''))
    if target.hostname not in {'127.0.0.1', 'localhost'} or not target.path.endswith('_test'):
        pytest.skip('requires an explicitly selected local *_test Postgres')
    # The room intentionally has its own top-level core/feeds packages. Keep
    # this full-service proof independent of pytest workers' imported packages.
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run([sys.executable, str(root / 'tests/market_docs_proof.py'), str(tmp_path)],
                            cwd=root, text=True, capture_output=True, timeout=240)
    assert result.returncode == 0, result.stdout + result.stderr
    proof = json.loads((tmp_path / 'job.json').read_text())
    assert proof['result'] == 'passed' and proof['model_calls'] == 0
