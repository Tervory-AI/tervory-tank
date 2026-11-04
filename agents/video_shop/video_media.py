"""HTTPS download with DNS pinned to validated public addresses; no redirects."""
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit

from .video_engine import MAX_BYTES


def download(url, limit=MAX_BYTES):
    parsed = urlsplit(url)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.port not in (None, 443) or len(url) > 2000):
        raise ValueError('url')
    addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
    ips = [ipaddress.ip_address(entry[4][0]) for entry in addresses]
    if not ips or any(not ip.is_global or ip.is_multicast for ip in ips):
        raise ValueError('url_address')
    connection = http.client.HTTPSConnection(parsed.hostname, timeout=15, context=ssl.create_default_context())
    # Preserve original hostname for TLS and Host while preventing DNS rebinding.
    connection._create_connection = lambda address, timeout, source_address=None: socket.create_connection(
        (str(ips[0]), 443), timeout, source_address)
    try:
        connection.request('GET', parsed.path + ('?' + parsed.query if parsed.query else '') or '/')
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError('url_response')
        result = bytearray()
        deadline = time.monotonic() + 45
        while chunk := response.read(65536):
            result.extend(chunk)
            if len(result) > limit or time.monotonic() > deadline:
                raise ValueError('media_limit')
        return bytes(result)
    except http.client.HTTPException:
        raise ValueError('url_response') from None
    finally:
        connection.close()
