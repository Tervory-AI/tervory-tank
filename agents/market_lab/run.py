"""One command for scheduled handlers and an isolated offline rehearsal."""
import argparse
import asyncio
import json
from uuid import UUID


def main(argv=None):
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true')
    mode.add_argument('--job')
    parser.add_argument('--tenant', type=UUID)
    parser.add_argument('--engine', default='ffl')
    args = parser.parse_args(argv)
    if args.dry_run:
        from core.dry_run import run
        result = asyncio.run(run())
    else:
        if args.tenant is None:
            parser.error('--tenant is required for a job')
        from core.readiness import missing, REQUIRED
        needed = missing(REQUIRED)
        if needed:
            print(json.dumps({'status': 'not_configured', 'missing_settings': needed}))
            return 0
        import app
        if args.job not in app.app.state.handlers:
            parser.error('unknown job')
        from chassis.memory import MemoryClient
        from types import SimpleNamespace
        try:
            ctx = SimpleNamespace(tenant_id=str(args.tenant), agent='market_lab',
                                  input={'engine': args.engine}, memory=MemoryClient())
            result = asyncio.run(app.app.state.handlers[args.job](ctx))
        except Exception as exc:
            print(json.dumps({'status': 'failed', 'kind': type(exc).__name__,
                              'error': 'Market Lab could not read its stored sources. Try again shortly.'}))
            return 1
    print(json.dumps(result, default=str, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
