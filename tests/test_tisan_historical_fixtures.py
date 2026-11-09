"""Historical negatives retain exact upstream bytes, not simulated clients."""
import hashlib
import json
from pathlib import Path


def test_historical_clients_and_patch_are_pinned_and_byte_identical():
    root = Path(__file__).parent / 'fixtures/tisan_unintegrated_core'
    sources = json.loads((root / 'SOURCE.json').read_text())
    assert len(sources) == 8
    assert {item['commit'] for item in sources.values()} == {
        'ea9f0d0418951ae7215a165e9df1e590902002fd',
        '6c3207008a5085be9648f3485e8bd6492dc9ef2f',
    }
    for name, source in sources.items():
        assert hashlib.sha256((root / name).read_bytes()).hexdigest() == source['sha256'], name
