"""Infrastructure probe only. Transport readiness never claims hearing/AI readiness."""
import json
import os
import socket
import ssl
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

REGION = os.environ.get('MOOT_REGION')
if REGION not in {'us-east', 'za'}:
    raise SystemExit('MOOT_REGION must be us-east or za')


def ready():
    try:
        with socket.create_connection(('redis', 6379), timeout=1) as conn:
            conn.sendall(b'*1\r\n$4\r\nPING\r\n')
            if conn.recv(32) != b'+PONG\r\n':
                return False
        # Internal transport probe must not use an inherited outbound proxy.
        with urllib.request.build_opener(urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=ssl.create_default_context(
                cafile=os.environ.get('SSL_CERT_FILE')))).open(
            'https://livekit-tls:8443/', timeout=1
        ) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in {'/healthz', '/readyz'}:
            self.send_error(404)
            return
        healthy = self.path == '/healthz' or ready()
        body = json.dumps({'product': 'moot', 'region': REGION,
            'transport_ready': healthy if self.path == '/readyz' else None,
            'hearing_runtime': 'not_connected', 'speech': 'unavailable'}).encode()
        self.send_response(200 if healthy else 503)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


if __name__ == '__main__':
    ThreadingHTTPServer(('0.0.0.0', 8090), Handler).serve_forever()
