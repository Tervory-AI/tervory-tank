"""Safe configuration diagnostics: names only, before any side effects."""
import os


def missing_settings(names):
    return [name for name in names if not os.environ.get(name, '').strip()]


def not_configured(names):
    return {'ok': False, 'status': 'not_configured', 'missing_settings': names,
            'detail': 'Missing settings: ' + ', '.join(names)}
