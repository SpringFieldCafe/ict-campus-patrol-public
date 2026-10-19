"""Create ignored local configuration without printing any credentials."""

import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
destination = root / ".env"
if destination.exists():
    print("Existing cloud/backend/.env preserved.")
else:
    values = (root / ".env.example").read_text()
    values = values.replace("GENERATE_SECRET_KEY", secrets.token_urlsafe(48))
    values = values.replace("GENERATE_OPERATOR_PASSWORD", secrets.token_urlsafe(24))
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as output:
        output.write(values)
    print("Created ignored cloud/backend/.env (0600). Read credentials locally when needed.")
