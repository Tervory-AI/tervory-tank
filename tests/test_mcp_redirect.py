"""The previous MCP host delegates to Workspace/Tank without issuing credentials."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mcp'))
from connector.app import create_app, ROUTES  # noqa: E402


@pytest.mark.parametrize('path', list(ROUTES))
def test_protocol_routes_preserve_requests_and_use_only_canonical_origin(path):
    target, methods = ROUTES[path]
    with TestClient(create_app()) as client:
        response = client.request(sorted(methods)[0], '/' + path + '?state=offline&redirect_uri=https%3A%2F%2Fevil.example',
                                  headers={'host': 'evil.example', 'authorization': 'Bearer offline-marker'},
                                  follow_redirects=False)
    assert response.status_code == 307
    assert response.headers['location'] == 'https://app.tervory.com' + target + '?state=offline&redirect_uri=https%3A%2F%2Fevil.example'
    assert response.headers['cache-control'] == 'no-store'
    assert response.headers['referrer-policy'] == 'no-referrer'
    assert 'set-cookie' not in response.headers


def test_previous_login_callbacks_and_unknown_paths_are_removed():
    with TestClient(create_app()) as client:
        for path in ['/oauth/obsolete/callback', '/oauth/choose', '/authorize/continue', '/unknown']:
            assert client.get(path, follow_redirects=False).status_code == 404
        assert client.get('/token', follow_redirects=False).status_code == 405
        assert client.get('/health').json() == {'ok': True}
