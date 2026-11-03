"""Attest the CRM organization already resolved by BottleCRM's PAT middleware.

No token parsing, extra scopes, membership lookup or organization override.
An expected organization is a restriction, never authentication or authority.
"""
from uuid import UUID

HEADER = 'X-Tervory-CRM-Organization'


class OrganizationBinding:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        expected = request.headers.get(HEADER)
        org = getattr(request, 'org', None)
        pat = getattr(request, '_pat', None)
        actual = str(org.id) if org is not None and pat is not None else None
        if expected:
            try:
                valid = actual is not None and UUID(expected) == UUID(actual)
            except (ValueError, TypeError, AttributeError):
                valid = False
            if not valid:
                # Runs before the view: a mismatched token cannot write in another org.
                from django.http import JsonResponse
                return JsonResponse({'error': True, 'message': 'Organization binding refused'}, status=403)
        response = self.get_response(request)
        # Remove any preexisting header; only the server's resolved PAT org attests it.
        if HEADER in response:
            del response[HEADER]
        if actual is not None and 200 <= response.status_code < 300:
            response[HEADER] = actual
        return response
