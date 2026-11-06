"""Bounded reads and locks for Autumbra's private metadata files."""
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import stat
import time


def checked_path(path: Path) -> Path:
    path = Path(path).absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("Autumbra storage is unavailable.")
    return path


def read_json(path: Path, *, limit: int = 2_000_000):
    path = checked_path(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as file:
        meta = os.fstat(file.fileno())
        if not stat.S_ISREG(meta.st_mode) or meta.st_size > limit:
            raise ValueError("Autumbra storage is unavailable.")
        raw = file.read(limit + 1)
        if len(raw) > limit:
            raise ValueError("Autumbra storage is unavailable.")
    return json.loads(raw)


@contextmanager
def file_lock(path: Path, *, timeout: float = 30):
    path = checked_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    with os.fdopen(descriptor, "a") as lock:
        if not stat.S_ISREG(os.fstat(lock.fileno()).st_mode):
            raise ValueError("Autumbra storage is unavailable.")
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise TimeoutError("Autumbra storage is busy.") from None
                time.sleep(min(.05, max(0, deadline - time.monotonic())))
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
