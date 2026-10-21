"""Keep tokens and private keys out of logs."""

from __future__ import annotations

import logging
import re

_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    # Installation tokens can contain "-" and ".", so redact the whole token, not just a prefix.
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_.-]+"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"(?i)(authorization:\s*bearer\s+)\S+"),
    re.compile(r"(?i)(x-tank-key:\s*)\S+"),
    re.compile(r"(?i)(password=)\S+"),
    re.compile(r"x-access-token:[^@\s]+"),
)


def redact(text: str) -> str:
    cleaned = text
    for pattern in _PATTERNS:
        cleaned = pattern.sub(lambda match: (match.group(1) + "[redacted]") if match.lastindex else "[redacted]", cleaned)
    return cleaned


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(record.getMessage())
        record.args = ()
        return True


def install() -> None:
    logging.getLogger().addFilter(RedactFilter())
