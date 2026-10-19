"""Tests use private temporary data, synthetic images and a substitute subprocess."""

import json
import os
import secrets
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

os.environ["APP_DATA_DIR"] = tempfile.mkdtemp(prefix="campus-api-tests-")
os.environ["SECRET_KEY"] = secrets.token_urlsafe(48)
os.environ["FIRST_SUPERUSER_PASSWORD"] = secrets.token_urlsafe(24)
os.environ["FIRST_SUPERUSER"] = "operator@example.com"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.routes.tasks import get_service
from app.core.config import settings
from app.main import app
from app.services import runtime
from app.services.tasks import TaskService


@pytest.fixture
def api(tmp_path, monkeypatch):
    source = tmp_path / "source"
    module = source / "mujoco_sim"
    module.mkdir(parents=True)
    (module / "__init__.py").touch()
    (module / "run.py").write_text("""
import argparse, json, time
from pathlib import Path
p = argparse.ArgumentParser()
p.add_argument("--goal-x", type=float)
p.add_argument("--steps", type=int)
p.add_argument("--record")
p.add_argument("--log")
p.add_argument("--waypoints")
a, _ = p.parse_known_args()
Path(a.log).write_text(json.dumps({"step": 1, "position_xy": [0, 0], "target_distance": 1}) + "\\n")
time.sleep(20 if a.goal_x == 2 else 0.3)
if a.record: Path(a.record).write_bytes(b"synthetic-video-fixture")
summary = {"goal_reached": a.steps != 1, "fallen": False, "collision": False}
if a.waypoints:
 n = len(json.loads(Path(a.waypoints).read_text()))
 reached = n - 1 if a.steps == 2 else n
 summary.update(waypoints_total=n, waypoints_reached=reached, reached_indices=list(range(reached)))
print(json.dumps(summary))
""")
    policy = tmp_path / "policy.pt"
    policy.write_bytes(b"synthetic-policy-fixture")
    points = tmp_path / "points.json"
    points.write_text("""{"schema_version":1,"reference":"initial_pose","points":[
      {"id":"a","description":"synthetic short task","goal_forward":1,"goal_left":0},
      {"id":"b","description":"synthetic cancellable task","goal_forward":2,"goal_left":0}]}""")
    config = tmp_path / "runtime.json"
    config.write_text(json.dumps({"output_dir": str(tmp_path / "robot-output")}))
    # The public release excludes the optional robot CLI. Photo/analysis tests
    # use an explicit synthetic configuration adapter, just as simulation tests
    # use a temporary runner; no unpublished robot source is needed or exercised.
    monkeypatch.setattr(
        runtime, "runtime_config", lambda configured: json.loads(configured.GO2_CONFIG.read_text())
    )
    local = settings.model_copy(
        update={
            "APP_DATA_DIR": tmp_path / "data",
            "EXECUTION_LOCK_PATH": tmp_path / "execution.lock",
            "GO2_POINTS": points,
            "GO2_CONFIG": config,
            "SIM_SOURCE": source,
            "SIM_PYTHON": sys.executable,
            "SIM_HIMLOCO_POLICY": policy,
            "SIM_NAVIGATION_POLICY": policy,
            "SIM_RECORD_VIDEO": True,
            "SIM_STEPS": 100,
            "HUAWEI_API_KEY": None,
            "HUAWEI_MODEL": None,
            "HUAWEI_CHAT_COMPLETIONS_URL": None,
            "MOTION_ENABLED": False,
        }
    )
    service = TaskService(local)
    app.dependency_overrides[get_service] = lambda: service
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/login/access-token",
            data={
                "username": settings.FIRST_SUPERUSER,
                "password": settings.FIRST_SUPERUSER_PASSWORD,
            },
        )
        assert response.status_code == 200
        headers = {"Authorization": "Bearer " + response.json()["access_token"]}
        owner = client.get("/api/v1/users/me", headers=headers).json()["id"]
        try:
            yield client, service, headers, owner
        finally:
            service.close()
    app.dependency_overrides.clear()
