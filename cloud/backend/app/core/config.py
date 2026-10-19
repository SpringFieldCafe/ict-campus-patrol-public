"""Adapted from fastapi/full-stack-fastapi-template (MIT); see UPSTREAM.md."""

import os
import sys
import tempfile
from pathlib import Path

from pydantic import EmailStr, Field, SecretStr, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env", env_ignore_empty=True, extra="ignore"
    )
    PROJECT_NAME: str = "Campus Patrol API"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = Field(min_length=32)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=120, ge=1, le=1440)
    FIRST_SUPERUSER: EmailStr = "operator@example.com"
    FIRST_SUPERUSER_PASSWORD: str = Field(min_length=16)
    FRONTEND_ORIGINS: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    APP_DATA_DIR: Path = REPO_ROOT / ".local/backend"
    GO2_CONFIG: Path = REPO_ROOT / "edge/go2/runtime/config.example.json"
    GO2_POINTS: Path = REPO_ROOT / "edge/go2/runtime/observation-points.example.json"
    GO2_PYTHON: str = sys.executable
    MOTION_ENABLED: bool = False
    CAMERA_SOURCE: str = "unitree"
    CAPTURE_PYTHON: str | None = None
    DOCK_HOST: str | None = None
    DOCK_USER: str = "unitree"
    DOCK_DEVICE: str = "/dev/video4"
    TASK_TIMEOUT_SECONDS: float = Field(default=90, gt=0, le=600)
    SIM_SOURCE: Path = REPO_ROOT / "edge/go2/simulation/src"
    SIM_ROUTES: Path = REPO_ROOT / "edge/go2/simulation/routes.json"
    SIM_PYTHON: str | None = None
    SIM_HIMLOCO_POLICY: Path | None = REPO_ROOT / "edge/go2/simulation/assets/himloco.pt"
    SIM_NAVIGATION_POLICY: Path | None = REPO_ROOT / "edge/go2/simulation/assets/navigation.pt"
    SIM_SCENE: str = "himloco_flat"
    SIM_STEPS: int = Field(default=30000, ge=1, le=120000)
    SIM_RECORD_VIDEO: bool = True
    EXECUTION_LOCK_PATH: Path = Path(tempfile.gettempdir()) / f"campus-execution-{os.getuid()}.lock"
    REMOTE_ENABLED: bool = False
    REMOTE_EXECUTOR_KEY: SecretStr | None = None
    REMOTE_DEVICE_ID: str = "ubuntu-simulation"
    REMOTE_ROUTE_ID: str = "checkpoints-simple"
    REMOTE_SERVER_URL: str | None = None
    REMOTE_POLL_SECONDS: float = Field(default=1, ge=0.1, le=10)
    REMOTE_OFFLINE_SECONDS: float = Field(default=10, ge=1, le=120)
    REMOTE_DISPATCH_SECONDS: float = Field(default=10, ge=1, le=60)
    REMOTE_MAX_VIDEO_BYTES: int = Field(default=64 * 1024 * 1024, gt=0, le=256 * 1024 * 1024)
    REMOTE_DEMO_USER: EmailStr = "judge@example.com"
    REMOTE_DEMO_PASSWORD: SecretStr | None = None
    HUAWEI_CHAT_COMPLETIONS_URL: str | None = None
    HUAWEI_MODEL: str | None = None
    HUAWEI_API_KEY: SecretStr | None = None
    HUAWEI_TIMEOUT_SECONDS: float = Field(default=45, gt=0, le=120)
    MAX_PHOTO_BYTES: int = Field(default=10 * 1024 * 1024, gt=0, le=20 * 1024 * 1024)

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return "sqlite:///" + str(self.APP_DATA_DIR.resolve() / "accounts.sqlite3")

    @property
    def huawei_configured(self) -> bool:
        return bool(self.HUAWEI_CHAT_COMPLETIONS_URL and self.HUAWEI_MODEL and self.HUAWEI_API_KEY)

    @model_validator(mode="after")
    def validate_local_settings(self):
        if self.SECRET_KEY == "changethis" or self.FIRST_SUPERUSER_PASSWORD == "changethis":
            raise ValueError("Generate local credentials with scripts/init_local.py")
        if not self.APP_DATA_DIR.is_absolute():
            raise ValueError("APP_DATA_DIR must be absolute")
        if self.CAMERA_SOURCE not in {"unitree", "dock"}:
            raise ValueError("CAMERA_SOURCE must be unitree or dock")
        if self.REMOTE_ENABLED and (
            not self.REMOTE_EXECUTOR_KEY or len(self.REMOTE_EXECUTOR_KEY.get_secret_value()) < 32
        ):
            raise ValueError(
                "Remote service requires a separate executor key (at least 32 characters)"
            )
        if self.REMOTE_ENABLED and self.MOTION_ENABLED:
            raise ValueError("Remote service is simulation-only; motion must remain disabled")
        if self.REMOTE_DEMO_PASSWORD and len(self.REMOTE_DEMO_PASSWORD.get_secret_value()) < 16:
            raise ValueError("Demo password requires at least 16 characters")
        if self.HUAWEI_CHAT_COMPLETIONS_URL:
            from urllib.parse import urlparse

            parsed = urlparse(self.HUAWEI_CHAT_COMPLETIONS_URL)
            if (
                parsed.scheme != "https"
                or not parsed.hostname
                or parsed.username
                or parsed.password
            ):
                raise ValueError("Huawei endpoint must be an HTTPS URL without credentials")
        return self


settings = Settings(_env_file=os.environ.get("CAMPUS_ENV_FILE", BACKEND_ROOT / ".env"))
