"""Both directions of MCP OAuth must remain reachable in the actual Tank app."""
from test_smoke import mod
from http_routes import iter_http_routes


def test_server_and_client_oauth_routes_coexist_once():
    required = {
        ('/oauth/token', 'POST'),
        ('/oauth/revoke', 'POST'),
        ('/mcp', 'POST'),
        ('/v1/command/mcp/oauth/start', 'POST'),
        ('/v1/command/mcp/oauth/callback', 'POST'),
    }
    routes = [
        (route.path, method)
        for route in iter_http_routes(mod.app.routes)
        for method in (getattr(route, 'methods', None) or [])
    ]
    for expected in required:
        assert routes.count(expected) == 1, expected
