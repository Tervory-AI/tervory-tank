"""Runtime boundary for the immutable, published series parsing implementation."""
from core.pure import series_fetch as _parse


def series_fetch(payload):
    if payload.get('adapter') == 'listing' and not payload.get('fixtures'):
        raise RuntimeError('listing fetch needs fixtures or a live runner')
    return _parse(payload)
