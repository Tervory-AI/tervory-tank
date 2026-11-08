"""Render deployment-local private config; never prints configuration or credentials."""
import json
import os
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
    target = Path(os.environ['MOOT_CONFIG_DIR'])
    target.mkdir(mode=0o750, parents=True, exist_ok=True)
    target.chmod(0o750)
    configs = {
        'livekit.json': {'port': 7880, 'bind_addresses': ['0.0.0.0'],
            'rtc': {'tcp_port': 7881, 'udp_port': 7882, 'use_external_ip': False},
            'redis': {'address': 'redis:6379'}, 'keys': {key: secret},
            'room': {'auto_create': False, 'max_participants': 8, 'empty_timeout': 120},
            'logging': {'level': 'warn'}},
        'egress.json': {'api_key': key, 'api_secret': secret, 'ws_url': 'ws://livekit:7880',
            'insecure': True, 'redis': {'address': 'redis:6379'}, 'health_port': 9090,
            'log_level': 'warn', 'session_limits': {'file_output_max_duration': '1h',
            'stream_output_max_duration': '1h'}}}
    for name, value in configs.items():
        # Unique UID services share a deployment-owned config group. Operator sets
        # the directory group to the containers' supplemental group before launch.
        fd = os.open(target / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        os.fchmod(fd, 0o640)
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream)


if __name__ == '__main__':
    configure()
