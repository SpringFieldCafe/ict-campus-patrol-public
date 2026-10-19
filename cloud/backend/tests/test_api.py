import hashlib
import json
import os
import signal
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import SecretStr

from app.services import huawei, runtime
from app.services.store import ServiceError, atomic_json, identity, now
from app.services.tasks import TaskService

PREFIX = "/api/v1"


def wait_for_task(client, headers, task_id, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"{PREFIX}/tasks/{task_id}", headers=headers)
        assert response.status_code == 200, response.text
        value = response.json()
        if (
            value["state"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT", "REJECTED"}
            and not value["worker_alive"]
        ):
            return value
        time.sleep(0.05)
    raise AssertionError("Substitute task did not complete")


def successful_photo(service, owner):
    task_id = "task-" + uuid.uuid4().hex
    directory = service.store.directory(task_id)
    directory.mkdir()
    atomic_json(
        directory / "request.json",
        {
            "task_id": task_id,
            "point_id": "a",
            "point": {"id": "a"},
            "point_reference": "initial_pose",
            "mode": "motion",
            "question": "test question",
            "owner_id": owner,
            "created_at_utc": now(),
            "timeout_seconds": 90,
        },
    )
    service.store.update(
        task_id,
        state="SUCCEEDED",
        error=None,
        stop_acknowledged=True,
        cleanup_forced=False,
        requires_operator_review=False,
        photo_available=True,
        video_available=False,
        analysis_state="NOT_CONFIGURED",
    )
    target = runtime.runtime_directory(service.settings, task_id)
    run = target / "run"
    run.mkdir(parents=True)
    # Artificial PNG signature and bytes are sufficient to test the evidence contract.
    image = b"\x89PNG\r\n\x1a\nsynthetic-unit-test-image"
    (run / "observation.png").write_bytes(image)
    digest = hashlib.sha256(image).hexdigest()
    evidence = {
        "task_id": task_id,
        "state": "PHOTO_READY",
        "mode": "motion",
        "stop_acknowledged": True,
        "source": "unitree",
        "image": "observation.png",
        "metadata": "observation.json",
        "image_sha256": digest,
        "width": 1,
        "height": 1,
        "captured_at_utc": now(),
    }
    atomic_json(run / "observation-result.json", evidence)
    atomic_json(run / "observation.json", evidence | {"mode": "camera"})
    atomic_json(
        target / "task.json",
        {"task_id": task_id, "state": "SUCCEEDED", "result": "run/observation-result.json"},
    )
    return task_id, target, run


def test_health_auth_cors_and_openapi(api):
    client, service, headers, owner = api
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get(PREFIX + "/points").status_code == 401
    assert client.get(PREFIX + "/points", headers=headers).json()["reference"] == "initial_pose"
    response = client.options(
        PREFIX + "/tasks",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert client.get(PREFIX + "/openapi.json").json()["paths"][PREFIX + "/tasks"]["post"][
        "responses"
    ]["202"]
    assert (
        client.get(PREFIX + "/capabilities", headers=headers).json()["huawei_configured"] is False
    )


def test_submit_busy_complete_video_and_persistence(api):
    client, service, headers, owner = api
    started = time.monotonic()
    response = client.post(
        PREFIX + "/tasks",
        headers=headers,
        json={"point_id": "a", "mode": "simulation", "question": "现场有什么？"},
    )
    assert response.status_code == 202, response.text
    assert time.monotonic() - started < 2
    task_id = response.json()["task_id"]
    busy = client.post(
        PREFIX + "/tasks", headers=headers, json={"point_id": "a", "mode": "simulation"}
    )
    assert busy.status_code == 409 and busy.json()["detail"]["code"] == "BUSY"
    value = wait_for_task(client, headers, task_id)
    assert value["state"] == "SUCCEEDED", value
    assert value["analysis_state"] == "NO_CAMERA_PHOTO" and value["photo_url"] is None
    assert client.get(value["video_url"], headers=headers).content == b"synthetic-video-fixture"
    assert client.get(f"{PREFIX}/tasks/{task_id}/photo", headers=headers).status_code == 409
    assert (
        client.get(f"{PREFIX}/tasks/{task_id}/events", headers=headers).json()["data"][-1]["state"]
        == "SUCCEEDED"
    )
    assert client.get(PREFIX + "/tasks", headers=headers).json()["count"] == 1
    restarted = TaskService(service.settings)
    assert restarted.view(task_id)["state"] == "SUCCEEDED"


def test_concurrent_submissions_accept_only_one(api):
    client, service, headers, owner = api

    def submit():
        try:
            return service.create("b", "simulation", "", owner)["task_id"]
        except ServiceError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(lambda _: submit(), range(2)))
    assert result.count("BUSY") == 1
    task_id = next(value for value in result if value != "BUSY")
    service.cancel(task_id)
    assert wait_for_task(client, headers, task_id)["state"] == "CANCELLED"


def test_cancel_timeout_and_non_goal_are_not_success(api):
    client, service, headers, owner = api
    task = service.create("b", "simulation", "", owner)
    response = client.post(f"{PREFIX}/tasks/{task['task_id']}/cancel", headers=headers)
    assert response.json()["cancel_requested"] is True
    assert wait_for_task(client, headers, task["task_id"])["state"] == "CANCELLED"
    service.settings = service.settings.model_copy(update={"TASK_TIMEOUT_SECONDS": 0.2})
    task = service.create("b", "simulation", "", owner)
    assert wait_for_task(client, headers, task["task_id"])["state"] == "TIMED_OUT"
    service.settings = service.settings.model_copy(
        update={"TASK_TIMEOUT_SECONDS": 90, "SIM_STEPS": 1}
    )
    task = service.create("a", "simulation", "", owner)
    result = wait_for_task(client, headers, task["task_id"])
    assert result["state"] == "FAILED" and result["error"]["code"] == "SIMULATION_GOAL_NOT_REACHED"


def test_motion_unknown_point_and_arbitrary_commands_rejected(api):
    client, service, headers, owner = api
    response = client.post(
        PREFIX + "/tasks", headers=headers, json={"point_id": "a", "mode": "motion"}
    )
    assert response.status_code == 409 and response.json()["detail"]["code"] == "MOTION_DISABLED"
    assert (
        client.post(
            PREFIX + "/tasks", headers=headers, json={"point_id": "missing", "mode": "simulation"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            PREFIX + "/tasks",
            headers=headers,
            json={"point_id": "a", "mode": "simulation", "command": "anything"},
        ).status_code
        == 422
    )
    assert not service.store.identifiers()


def test_photo_handoff_hash_and_path_validation(api):
    client, service, headers, owner = api
    task_id, target, run = successful_photo(service, owner)
    url = f"{PREFIX}/tasks/{task_id}/photo"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=headers).status_code == 200
    record = json.loads((target / "task.json").read_text())
    atomic_json(target / "task.json", record | {"state": "TIMED_OUT"})
    assert client.get(url, headers=headers).status_code == 409
    atomic_json(target / "task.json", record)
    evidence = json.loads((run / "observation-result.json").read_text())
    atomic_json(run / "observation-result.json", evidence | {"task_id": "wrong-task"})
    assert client.get(url, headers=headers).status_code == 409
    atomic_json(run / "observation-result.json", evidence | {"image": "../../../../secret.png"})
    assert client.get(url, headers=headers).status_code == 409
    atomic_json(run / "observation-result.json", evidence)
    (run / "observation.png").write_bytes(b"altered")
    assert client.get(url, headers=headers).status_code == 409


def test_ownership_and_missing_huawei(api):
    client, service, headers, owner = api
    task_id, _, _ = successful_photo(service, owner)
    with pytest.raises(ServiceError) as error:
        service.owned(task_id, "another-user", False)
    assert error.value.status == 404
    response = client.post(
        f"{PREFIX}/tasks/{task_id}/analysis", headers=headers, json={"question": "图中有什么？"}
    )
    assert (
        response.status_code == 503 and response.json()["detail"]["code"] == "HUAWEI_NOT_CONFIGURED"
    )
    assert service.view(task_id)["state"] == "SUCCEEDED"


def test_dead_worker_requires_review_and_does_not_retry(api):
    client, service, headers, owner = api
    task_id, _, _ = successful_photo(service, owner)
    service.store.update(task_id, state="NAVIGATING")
    atomic_json(
        service.store.directory(task_id) / "process.json", {"pid": 99999999, "start_ticks": "1"}
    )
    result = service.view(task_id)
    assert result["state"] == "FAILED" and result["requires_operator_review"]
    with pytest.raises(ServiceError) as error:
        service.create("a", "simulation", "", owner)
    assert error.value.code == "BUSY"


def test_huawei_payload_success_timeout_and_errors(api):
    client, service, headers, owner = api
    configured = service.settings.model_copy(
        update={
            "HUAWEI_CHAT_COMPLETIONS_URL": "https://example.invalid/v1/chat/completions",
            "HUAWEI_MODEL": "synthetic-vision-model",
            "HUAWEI_API_KEY": SecretStr("synthetic-key"),
        }
    )

    def success(request):
        assert request.headers["Authorization"] == "Bearer synthetic-key"
        body = json.loads(request.content)
        assert body["stream"] is False and body["messages"][0]["content"][1]["image_url"][
            "url"
        ].startswith("data:image/png;base64,")
        return httpx.Response(
            200, json={"id": "synthetic-request", "choices": [{"message": {"content": "测试回答"}}]}
        )

    answer = huawei.ask_image(
        configured, b"image", "image/png", "question", httpx.MockTransport(success)
    )
    assert answer["answer"] == "测试回答"

    def timeout(request):
        raise httpx.ReadTimeout("synthetic timeout")

    with pytest.raises(ServiceError) as error:
        huawei.ask_image(
            configured, b"image", "image/png", "question", httpx.MockTransport(timeout)
        )
    assert error.value.code == "MODEL_TIMEOUT"
    with pytest.raises(ServiceError) as error:
        huawei.ask_image(
            configured,
            b"image",
            "image/png",
            "question",
            httpx.MockTransport(lambda _: httpx.Response(429)),
        )
    assert error.value.code == "MODEL_REQUEST_FAILED"


def test_analysis_failure_preserves_robot_success(api, monkeypatch):
    client, service, headers, owner = api
    task_id, _, _ = successful_photo(service, owner)
    configured = service.settings.model_copy(
        update={
            "HUAWEI_CHAT_COMPLETIONS_URL": "https://example.invalid/v1/chat/completions",
            "HUAWEI_MODEL": "synthetic",
            "HUAWEI_API_KEY": SecretStr("synthetic-key"),
        }
    )

    def fail(*args, **kwargs):
        raise ServiceError(504, "MODEL_TIMEOUT", "Synthetic timeout")

    monkeypatch.setattr(huawei, "ask_image", fail)
    huawei.analyze(configured, service.store, task_id, "question")
    result = service.view(task_id)
    assert result["state"] == "SUCCEEDED" and result["analysis_state"] == "FAILED"


@pytest.mark.parametrize("exit_status", [0, 2])
def test_motion_worker_uses_existing_cli_contract_without_sdk(
    api, monkeypatch, tmp_path, exit_status
):
    """Exercise the real adapter with a substitute CLI; never enable a real robot."""
    from app import worker

    client, service, headers, owner = api
    task_id, target, run = successful_photo(service, owner)
    service.store.update(task_id, state="PREPARING", photo_available=False)
    cli_root = tmp_path / "substitute-cli"
    cli_root.mkdir()
    (cli_root / "cli.py").write_text(
        f"import sys,time\ntime.sleep(0.2)\nraise SystemExit({exit_status})\n"
    )
    local = service.settings.model_copy(update={"MOTION_ENABLED": True})
    monkeypatch.setattr(runtime, "RUNTIME", cli_root)
    monkeypatch.setattr(runtime, "runtime_directory", lambda config, identifier: target)
    monkeypatch.setattr(worker, "settings", local)
    monkeypatch.setattr("sys.argv", ["worker", "execute", task_id])
    previous = {value: signal.getsignal(value) for value in (signal.SIGTERM, signal.SIGINT)}
    try:
        assert worker.main() == (0 if exit_status == 0 else 1)
    finally:
        for value, handler in previous.items():
            signal.signal(value, handler)
    result = service.store.state(task_id)
    assert result["state"] == ("SUCCEEDED" if exit_status == 0 else "FAILED")
    assert result["photo_available"] is (exit_status == 0)
    if exit_status == 0:
        assert result["analysis_state"] == "NOT_CONFIGURED"


def test_analysis_launch_does_not_reuse_exited_robot_worker_identity(api, monkeypatch):
    client, service, headers, owner = api
    task_id, _, _ = successful_photo(service, owner)
    directory = service.store.directory(task_id)
    metadata = service.store.metadata(task_id)
    metadata["created_at_utc"] = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    atomic_json(directory / "request.json", metadata)
    atomic_json(directory / "process.json", {"pid": 99999999, "start_ticks": "1"})
    service.settings = service.settings.model_copy(
        update={
            "HUAWEI_CHAT_COMPLETIONS_URL": "https://example.invalid/v1/chat/completions",
            "HUAWEI_MODEL": "synthetic",
            "HUAWEI_API_KEY": SecretStr("synthetic-key"),
        }
    )

    def during_launch(identifier, action):
        assert identifier == task_id and action == "analyze"
        # A concurrent GET must not mark the newly starting analysis as lost.
        assert service.view(task_id)["analysis_state"] == "RUNNING"

    monkeypatch.setattr(service, "_launch", during_launch)
    response = client.post(
        f"{PREFIX}/tasks/{task_id}/analysis", headers=headers, json={"question": "test question"}
    )
    assert response.status_code == 202, response.text
    assert response.json()["state"] == "SUCCEEDED"
    service.store.update(
        task_id, analysis_state="FAILED", analysis_error={"code": "SYNTHETIC_TEST_END"}
    )


def test_live_delivery_worker_blocks_duplicate_analysis(api):
    client, service, headers, owner = api
    task_id, _, _ = successful_photo(service, owner)
    atomic_json(
        service.store.directory(task_id) / "process.json",
        {"pid": os.getpid(), "start_ticks": identity(os.getpid())},
    )
    service.settings = service.settings.model_copy(
        update={
            "HUAWEI_CHAT_COMPLETIONS_URL": "https://example.invalid/v1/chat/completions",
            "HUAWEI_MODEL": "synthetic",
            "HUAWEI_API_KEY": SecretStr("synthetic-key"),
        }
    )
    with pytest.raises(ServiceError) as error:
        service.analyze(task_id, "question")
    assert error.value.code == "BUSY"


def test_outer_motion_deadline_is_not_reported_as_manual_cancel(api, monkeypatch, tmp_path):
    from app import worker

    client, service, headers, owner = api
    task_id, target, _ = successful_photo(service, owner)
    directory = service.store.directory(task_id)
    metadata = service.store.metadata(task_id)
    atomic_json(directory / "request.json", metadata | {"timeout_seconds": 0.05})
    service.store.update(task_id, state="PREPARING", photo_available=False)
    cli_root = tmp_path / "deadline-cli"
    cli_root.mkdir()
    (cli_root / "cli.py").write_text(
        "import json,time\nfrom pathlib import Path\n"
        f"path=Path({str(target / 'task.json')!r})\n"
        "time.sleep(0.4)\nvalue=json.loads(path.read_text())\n"
        "value.update(state='CANCELLED',error={'code':'CANCELLED'})\n"
        "path.write_text(json.dumps(value))\n"
    )
    monkeypatch.setattr(runtime, "RUNTIME", cli_root)
    monkeypatch.setattr(runtime, "runtime_directory", lambda config, identifier: target)
    monkeypatch.setattr(runtime, "cancel_motion", lambda config, identifier: None)
    monkeypatch.setattr(
        worker, "settings", service.settings.model_copy(update={"MOTION_ENABLED": True})
    )
    monkeypatch.setattr("sys.argv", ["worker", "execute", task_id])
    previous = {value: signal.getsignal(value) for value in (signal.SIGTERM, signal.SIGINT)}
    try:
        assert worker.main() == 0
    finally:
        for value, handler in previous.items():
            signal.signal(value, handler)
    state = service.store.state(task_id)
    assert state["state"] == "TIMED_OUT"
    assert state["error"]["code"] == "TASK_TIMEOUT" and not state["photo_available"]
