"""One machine/account: remote demo exclusively owns execution until it exits.

Locks are kept by inherited file descriptors, including after an API/agent crash.
Closing a parent's descriptor must not explicitly unlock the child's descriptor.
"""

import fcntl
import os
from contextlib import contextmanager
from pathlib import Path

from app.services.store import ServiceError


@contextmanager
def execution_gate(path: Path, *, remote: bool = False):
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(descriptor, (fcntl.LOCK_EX if remote else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ServiceError(
                409,
                "EXECUTION_IN_USE",
                "Remote demo owns execution, or an existing local task is still running",
            ) from None
        yield descriptor
    finally:
        os.close(descriptor)


def local_suspended(path: Path) -> bool:
    try:
        with execution_gate(path):
            return False
    except ServiceError:
        return True
