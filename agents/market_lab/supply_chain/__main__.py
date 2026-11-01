"""Nightly CLI; importing the feed never opens a PR."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from . import inventory, scan
from .fixes import FixError, PublicationError, publish
from .http import Client, SourceError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    client = Client(os.environ.get("GH_TOKEN", ""))
    read_client = Client(os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN", ""))
    report = scan(inventory(args.root), read_client)
    args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Locks: {len(report['coverage'])}; dependencies: {report['dependency_count']}; matches: {len(report['findings'])}")
    if not report["complete"]:
        print("Supply-chain scan incomplete; see the report. No fixes published.")
        return 1
    if args.publish:
        try:
            for url in publish(args.root, report, client, os.environ.get("GITHUB_REPOSITORY", "")):
                print(url)
        except (FixError, SourceError, KeyError, TypeError, ValueError) as error:
            if isinstance(error, PublicationError):
                for url in error.urls:
                    print(url)
            print(str(error) if isinstance(error, (FixError, SourceError)) else "Fix publication failed; no merge attempted.")
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
