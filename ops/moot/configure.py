"""Render deployment-local private config; never prints configuration or credentials."""
import json
import os
import ssl
from pathlib import Path


def configure():
    names = ('MOOT_REGION', 'MOOT_CONFIG_DIR', 'MOOT_LIVEKIT_API_KEY', 'MOOT_LIVEKIT_API_SECRET')
    if any(not os.environ.get(name) for name in names):
        raise SystemExit('Required Moot configuration names are missing')
    if os.environ['MOOT_REGION'] not in {'us-east', 'za'}:
        raise SystemExit('MOOT_REGION must be us-east or za')
    key, secret = (os.environ[name] for name in names[2:])
    if len(secret) < 32:
        raise SystemExit('MOOT_LIVEKIT_API_SECRET must contain at least 32 characters')
    tls_names = ('MOOT_TLS_CERT_FILE', 'MOOT_TLS_KEY_FILE', 'MOOT_TLS_CA_FILE')
    if any(not os.environ.get(name) or not Path(os.environ[name]).is_file() for name in tls_names):
        raise SystemExit('Moot TLS certificate, private key and CA files are required')
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(os.environ[tls_names[0]], os.environ[tls_names[1]])
        ssl.create_default_context(cafile=os.environ[tls_names[2]])
    except (OSError, ssl.SSLError):
        raise SystemExit('Invalid Moot TLS certificate, private key or CA') from None
    target = Path(os.environ['MOOT_CONFIG_DIR'])
    target.mkdir(mode=0o750, parents=True, exist_ok=True)
    target.chmod(0o750)
    configs = {
        'livekit.json': {'port': 7880, 'bind_addresses': ['0.0.0.0'],
            'rtc': {'tcp_port': 7881, 'udp_port': 7882, 'use_external_ip': False},
            'redis': {'address': 'redis:6379'}, 'keys': {key: secret},
            'room': {'auto_create': False, 'max_participants': 8, 'empty_timeout': 120},
            'logging': {'level': 'warn'}},
        'egress.json': {'api_key': key, 'api_secret': secret, 'ws_url': 'wss://livekit-tls:8443',
            'insecure': False, 'redis': {'address': 'redis:6379'}, 'health_port': 9090,
            'log_level': 'warn', 'session_limits': {'file_output_max_duration': '1h',
            'stream_output_max_duration': '1h'}}}
    configs['nginx.conf'] = '''pid /tmp/nginx.pid;
error_log /dev/stderr warn;
worker_processes 1;
events { worker_connections 128; }
http {
  access_log off;
  client_body_temp_path /tmp/client;
  proxy_temp_path /tmp/proxy;
  fastcgi_temp_path /tmp/fastcgi;
  uwsgi_temp_path /tmp/uwsgi;
  scgi_temp_path /tmp/scgi;
  map $http_upgrade $connection_upgrade { default upgrade; '' close; }
  server {
    listen 8443 ssl;
    server_name livekit-tls;
    ssl_certificate /run/moot/tls.crt;
    ssl_certificate_key /run/moot/tls.key;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_session_tickets off;
    location / {
      proxy_pass http://livekit:7880;
      proxy_http_version 1.1;
      proxy_set_header Upgrade $http_upgrade;
      proxy_set_header Connection $connection_upgrade;
      proxy_read_timeout 60s;
    }
  }
}
'''
    for name, value in configs.items():
        # Unique UID services share a deployment-owned config group. Operator sets
        # the directory group to the containers' supplemental group before launch.
        fd = os.open(target / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        os.fchmod(fd, 0o640)
        with os.fdopen(fd, 'w') as stream:
            if name.endswith('.json'):
                json.dump(value, stream)
            else:
                stream.write(value)


if __name__ == '__main__':
    configure()
