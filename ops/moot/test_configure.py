"""Focused runtime-config checks; certificate material is generated only in temp files."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('moot_configure', Path(__file__).with_name('configure.py'))
CONFIGURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONFIGURE)


def certificates(directory):
    ca_key, ca, key, request, cert = (directory / name for name in
        ('ca.key', 'ca.crt', 'server.key', 'server.csr', 'server.crt'))
    extensions = directory / 'extensions.cnf'
    extensions.write_text('subjectAltName=DNS:livekit-tls,DNS:localhost\nextendedKeyUsage=serverAuth\nbasicConstraints=critical,CA:FALSE\n')
    commands = [
        ['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
            '-subj', '/CN=Moot disposable test CA', '-keyout', str(ca_key), '-out', str(ca)],
        ['openssl', 'req', '-newkey', 'rsa:2048', '-nodes', '-subj', '/CN=livekit-tls',
            '-keyout', str(key), '-out', str(request)],
        ['openssl', 'x509', '-req', '-in', str(request), '-CA', str(ca), '-CAkey', str(ca_key),
            '-CAcreateserial', '-days', '1', '-extfile', str(extensions), '-out', str(cert)],
    ]
    for command in commands:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for path in (ca, cert, key):
        path.chmod(0o640)
    return cert, key, ca


class ConfigurationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = tempfile.TemporaryDirectory(prefix='moot-config-test-')
        cls.cert, cls.key, cls.ca = certificates(Path(cls.files.name))

    @classmethod
    def tearDownClass(cls):
        cls.files.cleanup()

    def environment(self, target):
        return {'MOOT_REGION': 'us-east', 'MOOT_CONFIG_DIR': str(target),
            'MOOT_LIVEKIT_API_KEY': 'placeholder-api-key',
            'MOOT_LIVEKIT_API_SECRET': 'placeholder-secret-material-for-config-tests',
            'MOOT_TLS_CERT_FILE': str(self.cert), 'MOOT_TLS_KEY_FILE': str(self.key),
            'MOOT_TLS_CA_FILE': str(self.ca)}

    def test_secure_render_and_private_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, self.environment(Path(directory)), clear=True):
                CONFIGURE.configure()
            egress = json.loads((Path(directory) / 'egress.json').read_text())
            self.assertEqual(egress['ws_url'], 'wss://livekit-tls:8443')
            self.assertIs(egress['insecure'], False)
            nginx = (Path(directory) / 'nginx.conf').read_text()
            self.assertIn('ssl_protocols TLSv1.2 TLSv1.3;', nginx)
            self.assertIn('ssl_certificate_key /run/moot/tls.key;', nginx)
            self.assertNotIn(self.key.read_text(), nginx)
            for name in ('livekit.json', 'egress.json', 'nginx.conf'):
                self.assertEqual((Path(directory) / name).stat().st_mode & 0o777, 0o640)

    def test_missing_tls_fails_before_creating_config(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'rendered'
            env = self.environment(target)
            env.pop('MOOT_TLS_CA_FILE')
            with patch.dict(os.environ, env, clear=True), self.assertRaises(SystemExit):
                CONFIGURE.configure()
            self.assertFalse(target.exists())

    def test_invalid_certificate_or_ca_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / 'invalid.pem'
            broken.write_text('invalid certificate fixture')
            for name in ('MOOT_TLS_CERT_FILE', 'MOOT_TLS_KEY_FILE', 'MOOT_TLS_CA_FILE'):
                target = Path(directory) / name
                env = self.environment(target)
                env[name] = str(broken)
                with patch.dict(os.environ, env, clear=True), self.assertRaises(SystemExit):
                    CONFIGURE.configure()
                self.assertFalse(target.exists())


if __name__ == '__main__':
    unittest.main()
