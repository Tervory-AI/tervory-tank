"""Redirect the previous MCP host to the existing Workspace/Tank entry point."""
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, Response

ORIGIN = 'https://app.tervory.com'
ROUTES = {
    'mcp': ('/mcp', {'GET', 'POST', 'DELETE'}),
    'authorize': ('/oauth/authorize', {'GET'}),
    'token': ('/oauth/token', {'POST'}),
    'register': ('/oauth/register', {'POST'}),
    'revoke': ('/oauth/revoke', {'POST'}),
    '.well-known/oauth-protected-resource': ('/.well-known/oauth-protected-resource', {'GET'}),
    '.well-known/oauth-protected-resource/mcp': ('/.well-known/oauth-protected-resource/mcp', {'GET'}),
    '.well-known/oauth-authorization-server': ('/.well-known/oauth-authorization-server', {'GET'}),
}


def create_app() -> FastAPI:
    server = FastAPI(title='Tervory', docs_url=None, redoc_url=None, openapi_url=None)

    @server.get('/health')
    async def health():
        return {'ok': True}

    @server.api_route('/{path:path}', methods=['GET', 'POST', 'DELETE', 'PUT', 'PATCH', 'OPTIONS', 'HEAD'])
    async def canonical(path: str, request: Request):
        route = ROUTES.get(path)
        if route is None:
            return Response(status_code=404)
        target, methods = route
        if request.method not in methods:
            return Response(status_code=405, headers={'Allow': ', '.join(sorted(methods))})
        query = '?' + request.url.query if request.url.query else ''
        return RedirectResponse(ORIGIN + target + query, status_code=307,
                                headers={'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'})

    return server


app = create_app()
