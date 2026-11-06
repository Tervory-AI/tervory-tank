"""Repository ingress contract. Compose config only: never builds or starts a service."""
from __future__ import annotations

import copy
import ipaddress
import json
import os
import re
import shutil
import subprocess
import unittest

import yaml
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'docs/ops/PRODUCT-HOSTS.md'
TOKEN = re.compile(r'\s*(Host|PathPrefix|Path|`[^`]*`|&&|\|\||[!(),])')


class Predicate:
    """Parse a deliberately small rule grammar; unknown matchers fail closed."""
    def __init__(self, text):
        self.tokens = []
        pos = 0
        while pos < len(text):
            match = TOKEN.match(text, pos)
            if not match:
                raise ValueError('Unsupported routing predicate')
            self.tokens.append(match[1])
            pos = match.end()
        self.index = 0
        self.tree = self.expression()
        if self.index != len(self.tokens):
            raise ValueError('Trailing routing predicate')

    def take(self, token=None):
        if self.index >= len(self.tokens):
            raise ValueError('Incomplete routing predicate')
        value = self.tokens[self.index]
        if token is not None and value != token:
            raise ValueError('Unexpected routing token')
        self.index += 1
        return value

    def peek(self, token):
        return self.index < len(self.tokens) and self.tokens[self.index] == token

    def expression(self):
        left = self.conjunction()
        while self.peek('||'):
            self.take(); left = ('or', left, self.conjunction())
        return left

    def conjunction(self):
        left = self.atom()
        while self.peek('&&'):
            self.take(); left = ('and', left, self.atom())
        return left

    def atom(self):
        if self.peek('!'):
            self.take(); return ('not', self.atom())
        if self.peek('('):
            self.take(); value = self.expression(); self.take(')'); return value
        kind = self.take()
        if kind not in ('Host', 'Path', 'PathPrefix'):
            raise ValueError('Unsupported routing matcher')
        self.take('('); value = self.take(); self.take(')')
        if not value.startswith('`') or not value.endswith('`'):
            raise ValueError('Routing arguments must be literals')
        return (kind, value[1:-1])

    def matches(self, host, path):
        def visit(node):
            kind = node[0]
            if kind == 'and': return visit(node[1]) and visit(node[2])
            if kind == 'or': return visit(node[1]) or visit(node[2])
            if kind == 'not': return not visit(node[1])
            if kind == 'Host': return host == node[1]
            if kind == 'Path': return path == node[1]
            return path.startswith(node[1])
        return visit(self.tree)


def load_contract():
    text = CONTRACT.read_text()
    blocks = re.findall(r'```json\n(.*?)\n```', text, re.S)
    if len(blocks) != 1:
        raise ValueError('Expected exactly one routing table')
    rows = json.loads(blocks[0])
    if not isinstance(rows, list) or not rows:
        raise ValueError('Routing table must be nonempty')
    # DECISION keep the new engine ingress authority in machine configuration;
    # the founder requested no document edits. Every existing gate still applies.
    return rows + json.loads((ROOT / 'litellm/langfuse-ingress.json').read_text())


def compose_files(root=ROOT):
    # Tracked files only: never a local .env, build output or node_modules copy.
    paths = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    return [p for p in paths if re.search(r'(?:^|/)(?:docker-)?compose[^/]*\.ya?ml$', p)]


def compose_config(path, root=ROOT):
    """Use synthetic required inputs, defaults otherwise; never inherit production keys."""
    text = (root / path).read_text()
    required = set(re.findall(r'\$\{([A-Z][A-Z0-9_]*):?\?', text))
    env = {'PATH': os.defpath + ':/usr/local/bin', 'HOME': '/nonexistent',
           **{key: 'routing-ci' for key in required}}
    # The frozen sign-in compose has a required, public network name.
    if 'TRIGGER_SIGNIN_PROXY_NETWORK' in required:
        env['TRIGGER_SIGNIN_PROXY_NETWORK'] = 'coolify'
    # Coolify strips this boolean metadata before invoking Compose. Preserve it
    # as an x-extension for offline schema validation; never drop runtime fields.
    for spec in yaml.safe_load(text).get('services', {}).values():
        if 'exclude_from_hc' in spec and not isinstance(spec['exclude_from_hc'], bool):
            raise ValueError('Invalid Coolify health metadata')
    text = re.sub(r'(?m)^(    )exclude_from_hc:', r'\1x-coolify-exclude-from-hc:', text)
    command = ['docker', 'compose', '--env-file', '/dev/null', '--project-name', 'routing-ci',
               '--project-directory', str((root / path).parent), '-f', '-', 'config', '--format', 'json', '--no-path-resolution']
    result = subprocess.run(command, env=env, input=text, capture_output=True, text=True, timeout=30)
    if result.returncode:
        # Synthetic inputs only, but do not emit rendered environments or raw errors.
        raise ValueError(f'{path}: docker compose config failed (exit {result.returncode})')
    return json.loads(result.stdout)


def routers(configs):
    out = {}
    for file, config in configs.items():
        for service, spec in config['services'].items():
            labels = spec.get('labels') or {}
            if isinstance(labels, list): labels = dict(x.split('=', 1) for x in labels)
            for key, rule in labels.items():
                if re.match(r'traefik\.(tcp|udp)\.routers\.', key):
                    raise ValueError('Non-HTTP ingress needs an explicit contract schema review')
                match = re.fullmatch(r'traefik\.http\.routers\.([^.]+)\.rule', key)
                if not match: continue
                name = match[1]; prefix = f'traefik.http.routers.{name}.'
                out[file, name] = {'service': service, 'spec': spec, 'labels': labels,
                                   'rule': rule, 'prefix': prefix, 'config': config}
    return out


def validate(configs, rows):
    actual = routers(configs)
    expected = {}
    required = {'host', 'paths', 'service', 'port', 'network', 'access', 'compose', 'router', 'priority'}
    for row in rows:
        if set(row) != required: raise ValueError('Invalid routing table columns')
        if row['access'] not in ('public', 'Access-protected'): raise ValueError('Invalid access class')
        if not re.fullmatch(r'[a-z0-9.-]+', row['host']): raise ValueError('Invalid hostname')
        try: ipaddress.ip_address(row['host'])
        except ValueError: pass
        else: raise ValueError('IP addresses are not public product hostnames')
        key = row['compose'], row['router']
        if any(x['host'] == row['host'] for x in expected.get(key, [])):
            raise ValueError('Duplicate routing row')
        expected.setdefault(key, []).append(row)
    for key, entry in actual.items():
        labels, prefix = entry['labels'], entry['prefix']
        https = labels.get(prefix + 'entrypoints') == 'https'
        peer = key if https else (key[0], key[1].removesuffix('-http') + '-https')
        if peer not in expected: raise ValueError(f'Undocumented router: {key}')
        group = expected[peer]
        first = group[0]
        if any({k:v for k,v in r.items() if k != 'host'} !=
               {k:v for k,v in first.items() if k != 'host'} for r in group):
            raise ValueError('Inconsistent multi-host routing rows')
        hosts = [r['host'] for r in group]
        host_rule = ' || '.join(f'Host(`{h}`)' for h in hosts)
        if len(hosts) > 1: host_rule = '(' + host_rule + ')'
        # Existing frozen API has no explicit PathPrefix; it is logically a catch-all.
        wanted = host_rule + ' && ' + first['paths']
        rule = entry['rule']
        if rule == host_rule: rule += ' && PathPrefix(`/`)'
        predicate = Predicate(rule)
        if predicate.tree != Predicate(wanted).tree: raise ValueError(f'Routing rule drift: {key}')
        if entry['service'] != first['service']: raise ValueError('Routing service drift')
        upstream = labels.get(prefix + 'service')
        # Legacy Rig HTTP router has one unambiguous explicit backend.
        if not upstream and not https and key == ('agents/rig/docker-compose.yml', 'rig-http'):
            upstream = 'rig'
        port = labels.get(f'traefik.http.services.{upstream}.loadbalancer.server.port')
        if str(first['port']) != str(port): raise ValueError('Missing or changed routing port')
        if str(first['priority']) != labels.get(prefix + 'priority'): raise ValueError('Routing priority drift')
        if labels.get('traefik.enable') != 'true': raise ValueError('Public router must be enabled')
        network = labels.get('traefik.docker.network')
        documented_network = first['network']
        if first['host'] == 'auth.tervory.com': documented_network = 'coolify'
        if network != documented_network: raise ValueError('Routing network drift')
        attached = entry['spec'].get('networks') or {'default': {}}
        netdefs = entry['config'].get('networks') or {}
        usable = [name for name in attached if (netdefs.get(name) or {}).get('name') == network
                  and not (netdefs.get(name) or {}).get('internal', False)]
        if not usable: raise ValueError('Public router has no matching non-internal proxy network')
        if https:
            if labels.get(prefix+'tls') != 'true' or labels.get(prefix+'tls.certresolver') != 'letsencrypt':
                raise ValueError('HTTPS router missing TLS/certificate resolver')
        else:
            if labels.get(prefix+'entrypoints') != 'http': raise ValueError('Unknown ingress entrypoint')
            middlewares = labels.get(prefix+'middlewares', '').split(',')
            if not any(m == 'redirect-to-https' or labels.get(
                f'traefik.http.middlewares.{m}.redirectscheme.scheme') == 'https' for m in middlewares):
                raise ValueError('HTTP router must redirect to HTTPS')
        for row in group:
            # Sign-in's existing identity API is frozen and explicitly outside this migration.
            if row['host'] == 'auth.tervory.com': continue
            paths = ['/admin', '/admin/', '/admin/users', '/internal', '/internal/', '/internal/control']
            # Also inspect explicitly declared children that could evade generic probes.
            paths += re.findall(r'`(/(?:admin|internal)[^`]*)`', rule)
            if row['access'] != 'Access-protected' and (
                row['port'] not in (80, 443, 3000, 8000, 8080) or
                any(predicate.matches(row['host'], path) for path in paths)):
                raise ValueError('Public ingress exposes a restricted path or control port')
    missing = set(expected) - set(actual)
    if missing: raise ValueError(f'Unrouted product hosts: {sorted(missing)}')
    # Require the HTTP redirect pair for each migrated HTTPS router.
    for key, group in expected.items():
        if group[0]['host'] == 'auth.tervory.com': continue
        http = key[0], key[1].removesuffix('-https') + '-http'
        if http not in actual: raise ValueError('Missing HTTP redirect router')


class RoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Tank's test image has no Docker CLI. The always-required host-side
        # routing job invokes this file directly and must fail, never skip.
        if __name__ != '__main__' and shutil.which('docker') is None:
            raise unittest.SkipTest('Validated by the required host-side routing CI job')
        cls.rows = load_contract()
        cls.configs = {p: compose_config(p) for p in compose_files()}

    def test_all_compose_files_and_routing_contract(self):
        self.assertGreaterEqual(len(self.configs), 15)
        validate(self.configs, self.rows)

    def changed(self):
        return copy.deepcopy(self.configs), copy.deepcopy(self.rows)

    def test_missing_host_fails(self):
        configs, rows = self.changed()
        del configs['docker-compose.yml']['services']['workspace']['labels']['traefik.http.routers.product-rig-app-https.rule']
        with self.assertRaisesRegex(ValueError, 'Unrouted'): validate(configs, rows)

    def test_new_host_or_path_fails(self):
        for rule in ['Host(`unreviewed.tervory.com`) && PathPrefix(`/`)',
                     'Host(`rig.tervory.com`) && PathPrefix(`/new-path`)']:
            configs, rows = self.changed()
            configs['docker-compose.yml']['services']['workspace']['labels']['traefik.http.routers.product-rig-app-https.rule'] = rule
            with self.assertRaisesRegex(ValueError, 'drift'): validate(configs, rows)

    def test_new_undocumented_router_fails(self):
        configs, rows = self.changed()
        labels = configs['docker-compose.yml']['services']['workspace']['labels']
        labels['traefik.http.routers.surprise.rule'] = 'Host(`surprise.tervory.com`)'
        with self.assertRaisesRegex(ValueError, 'Undocumented'): validate(configs, rows)

    def test_non_http_ingress_fails_closed(self):
        configs, rows = self.changed()
        configs['docker-compose.yml']['services']['workspace']['labels']['traefik.tcp.routers.control.rule'] = 'HostSNI(`*`)'
        with self.assertRaisesRegex(ValueError, 'Non-HTTP'): validate(configs, rows)

    def test_internal_only_router_fails(self):
        configs, rows = self.changed()
        configs['docker-compose.yml']['networks']['product-proxy']['internal'] = True
        with self.assertRaisesRegex(ValueError, 'non-internal'): validate(configs, rows)

    def test_control_port_and_admin_path_fail_even_if_documented_as_public(self):
        for port, paths in [(8003, None), (3000, 'PathPrefix(`/internal/hidden`)'),
                            (3000, 'Path(`/admin/private`)')]:
            configs, rows = self.changed()
            labels = configs['docker-compose.yml']['services']['workspace']['labels']
            for row in rows:
                if row['router'] == 'product-rig-app-https':
                    row['port'] = port
                    if paths: row['paths'] = paths
            labels['traefik.http.services.product-workspace.loadbalancer.server.port'] = str(port)
            # Change all shared-port rows to exercise the security gate, not a drift check.
            for row in rows:
                if row['service'] == 'workspace': row['port'] = port
            if paths:
                for proto in ('http', 'https'):
                    labels[f'traefik.http.routers.product-rig-app-{proto}.rule'] = 'Host(`rig.tervory.com`) && ' + paths
            with self.assertRaisesRegex(ValueError, 'restricted'): validate(configs, rows)

    def test_split_rig_routes_never_overlap(self):
        actual = routers(self.configs)
        api = Predicate(actual['agents/rig/docker-compose.yml', 'rig-https']['rule'])
        app = Predicate(actual['docker-compose.yml', 'product-rig-app-https']['rule'])
        for path in ['/', '/rig', '/v1/rig', '/v1/rig/orders', '/widget/x', '/widgetevil',
                     '/health', '/page/x', '/product/x', '/storage/x', '/admin', '/internal/x']:
            count = sum(p.matches('rig.tervory.com', path) for p in (api, app))
            self.assertEqual(count, 0 if path.startswith(('/admin', '/internal')) else 1, path)

    def test_unknown_matchers_fail_closed(self):
        for rule in ['HostRegexp(`.*`)', 'PathPrefix(`/`) || Headers(`x`,`y`)', 'Host(`ok`) garbage']:
            with self.assertRaises(ValueError): Predicate(rule)


if __name__ == '__main__':
    unittest.main()
