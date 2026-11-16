"""OS-owned locks survive neither process crashes nor device reassignment."""

import fcntl
import hashlib
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def exclusive(path, description):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(f"{description} is already in use.") from error
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


@contextmanager
def device_lock(serial):
    lock_dir = Path(tempfile.gettempdir()) / f"taktik-devices-{os.getuid()}"
    lock_dir.mkdir(mode=0o700, exist_ok=True)
    key = hashlib.sha256(serial.encode()).hexdigest()
    with exclusive(lock_dir / key, f"Device {serial}"):
        yield
