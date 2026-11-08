"""Production transport validation is independent of the recording-worker disk gate."""
import ssl

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ops.moot.test_configure import certificates
from tank.moot import main
from tank.moot.livekit import Rooms


@pytest.fixture
def runtime_env(monkeypatch,tmp_path):
    cert,key,ca=certificates(tmp_path)
    settings={'MOOT_REGION':'us-east','MOOT_JOURNAL_PATH':str(tmp_path/'journal.sqlite'),
      'MOOT_INTERNAL_API_KEY':'placeholder-internal-key','MOOT_LIVEKIT_URL':'https://livekit-tls:8443',
      'MOOT_LIVEKIT_PUBLIC_URL':'wss://moot.example.test','MOOT_LIVEKIT_API_KEY':'placeholder-api-key',
      'MOOT_LIVEKIT_API_SECRET':'placeholder-secret-material-for-local-tests',
      'MOOT_LEGACY_URL':'http://legacy-room:8000','MOOT_LEGACY_API_KEY':'placeholder-legacy-key',
      'MOOT_TLS_CA_FILE':str(ca)}
    for name,value in settings.items():monkeypatch.setenv(name,value)
    return settings


@pytest.mark.parametrize('name,value',[
    ('MOOT_LIVEKIT_URL','http://livekit:7880'),
    ('MOOT_LIVEKIT_PUBLIC_URL','https://moot.example.test'),
])
def test_deployment_rejects_non_tls_or_wrong_scheme(runtime_env,monkeypatch,name,value):
    monkeypatch.setenv(name,value)
    with pytest.raises(RuntimeError,match='requires secure TLS URLs'):
        main.build()


def test_configured_ca_reaches_all_internal_clients(runtime_env,monkeypatch):
    captured={}
    def app_factory(**kwargs):captured.update(kwargs);return FastAPI()
    monkeypatch.setattr(main,'create_app',app_factory)
    app=main.build()
    rooms=captured['rooms']
    assert rooms.tls_context.check_hostname is True
    assert rooms.tls_context.verify_mode==ssl.CERT_REQUIRED
    assert rooms.tls_context.cert_store_stats()['x509_ca']>0
    with TestClient(app):pass


def test_invalid_ca_fails_closed_before_clients_start(runtime_env,monkeypatch,tmp_path):
    invalid=tmp_path/'invalid-ca';invalid.write_text('invalid CA fixture')
    monkeypatch.setenv('MOOT_TLS_CA_FILE',str(invalid))
    with pytest.raises(RuntimeError,match='TLS CA is unavailable or invalid'):
        main.build()


def test_default_client_never_disables_peer_verification():
    rooms=Rooms('https://livekit-tls:8443','wss://moot.example.test','placeholder-api-key','placeholder-secret')
    assert rooms.tls_context.check_hostname is True
    assert rooms.tls_context.verify_mode==ssl.CERT_REQUIRED
