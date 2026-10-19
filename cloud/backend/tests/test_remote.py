"""Real ASGI protocol + existing subprocess executor, with controllable network faults."""

import hashlib
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import SecretStr

from app.api.routes.tasks import get_service
from app.main import app
from app.remote_agent import RemoteExecutor
from app.services.execution_gate import execution_gate
from app.services.remote import RemoteTaskService
from app.services.store import ServiceError, atomic_json, read_object

PREFIX = "/api/v1"


class Network(httpx.BaseTransport):
    def __init__(self, client):
        self.client = client
        self.offline = False
        self.drop_once = None

    def handle_request(self, request):
        if self.offline:
            raise httpx.ConnectError("Injected network outage", request=request)
        response = self.client.request(
            request.method,
            request.url.raw_path.decode(),
            headers=dict(request.headers),
            content=request.read(),
        )
        if self.drop_once and request.url.path.endswith(self.drop_once):
            self.drop_once = None
            raise httpx.ReadError("Injected lost acknowledgement", request=request)
        return httpx.Response(
            response.status_code,
            headers=response.headers,
            content=response.content,
            request=request,
        )


@pytest.fixture
def remote(api, tmp_path):
    client, local, headers, owner = api
    runner = local.settings.SIM_SOURCE / "mujoco_sim/run.py"
    code = runner.read_text().replace(
        'b"synthetic-video-fixture"', 'bytes([0,0,0,24]) + b"ftypmp42synthetic-video-fixture"'
    )
    code = code.replace(
        "time.sleep(20 if a.goal_x == 2 else 0.3)", "time.sleep(3 if a.steps == 3 else 0.3)"
    )
    code = code.replace(
        "a, _ = p.parse_known_args()",
        'a, _ = p.parse_known_args()\nwith Path(a.log).with_suffix(".starts").open("a") as starts: starts.write("started\\n")',
    )
    runner.write_text(code)
    key = SecretStr("executor-test-" + "x" * 40)
    server_config = local.settings.model_copy(
        update={
            "APP_DATA_DIR": tmp_path / "server",
            "REMOTE_ENABLED": True,
            "REMOTE_EXECUTOR_KEY": key,
            "SIM_SOURCE": tmp_path / "absent-server-source",
            "SIM_PYTHON": None,
            "SIM_HIMLOCO_POLICY": None,
            "SIM_NAVIGATION_POLICY": None,
        }
    )
    server = RemoteTaskService(server_config)
    app.dependency_overrides[get_service] = lambda: server
    config = local.settings.model_copy(
        update={
            "APP_DATA_DIR": tmp_path / "executor",
            "REMOTE_EXECUTOR_KEY": key,
            "REMOTE_SERVER_URL": "http://127.0.0.1:8010",
        }
    )
    network = Network(client)
    agent = RemoteExecutor(config, transport=network)
    with execution_gate(config.EXECUTION_LOCK_PATH, remote=True) as descriptor:
        agent.gate_fd = descriptor
        try:
            yield client, server, agent, network, headers, owner, local
        finally:
            network.offline = False
            network.drop_once = None
            agent.shutdown(delivery_seconds=0.5)


def create(client, headers):
    response = client.post(
        PREFIX + "/tasks",
        headers=headers,
        json={
            "mode": "simulation",
            "simulation_route_id": "checkpoints-simple",
        },
    )
    assert response.status_code == 202, response.text
    return response.json()["task_id"]


def finish(agent, server, task_id, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        agent.cycle()
        value = server.view(task_id)
        if not value["remote_pending"]:
            return value
        time.sleep(0.04)
    raise AssertionError("Remote result did not finish")


def poll_body(agent):
    return {
        "session_id": agent.session_id,
        "device_id": agent.config.REMOTE_DEVICE_ID,
        "configured": True,
        "accepting": True,
        "current_task_id": None,
    }


def test_disabled_by_default_and_separate_executor_auth(api, remote):
    client, server, agent, network, headers, owner, local = remote
    assert (
        client.post(PREFIX + "/executor/poll", json=poll_body(agent), headers=headers).status_code
        == 401
    )
    assert client.post(PREFIX + "/executor/poll", json=poll_body(agent)).status_code == 401
    app.dependency_overrides[get_service] = lambda: local
    assert client.post(PREFIX + "/executor/poll", json=poll_body(agent)).status_code == 404
    app.dependency_overrides[get_service] = lambda: server


def test_offline_has_no_queue_and_remote_server_needs_no_simulation_assets(remote):
    client, server, agent, network, headers, owner, local = remote
    response = client.post(
        PREFIX + "/tasks",
        headers=headers,
        json={"mode": "simulation", "simulation_route_id": "checkpoints-simple"},
    )
    assert response.status_code == 503
    assert server.store.identifiers() == []
    agent.cycle()
    assert server.capabilities()["simulation_configured"] is True
    assert local.capabilities()["local_suspended"] is True
    response = local.capabilities()
    assert response["simulation_configured"] is False
    with pytest.raises(ServiceError) as blocked:
        local.create("a", "simulation", "", owner)
    assert blocked.value.code == "EXECUTION_IN_USE"
    task_id = create(client, headers)
    finished = finish(agent, server, task_id)
    assert finished["state"] == "SUCCEEDED"
    assert finished["simulation_summary"]["reached_indices"] == [0, 1, 2]
    assert finished["photo_available"] is False
    assert server.settings.SIM_PYTHON is None
    assert not server.settings.SIM_SOURCE.exists()
    server_video = server.store.directory(task_id) / "simulation.mp4"
    executor_video = agent.local.store.directory(task_id) / "simulation.mp4"
    assert server_video != executor_video
    assert server_video.read_bytes() == executor_video.read_bytes()
    assert client.get(finished["video_url"], headers=headers).content == server_video.read_bytes()


def test_duplicate_poll_and_lost_complete_ack_never_restart_execution(remote):
    client, server, agent, network, headers, owner, local = remote
    agent.cycle()
    task_id = create(client, headers)
    assignments = [agent._post("poll", poll_body(agent))["assignment"] for _ in range(3)]
    assert assignments[0] == assignments[1] == assignments[2]
    network.drop_once = "/complete"
    deadline = time.monotonic() + 5
    lost = False
    while time.monotonic() < deadline:
        try:
            agent.cycle()
        except httpx.ReadError:
            lost = True
        if lost and not agent.pending():
            break
        time.sleep(0.03)
    assert lost
    assert not agent.pending()
    assert server.view(task_id)["state"] == "SUCCEEDED"
    assert (
        agent.local.store.directory(task_id) / "simulation.starts"
    ).read_text().splitlines() == ["started"]


def test_lost_start_ack_reports_failure_without_launch_or_retry(remote):
    client, server, agent, network, headers, owner, local = remote
    agent.cycle()
    task_id = create(client, headers)
    network.drop_once = "/start"
    agent.cycle()
    task = finish(agent, server, task_id)
    assert task["state"] == "FAILED"
    assert task["error"]["code"] == "START_UNCONFIRMED"
    directory = agent.local.store.directory(task_id)
    assert not (directory / "process.json").exists()
    assert not (directory / "worker-starts.jsonl").exists()
    for _ in range(3):
        agent.cycle()
    assert not (directory / "process.json").exists()


def test_shutdown_cancels_unclaimed_assignment_and_closes_admission(remote):
    client, server, agent, network, headers, owner, local = remote
    agent.cycle()
    task_id = create(client, headers)
    agent.shutdown(delivery_seconds=0)
    task = server.view(task_id)
    assert task["state"] == "CANCELLED" and not task["remote_pending"]
    assert server.capabilities()["remote"]["online"] is False


def test_task_credentials_and_report_order_cannot_be_bypassed(remote):
    client, server, agent, network, headers, owner, local = remote
    task_id, credentials = claimed(remote)
    with pytest.raises(httpx.HTTPStatusError) as rejected:
        agent._post(f"tasks/{task_id}/start", credentials | {"lease_token": "字" * 40})
    assert rejected.value.response.status_code == 403
    for sequence, state in [(2, "NAVIGATING"), (1, "PREPARING"), (3, "PREPARING")]:
        agent._post(
            f"tasks/{task_id}/report",
            credentials
            | {
                "sequence": sequence,
                "state": state,
                "execution_finished": False,
            },
        )
        assert server.view(task_id)["state"] == "NAVIGATING"
    agent._post(
        f"tasks/{task_id}/report",
        credentials
        | {
            "sequence": 4,
            "state": "FAILED",
            "execution_finished": True,
            "requires_operator_review": True,
        },
    )
    agent._post(f"tasks/{task_id}/complete", credentials)
    assert server.view(task_id)["requires_operator_review"] is True
    assert server.store.active() == [task_id]


def test_disconnect_continues_locally_and_reconnect_delivers_original_result(remote):
    client, server, agent, network, headers, owner, local = remote
    agent.cycle()
    task_id = create(client, headers)
    agent.cycle()
    network.offline = True
    record = read_object(server.executor_path)
    atomic_json(
        server.executor_path,
        record | {"last_seen_utc": (datetime.now(UTC) - timedelta(seconds=30)).isoformat()},
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        task = agent.local.view(task_id)
        if task["state"] == "SUCCEEDED" and not task["worker_alive"]:
            break
        time.sleep(0.03)
    assert task["state"] == "SUCCEEDED"
    cloud = server.view(task_id)
    assert cloud["executor_online"] is False
    assert cloud["remote_pending"] is True and cloud["state"] not in {"FAILED", "CANCELLED"}
    with pytest.raises(httpx.ConnectError):
        agent.cycle()
    network.offline = False
    assert finish(agent, server, task_id)["state"] == "SUCCEEDED"
    assert (
        agent.local.store.directory(task_id) / "simulation.starts"
    ).read_text().splitlines() == ["started"]


def test_cancel_waits_for_execution_confirmation(remote):
    client, server, agent, network, headers, owner, local = remote
    agent.local.settings = agent.local.settings.model_copy(update={"SIM_STEPS": 3})
    agent.cycle()
    task_id = create(client, headers)
    agent.cycle()
    response = client.post(f"{PREFIX}/tasks/{task_id}/cancel", headers=headers)
    assert response.json()["cancel_requested"] is True
    assert server.view(task_id)["state"] != "CANCELLED"
    task = finish(agent, server, task_id)
    assert task["state"] == "CANCELLED" and not task["video_available"]


def test_shutdown_cancels_then_preserves_undelivered_result_offline(remote):
    client, server, agent, network, headers, owner, local = remote
    agent.local.settings = agent.local.settings.model_copy(update={"SIM_STEPS": 3})
    agent.cycle()
    task_id = create(client, headers)
    agent.cycle()
    network.offline = True
    agent.shutdown(delivery_seconds=0.1)
    task = agent.local.view(task_id)
    assert task["state"] == "CANCELLED" and task["worker_alive"] is False
    assert agent.pending() == task_id
    # Re-open only the HTTP client/session. Durable receipt prevents new launch.
    restored = RemoteExecutor(agent.config, transport=network)
    restored.gate_fd = agent.gate_fd
    network.offline = False
    try:
        assert finish(restored, server, task_id)["state"] == "CANCELLED"
        assert (restored.local.store.directory(task_id) / "launch-attempt.json").exists()
    finally:
        restored.shutdown(delivery_seconds=0.1)


def test_competing_submissions_and_executor_sessions_are_rejected(remote):
    client, server, agent, network, headers, owner, local = remote
    agent.cycle()

    def submit(_):
        return client.post(
            PREFIX + "/tasks",
            headers=headers,
            json={"mode": "simulation", "simulation_route_id": "checkpoints-simple"},
        ).status_code

    with ThreadPoolExecutor(max_workers=6) as pool:
        statuses = list(pool.map(submit, range(6)))
    assert statuses.count(202) == 1 and statuses.count(409) == 5
    with pytest.raises(httpx.HTTPStatusError) as conflict:
        agent._post("poll", poll_body(agent) | {"session_id": str(uuid.uuid4())})
    assert conflict.value.response.status_code == 409
    task_id = server.store.identifiers()[0]
    assert finish(agent, server, task_id)["state"] == "SUCCEEDED"


def claimed(remote):
    client, server, agent, network, headers, owner, local = remote
    agent.cycle()
    task_id = create(client, headers)
    assignment = agent._post("poll", poll_body(agent))["assignment"]
    credentials = {"session_id": agent.session_id, "lease_token": assignment["lease_token"]}
    assert agent._post(f"tasks/{task_id}/start", credentials)["start"]
    return task_id, credentials


def test_incomplete_checkpoints_and_missing_video_cannot_publish_success(remote):
    client, server, agent, network, headers, owner, local = remote
    task_id, credentials = claimed(remote)
    result = credentials | {
        "sequence": 1,
        "state": "SUCCEEDED",
        "execution_finished": True,
        "simulation_summary": {
            "goal_reached": True,
            "collision": False,
            "fallen": False,
            "waypoints_total": 3,
            "waypoints_reached": 2,
            "reached_indices": [0, 1],
        },
    }
    with pytest.raises(httpx.HTTPStatusError) as rejected:
        agent._post(f"tasks/{task_id}/report", result)
    assert rejected.value.response.status_code == 422
    assert server.view(task_id)["state"] != "SUCCEEDED"


def test_video_upload_is_bounded_verified_and_idempotent(remote):
    client, server, agent, network, headers, owner, local = remote
    task_id, credentials = claimed(remote)
    video = bytes([0, 0, 0, 24]) + b"ftypmp42synthetic-test-video"
    descriptor = {"size": len(video), "sha256": hashlib.sha256(video).hexdigest()}
    result = credentials | {
        "sequence": 1,
        "state": "FAILED",
        "execution_finished": True,
        "video": descriptor,
        "error": {"code": "TEST_FAILURE", "message": "Synthetic failed task"},
    }
    agent._post(f"tasks/{task_id}/report", result)
    assert server.view(task_id)["remote_phase"] == "UPLOADING"
    with pytest.raises(httpx.HTTPStatusError):
        agent._post(f"tasks/{task_id}/complete", credentials)
    upload_headers = {
        "X-Executor-Session": agent.session_id,
        "X-Task-Token": credentials["lease_token"],
    }
    assert (
        agent.client.post(
            f"tasks/{task_id}/video", headers=upload_headers, content=video + b"extra"
        ).status_code
        == 413
    )
    assert (
        agent.client.post(
            f"tasks/{task_id}/video", headers=upload_headers, content=video[:-1] + b"X"
        ).status_code
        == 422
    )
    assert not list(server.store.directory(task_id).glob(".video-*"))
    assert (
        agent.client.post(f"tasks/{task_id}/video", headers=upload_headers, content=video).json()
        == descriptor
    )
    agent._post(f"tasks/{task_id}/complete", credentials)
    assert agent._post(f"tasks/{task_id}/complete", credentials)["delivered"]
    agent._post(
        f"tasks/{task_id}/report",
        credentials | {"sequence": 999, "state": "NAVIGATING", "execution_finished": False},
    )
    assert server.view(task_id)["state"] == "FAILED"


def test_unclaimed_expired_task_is_not_executed_after_reconnect(remote):
    client, server, agent, network, headers, owner, local = remote
    agent.cycle()
    task_id = create(client, headers)
    path = server.store.directory(task_id) / "request.json"
    atomic_json(
        path,
        read_object(path)
        | {"created_at_utc": (datetime.now(UTC) - timedelta(seconds=30)).isoformat()},
    )
    agent.cycle()
    task = server.view(task_id)
    assert task["state"] == "REJECTED" and not task["remote_pending"]
    assert not agent.local.store.directory(task_id).exists()
