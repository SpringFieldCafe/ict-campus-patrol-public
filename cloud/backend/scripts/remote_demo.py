"""Prepare ignored two-node configs without printing passwords or executor keys."""

import json
import os
import secrets
from pathlib import Path

from app.core.config import REPO_ROOT, settings

ROOT = REPO_ROOT / ".local/remote-demo"


def write_private(path: Path, values: dict):
    if path.exists():
        print(f"Preserved existing {path.name}")
        return
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        for key, value in values.items():
            if value is not None:
                output.write(key + "=" + json.dumps(str(value), ensure_ascii=False) + "\n")


def main():
    ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    key_path = ROOT / "executor-key"
    if not key_path.exists():
        descriptor = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as output:
            output.write(secrets.token_urlsafe(48))
    key = key_path.read_text()
    write_private(
        ROOT / "server.env",
        {
            "SECRET_KEY": secrets.token_urlsafe(48),
            "FIRST_SUPERUSER": "operator@example.com",
            "FIRST_SUPERUSER_PASSWORD": secrets.token_urlsafe(24),
            "REMOTE_DEMO_USER": "judge@example.com",
            "REMOTE_DEMO_PASSWORD": secrets.token_urlsafe(24),
            "APP_DATA_DIR": ROOT / "server",
            "REMOTE_ENABLED": "true",
            "REMOTE_EXECUTOR_KEY": key,
            "MOTION_ENABLED": "false",
            "SIM_RECORD_VIDEO": "true",
            # The coordinator deliberately has no simulation interpreter or weights.
            "SIM_SOURCE": ROOT / "server-does-not-have-simulation",
            "SIM_HIMLOCO_POLICY": ROOT / "absent-himloco.pt",
            "SIM_NAVIGATION_POLICY": ROOT / "absent-navigation.pt",
        },
    )
    write_private(
        ROOT / "executor.env",
        {
            "SECRET_KEY": secrets.token_urlsafe(48),
            "FIRST_SUPERUSER_PASSWORD": secrets.token_urlsafe(24),
            "APP_DATA_DIR": ROOT / "executor",
            "REMOTE_ENABLED": "false",
            "REMOTE_EXECUTOR_KEY": key,
            "REMOTE_SERVER_URL": "http://127.0.0.1:8010",
            "MOTION_ENABLED": "false",
            "SIM_RECORD_VIDEO": "true",
            "SIM_PYTHON": settings.SIM_PYTHON,
            "SIM_SOURCE": settings.SIM_SOURCE,
            "SIM_HIMLOCO_POLICY": settings.SIM_HIMLOCO_POLICY,
            "SIM_NAVIGATION_POLICY": settings.SIM_NAVIGATION_POLICY,
            "EXECUTION_LOCK_PATH": settings.EXECUTION_LOCK_PATH,
        },
    )
    print("Prepared private server.env and executor.env under .local/remote-demo.")
    print("Remote execution remains off until the explicit server/executor commands are run.")
    print("Read the judge/admin credentials locally from server.env; do not paste them into chat.")


if __name__ == "__main__":
    main()
