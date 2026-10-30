"""Isolated Docker transport proof; fake lease/DNS/upstream, real private sockets.

Run --server and --client in two containers on one throwaway internal network.
No public address is dialed: the injected upstream is a local socketpair.
"""
import argparse
import asyncio
import socket
import threading
from uuid import UUID

import egress
import passive_gateway

TENANT = UUID('11111111-1111-4111-8111-111111111111')
SCAN = UUID('33333333-3333-4333-8333-333333333333')


async def server():
    class Store:
        async def pending(self, tenant, ident):
            assert (tenant, ident) == (TENANT, SCAN)
            return {'domain': 'owned.example', 'challenge': 'dummy-public-proof'}
        async def running(self, tenant, ident):
            return (tenant, ident) == (TENANT, SCAN)
        async def fail(self, *args):
            pass
    async def proof(domain, challenge):
        return (domain, challenge) == ('owned.example', 'dummy-public-proof')
    def connect(address, port):
        assert (address, port) == ('93.184.216.34', 443)
        one, two = socket.socketpair()
        def peer():
            with two:
                assert two.recv(10) == b'ping'
                two.sendall(b'pong')
        threading.Thread(target=peer, daemon=True).start()
        return one
    def proxy(**kwargs):
        kwargs.update(resolve=lambda host: '93.184.216.34', connect=connect)
        return egress.Proxy(**kwargs)
    passive_gateway.Proxy = proxy
    lease = passive_gateway.Lease(Store(), check=proof)
    bind = egress.private_bind_address()
    static = egress.Server(egress.Proxy(), host=bind, port=8080).start()
    try:
        assert await lease.start(TENANT, SCAN) == {'ready': True}
        print('READY: explicit private listeners 8080/8082; fake authorized lease and upstream', flush=True)
        await asyncio.Event().wait()
    finally:
        await lease.release(TENANT, SCAN)
        static.close()


def client(passive=False):
    host = 'radix-passive-proxy' if passive else 'radix-proxy-bind-proof'
    with socket.create_connection((host, 8080), timeout=5) as conn:
        conn.sendall(b'GET /health HTTP/1.1\r\nHost: radix-proxy-bind-proof\r\n\r\n')
        assert b'200 OK' in conn.recv(1024)
    for host in ('other.example', 'lokd.co.za', '127.0.0.1'):
        with socket.create_connection(('radix-passive-proxy' if passive else 'radix-proxy-bind-proof', 8082), timeout=5) as conn:
            conn.sendall(f'CONNECT {host}:443 HTTP/1.1\r\nHost: {host}:443\r\n\r\n'.encode())
            assert b'403' in conn.recv(1024)
    with socket.create_connection(('radix-passive-proxy' if passive else 'radix-proxy-bind-proof', 8082), timeout=5) as conn:
        conn.sendall(b'CONNECT owned.example:443 HTTP/1.1\r\nHost: owned.example:443\r\n\r\n')
        assert b'200 Connection Established' in conn.recv(1024)
        conn.sendall(b'ping')
        assert conn.recv(10) == b'pong'
    print('PASS: peer container reaches private 8080 health and leased 8082 tunnel; other hosts refused')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--server', action='store_true')
    parser.add_argument('--passive', action='store_true')
    args = parser.parse_args()
    if args.server:
        asyncio.run(server())
    else:
        client(args.passive)
