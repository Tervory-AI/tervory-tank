#!/usr/bin/env python3
"""Explicit fixture-only comparison; no model loading or network access."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tank'))

from route_comparison import dry_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', required=True)
    parser.add_argument('--tenant', required=True)
    parser.add_argument('--split', choices=('development', 'holdout'), required=True)
    args = parser.parse_args()
    data = json.loads((ROOT / 'tests/fixtures/route_comparison/examples.json').read_text())
    print(json.dumps(dry_run(data, tenant_id=args.tenant, split=args.split), indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
