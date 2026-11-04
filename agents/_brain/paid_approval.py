"""Pause the existing synchronous SDK transport at Tank's unspent approval response.

No provider, credential handoff or approval write. This runs only in the isolated
Hermes process and leaves requests to every other destination unchanged.
"""
import time
from urllib.parse import urlsplit

import httpx


def install(base, key, tenant, *, wait=time.sleep):
    original = httpx.Client.send
    origin = urlsplit(base)
    def send(client, request, **kwargs):
        local = (request.url.scheme, request.url.host, request.url.port or (443 if request.url.scheme == 'https' else 80)) == (origin.scheme, origin.hostname, origin.port or (443 if origin.scheme == 'https' else 80))
        eligible = local and request.method == 'POST' and request.url.path.endswith('/chat/completions')
        if eligible:
            request.read()
        while True:
            response = original(client, request, **kwargs)
            if not eligible or response.status_code != 409:
                return response
            response.read()
            detail = response.json().get('detail')
            if not isinstance(detail, dict) or detail.get('code') != 'paid_step_approval_required':
                return response
            if detail.get('tenant_id') != tenant:
                response.close()
                raise RuntimeError('Paid approval belongs to another tenant')
            response.close()
            while True:
                check = client.get(base.rstrip('/') + '/v1/paid-steps/approvals/' + detail['approval_id'],
                                   params={'tenant_id':tenant}, headers={'X-Tank-Key':key}, timeout=30)
                check.raise_for_status()
                state = check.json()['state']
                check.close()
                if state == 'approved':
                    break
                if state == 'denied':
                    raise RuntimeError('Paid step denied by tenant administrator')
                wait(5)
    httpx.Client.send = send
    return original
