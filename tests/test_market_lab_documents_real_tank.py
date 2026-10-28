"""Opt-in proof with the real Tank, actual room and local Postgres."""
import os
from urllib.parse import urlsplit

import pytest


def test_uploaded_documents_on_real_tank(tmp_path):
    target = urlsplit(os.environ.get('DATABASE_URL', ''))
    if target.hostname not in {'127.0.0.1', 'localhost'} or not target.path.endswith('_test'):
        pytest.skip('requires an explicitly selected local *_test Postgres')
    from market_docs_proof import services, check
    with services(tmp_path) as env:
        assert check(env, tmp_path)['result'] == 'passed'
