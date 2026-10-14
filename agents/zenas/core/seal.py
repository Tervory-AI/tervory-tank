"""Encrypt one identifier before it is stored. The chassis image has no cipher
library, so this is a keyed stream plus a MAC from the standard library."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import secrets


def key_bytes(value: str | None) -> bytes | None:
    if not value or not value.strip():
        return None
    try:
        key = bytes.fromhex(value.strip())
    except ValueError:
        return None
    if len(key) < 32:
        return None
    return key


def key_from_env(env: dict[str, str] | None = None) -> bytes | None:
    source = env if env is not None else os.environ
    return key_bytes(source.get("ZENAS_PII_KEY"))


def _stream(key: bytes, nonce: bytes, size: int) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < size:
        block = hashlib.sha256(key + nonce + counter.to_bytes(4, "big")).digest()
        out.extend(block)
        counter += 1
    return bytes(out[:size])


def seal(plaintext: str, key: bytes) -> str:
    if len(key) < 32:
        raise ValueError("pii key is too short")
    raw = plaintext.encode("utf-8")
    nonce = secrets.token_bytes(16)
    body = bytes(left ^ right for left, right in zip(raw, _stream(key, nonce, len(raw))))
    mac = hmac.new(key, b"zenas.pii" + nonce + body, hashlib.sha256).digest()
    return base64.b64encode(nonce + mac + body).decode("ascii")


def open_seal(token: str, key: bytes) -> str:
    blob = base64.b64decode(token)
    if len(blob) < 48:
        raise ValueError("pii seal failed")
    nonce, mac, body = blob[:16], blob[16:48], blob[48:]
    expect = hmac.new(key, b"zenas.pii" + nonce + body, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expect):
        raise ValueError("pii seal failed")
    raw = bytes(left ^ right for left, right in zip(body, _stream(key, nonce, len(body))))
    return raw.decode("utf-8")
