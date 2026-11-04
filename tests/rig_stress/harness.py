"""Prompt G preparation. Explicit workload only; never provisions or seeds a target."""
from __future__ import annotations

import argparse
import asyncio
import http.client
import ipaddress
import json
import math
import subprocess
import time
from pathlib import Path
from urllib.parse import urlsplit

LABEL = 'rigstress.isolated'
LEVELS = (5, 10, 20, 30)
LIMITS = {'search_p95_s': 1, 'quote_p95_s': 2, 'memory_fraction': .8,
          'forge_queue_wait_s': 300}
OPERATIONS = {'search': ('GET', '/v1/rig/search'),
              'setup': ('POST', '/v1/rig/setups'), 'quote': ('POST', '/v1/rig/quote')}


def measured(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def quantile(values: list[float], fraction: float) -> float | None:
    """Nearest rank; no observations must never count as a pass."""
    if not 0 < fraction <= 1 or not values or not all(measured(value) for value in values):
        return None
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)]


def failures(metrics: dict) -> list[str]:
    bad = [key for key, limit in LIMITS.items()
           if not measured(metrics.get(key)) or metrics[key] >= limit]
    if type(metrics.get('errors')) is not int or metrics['errors'] != 0:
        bad.append('errors')
    if type(metrics.get('dropped')) is not int or metrics['dropped'] != 0:
        bad.append('dropped')
    return bad


def docker(*args: str):
    result = subprocess.run(['docker', '--host=unix:///var/run/docker.sock', *args],
                            check=True, capture_output=True, text=True, timeout=15)
    return json.loads(result.stdout)


def validate_url(url: str, allowlist: list[str]) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != 'http' or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('Only credential-free HTTP origins are accepted')
    if parsed.path not in ('', '/') or not parsed.port:
        raise ValueError('Target must be an origin with an explicit port')
    # Literal RFC1918 only: no DNS, public addresses, redirects or production domains.
    address = ipaddress.ip_address(parsed.hostname or '')
    private = any(address in ipaddress.ip_network(net) for net in
                  ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
    if not private or url not in allowlist:
        raise ValueError('Target must be an explicitly allowlisted RFC1918 literal')
    return str(address)


def preflight(config: dict) -> None:
    if config.get('dedicated_spare_host') is not True:
        raise ValueError('Preflight requires explicit dedicated spare host confirmation')
    name = config['network']
    if not name.startswith('rigstress-'):
        raise ValueError('A dedicated rigstress- network is required')
    network = docker('network', 'inspect', name)[0]
    if network['Internal'] is not True or (network.get('Labels') or {}).get(LABEL) != 'true':
        raise ValueError('Network must be internal and labelled rigstress.isolated=true')
    members = network.get('Containers') or {}
    if not members:
        raise ValueError('No isolated targets')
    addresses = set()
    for identity in members:
        container = docker('inspect', identity)[0]
        if (container['Config'].get('Labels') or {}).get(LABEL) != 'true':
            raise ValueError('Every network member must be explicitly test labelled')
        if set(container['NetworkSettings']['Networks']) != {name}:
            raise ValueError('Targets must have exactly the isolated test network')
        host = container['HostConfig']
        if host.get('Privileged') or host.get('PortBindings') or container.get('Mounts'):
            raise ValueError('No privileged targets, published ports or mounted data')
        if host.get('NetworkMode') in ('host', 'default', 'bridge', 'coolify'):
            raise ValueError('Production/default networks forbidden')
        addresses.add(container['NetworkSettings']['Networks'][name]['IPAddress'])
    for store in config['stores']:
        if validate_url(store['target'], config['target_allowlist']) not in addresses:
            raise ValueError('Target is not an inspected isolated network member')


def load_config(path: Path) -> dict:
    config = json.loads(path.read_text())
    if not isinstance(config, dict):
        raise ValueError('Configuration must be an object')
    for field in ('rps_per_store', 'concurrency_per_store', 'catalogue_fixture',
                  'forge_fixture', 'stores', 'target_allowlist', 'network', 'dedicated_spare_host'):
        if field not in config:
            raise ValueError('Missing explicit setting: ' + field)
    for field in ('rps_per_store', 'concurrency_per_store'):
        value = config[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError('Positive finite workload required: ' + field)
    if not isinstance(config['concurrency_per_store'], int):
        raise ValueError('Concurrency must be an integer')
    for field in ('catalogue_fixture', 'forge_fixture'):
        fixture = (path.parent / config[field]).resolve()
        if not fixture.is_file():
            raise ValueError('Missing private test fixture: ' + field)
    if not isinstance(config['stores'], list) or len(config['stores']) != 30:
        raise ValueError('Explicit configuration for all 30 stores required')
    for store in config['stores']:
        validate_url(store['target'], config['target_allowlist'])
        if set(store['operations']) != {'search', 'setup', 'quote'}:
            raise ValueError('Explicit search/setup/quote request fixtures required')
        for kind, operation in store['operations'].items():
            if (operation['method'], operation['path']) != OPERATIONS[kind]:
                raise ValueError('Operation must match its exact approved Rig method/path')
            if set(operation) - {'method', 'path', 'body', 'expected_statuses'}:
                raise ValueError('Only reviewed operation fields are supported')
            statuses = operation.get('expected_statuses')
            if (not isinstance(statuses, list) or not statuses
                    or any(type(status) is not int or not 200 <= status < 300 for status in statuses)):
                raise ValueError('Expected statuses must be an explicit nonempty list of 2xx codes')
    return config


def request(origin: str, operation: dict) -> tuple[float, bool]:
    target = urlsplit(origin)
    connection = http.client.HTTPConnection(target.hostname, target.port, timeout=5)
    started = time.monotonic()
    try:
        body = json.dumps(operation['body']) if 'body' in operation else None
        connection.request(operation['method'], operation['path'], body,
                           {'Content-Type': 'application/json'})
        response = connection.getresponse()
        response.read(1024 * 1024)
        return time.monotonic() - started, response.status in operation['expected_statuses']
    except (OSError, http.client.HTTPException):
        return time.monotonic() - started, False
    finally:
        connection.close()


async def traffic(stores: list[dict], rps: float, concurrency: int, duration: float) -> dict:
    """Fixed arrivals; no unbounded task backlog. Report overload instead of hiding it."""
    output = {'latency': {'search': [], 'setup': [], 'quote': []}, 'errors': 0, 'dropped': 0}

    async def shopper(store):
        active = set()
        limit = asyncio.Semaphore(concurrency)
        operations = list(store['operations'].items())
        start = time.monotonic()
        sequence = 0

        async def one(kind, operation):
            try:
                elapsed, ok = await asyncio.to_thread(request, store['target'], operation)
                output['latency'][kind].append(elapsed)
                output['errors'] += int(not ok)
            finally:
                limit.release()

        while time.monotonic() < start + duration:
            deadline = start + sequence / rps
            await asyncio.sleep(max(0, deadline - time.monotonic()))
            if time.monotonic() >= start + duration:
                break
            kind, operation = operations[sequence % len(operations)]
            sequence += 1
            if limit.locked():
                output['dropped'] += 1
                continue
            await limit.acquire()
            task = asyncio.create_task(one(kind, operation))
            active.add(task)
            task.add_done_callback(active.discard)
        if active:
            await asyncio.gather(*active)

    await asyncio.gather(*(shopper(store) for store in stores))
    return output


def report(traffic_result: dict, samples: list[dict], queue_waits: list[float]) -> dict:
    """Require measured host/queue inputs; no idle or absent sample can prove capacity."""
    latency = traffic_result['latency']
    valid_samples = bool(samples) and all(
        measured(sample.get('memory_used_bytes')) and measured(sample.get('memory_total_bytes'))
        and sample['memory_total_bytes'] > 0
        and sample['memory_used_bytes'] <= sample['memory_total_bytes'] for sample in samples)
    metrics = {
        'errors': traffic_result['errors'], 'dropped': traffic_result['dropped'],
        'search_p95_s': quantile(latency['search'], .95),
        'quote_p95_s': quantile(latency['quote'], .95),
        'memory_fraction': max((s['memory_used_bytes'] / s['memory_total_bytes']
                                for s in samples), default=None) if valid_samples else None,
        'forge_queue_wait_s': max(queue_waits) if queue_waits and all(map(measured, queue_waits)) else None,
    }
    result = {'metrics': metrics, 'failed_limits': failures(metrics),
              'latency_seconds': {kind: {'p50': quantile(values, .5),
                                        'p95': quantile(values, .95), 'count': len(values)}
                                  for kind, values in latency.items()},
              'samples': samples, 'capacity_valid': False}
    # A wiring report is deliberately never a saturation/clients-per-box result.
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('config', type=Path)
    parser.add_argument('--isolated-test-target', action='store_true')
    args = parser.parse_args()
    if not args.isolated_test_target:
        parser.error('--isolated-test-target is required even for preflight')
    config = load_config(args.config)
    preflight(config)
    # Refuse incomplete saturation wiring rather than manufacture box capacity.
    print(json.dumps({'status': 'preflight_only', 'levels': LEVELS,
                      'seconds_per_level': 900, 'sample_interval_seconds': 30,
                      'limits': LIMITS, 'capacity_valid': False,
                      'remaining': 'Dedicated forge queue and host metrics adapters must be wired before saturation'}))


if __name__ == '__main__':
    main()
