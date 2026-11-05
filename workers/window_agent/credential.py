"""Git credential helper: named vault value staged read-only, never URL/argv."""
import os
import sys
from pathlib import Path


def main():
    if len(sys.argv) > 1 and sys.argv[1] != 'get':
        return
    fields = dict(line.split('=', 1) for line in sys.stdin.read(4096).splitlines() if '=' in line)
    if fields.get('protocol') != 'https' or fields.get('host') != 'github.com':
        raise SystemExit(1)
    token = Path(os.environ['GITHUB_TOKEN_FILE']).read_text().strip()
    if not token or '\n' in token or '\r' in token:
        raise SystemExit(1)
    sys.stdout.write(f'username=x-access-token\npassword={token}\n')


if __name__ == '__main__':
    main()
