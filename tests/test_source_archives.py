"""Bundled legal evidence and word corpus stay byte-identical to their source."""
import gzip
import hashlib
import json
from pathlib import Path


def test_source_archive_bytes_match_original_sha256():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / 'tests/fixtures/source-archives.json').read_text())
    assert len(manifest) == 6
    for name, expected in manifest.items():
        original = gzip.decompress((root / (name + '.gz')).read_bytes())
        assert hashlib.sha256(original).hexdigest() == expected
