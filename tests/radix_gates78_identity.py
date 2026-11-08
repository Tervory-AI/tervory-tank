"""Legacy unit-test signing using the exact merged verifier, without vendor edits.

These in-memory nonces support unit tests only. Gate acceptance uses the shared
Tank platform, real PostgresNonces, and signed-issuer authentication.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

import httpx

CORE_SHA = 'd02f08d38f10d70d1fd11b07635eb0f67a17e01b'


def install_verifier(monkeypatch, tmp_path):
    name = 'chassis.user_assertion'
    try:
        from chassis import user_assertion
        return user_assertion
    except ImportError:
        pass
    repositories = [os.environ.get('TANK_GATE78_CORE_REPO'), os.environ.get('TANK_SOURCE_REPO'),
                    '/workspace/tervory-tank']
    for source in repositories:
        if not source or not Path(source).exists():
            continue
        result = subprocess.run(['git', '-C', source, 'show', CORE_SHA + ':agents/_chassis/chassis/user_assertion.py'],
                                capture_output=True, text=True)
        if result.returncode == 0:
            path = tmp_path / 'user_assertion.py'
            path.write_text(result.stdout)
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            monkeypatch.setitem(sys.modules, name, module)
            spec.loader.exec_module(module)
            return module
    raise RuntimeError('Merged Tank assertion verifier is required: ' + CORE_SHA)


class UnitNonces:
    def __init__(self, pool):
        self.pool, self.used = pool, set()

    async def claim(self, tenant, nonce, expires):
        if nonce in self.used:
            return False
        self.used.add(nonce)
        return True


class SignedUnitActor(httpx.Auth):
    requires_request_body = True

    def auth_flow(self, request):
        from chassis.user_assertion import SignedUser, sign_assertion, HEADER
        tenant, user = request.headers.get('x-tervory-tenant'), request.headers.get('x-tervory-user')
        key = request.headers.get('x-tank-key')
        if tenant and user and key and HEADER not in request.headers:
            request.headers[HEADER] = sign_assertion('radix', SignedUser(tenant, user, 'member'),
                request.method, request.url.raw_path.decode('ascii'), request.content, key=key)
        yield request
