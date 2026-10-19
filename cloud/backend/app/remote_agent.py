"""Manually enabled outbound simulation executor. No listening network socket."""

import argparse
import fcntl
import hashlib
import json
import secrets
import signal
import tempfile
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.config import Settings, settings
from app.services import runtime
from app.services.execution_gate import execution_gate
from app.services.store import (
    TERMINAL,
    ServiceError,
    atomic_json,
    now,
    read_object,
)
from app.services.tasks import TaskService


class RemoteExecutor:
    def __init__(self, config: Settings, *, transport: httpx.BaseTransport | None = None):
        parsed = urlparse(config.REMOTE_SERVER_URL or "")
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or (
                parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
            )
        ):
            raise ValueError(
                "Executor URL requires HTTPS, or HTTP on loopback for local validation"
            )
        if (
            not config.REMOTE_EXECUTOR_KEY
            or len(config.REMOTE_EXECUTOR_KEY.get_secret_value()) < 32
        ):
            raise ValueError("Configure a separate executor credential before enabling the agent")
        self.config = config
        local_config = config.model_copy(
            update={
                "REMOTE_ENABLED": False,
                "MOTION_ENABLED": False,
                "REMOTE_EXECUTOR_KEY": None,
                "REMOTE_DEMO_PASSWORD": None,
                "HUAWEI_API_KEY": None,
                "HUAWEI_CHAT_COMPLETIONS_URL": None,
                "HUAWEI_MODEL": None,
            }
        )
        self.local = TaskService(local_config)
        session_path = config.APP_DATA_DIR / "executor-session.json"
        with (config.APP_DATA_DIR / ".session-init.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if not session_path.exists():
                atomic_json(session_path, {"session_id": str(uuid.uuid4())})
            self.session_id = str(uuid.UUID(read_object(session_path)["session_id"]))
        self.client = httpx.Client(
            base_url=config.REMOTE_SERVER_URL.rstrip("/") + config.API_V1_STR + "/executor/",
            headers={"Authorization": "Bearer " + config.REMOTE_EXECUTOR_KEY.get_secret_value()},
            timeout=3,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )
        self.stopping = False
        self.gate_fd: int | None = None

    def _post(self, path: str, body: dict) -> dict:
        response = self.client.post(path, json=body)
        response.raise_for_status()
        return response.json()

    def pending(self) -> str | None:
        candidates = [
            task
            for task in self.local.store.identifiers()
            if (self.local.store.directory(task) / "assignment.json").exists()
            and not (self.local.store.directory(task) / "delivered.json").exists()
        ]
        return (
            min(candidates, key=lambda task: self.local.store.metadata(task)["created_at_utc"])
            if candidates
            else None
        )

    def _credentials(self, task_id: str) -> dict:
        assignment = read_object(self.local.store.directory(task_id) / "assignment.json")
        return {"session_id": self.session_id, "lease_token": assignment["lease_token"]}

    def accept(self, assignment: dict) -> None:
        metadata = assignment["request"]
        task_id = metadata["task_id"]
        directory = self.local.store.directory(task_id)
        if directory.exists():
            original = read_object(directory / "assignment.json")
            if not secrets.compare_digest(original["lease_token"], assignment["lease_token"]):
                raise ValueError("Task ID was reused with different delivery credentials")
            # A durable receipt always suppresses a new launch, including after
            # response loss, process restart, and duplicate poll responses.
            return
        expected_route = runtime.select_simulation_route(self.config, self.config.REMOTE_ROUTE_ID)
        if (
            metadata.get("mode") != "simulation"
            or metadata.get("simulation_route") != expected_route
        ):
            raise ValueError("Only the matching preset simulation route may be executed")
        if not 0 < metadata.get("timeout_seconds", 0) <= self.config.TASK_TIMEOUT_SECONDS:
            raise ValueError("Task deadline exceeds the local execution limit")
        local_metadata = metadata | {"execution_backend": "local", "question": ""}
        temporary = Path(tempfile.mkdtemp(prefix=".accept-", dir=self.local.store.root))
        try:
            atomic_json(temporary / "request.json", local_metadata)
            atomic_json(temporary / "assignment.json", {"lease_token": assignment["lease_token"]})
            state = {
                "state": "PREPARING",
                "error": None,
                "stop_acknowledged": None,
                "cleanup_forced": False,
                "requires_operator_review": False,
                "photo_available": False,
                "video_available": False,
                "analysis_state": "NO_CAMERA_PHOTO",
                "updated_at_utc": now(),
            }
            atomic_json(temporary / "state.json", state)
            (temporary / "events.jsonl").write_text(
                json.dumps({"state": "PREPARING", "at_utc": state["updated_at_utc"], "error": None})
                + "\n"
            )
            temporary.replace(directory)
        finally:
            if temporary.exists():
                import shutil

                shutil.rmtree(temporary)
        atomic_json(directory / "launch-attempt.json", {"at_utc": now()})
        if assignment["cancel_requested"] or self.stopping:
            self.local.store.update(
                task_id,
                state="CANCELLED",
                error={"code": "CANCELLED", "message": "Cancelled before launch"},
            )
            return
        try:
            permission = self._post(f"tasks/{task_id}/start", self._credentials(task_id))
            if not permission["start"]:
                self.local.store.update(
                    task_id,
                    state="REJECTED",
                    error={"code": "START_REJECTED", "message": "Server did not grant execution"},
                )
                return
            if self.stopping:
                self.local.store.update(
                    task_id,
                    state="CANCELLED",
                    error={"code": "CANCELLED", "message": "Executor is shutting down"},
                )
                return
            self.local._launch(task_id, gate_fd=self.gate_fd)
        except httpx.HTTPError:
            # No subprocess was launched after an unconfirmed start response.
            # Reconnection delivers this failure; it never retries execution.
            self.local.store.update(
                task_id,
                state="FAILED",
                error={
                    "code": "START_UNCONFIRMED",
                    "message": "Start response was not confirmed; no execution retry",
                },
            )
        except OSError:
            self.local.store.update(
                task_id,
                state="FAILED",
                error={"code": "LAUNCH_FAILED", "message": "Could not launch local simulation"},
            )

    def relay(self, task_id: str) -> None:
        directory = self.local.store.directory(task_id)
        task = self.local.view(task_id)
        finished = task["state"] in TERMINAL and not task["worker_alive"]
        sequence_path = directory / "report-sequence.json"
        sequence = (read_object(sequence_path)["value"] if sequence_path.exists() else 0) + 1
        atomic_json(sequence_path, {"value": sequence})
        descriptor = None
        video = directory / "simulation.mp4"
        if finished and task["video_available"]:
            descriptor = {
                "size": video.stat().st_size,
                "sha256": hashlib.sha256(video.read_bytes()).hexdigest(),
            }
        state = (
            task["state"]
            if finished or task["state"] not in TERMINAL
            else "STOPPING"
            if task["cancel_requested"]
            else "NAVIGATING"
        )
        body = self._credentials(task_id) | {
            "sequence": sequence,
            "state": state,
            "execution_finished": finished,
            "simulation_progress": task.get("simulation_progress"),
            "simulation_summary": task.get("simulation_summary") if finished else None,
            "error": task.get("error") if finished else None,
            "requires_operator_review": task.get("requires_operator_review", False),
            "video": descriptor,
        }
        response = self._post(f"tasks/{task_id}/report", body)
        if response.get("cancel_requested") and not finished:
            self.local.cancel(task_id)
        if response.get("delivered"):
            atomic_json(directory / "delivered.json", {"at_utc": now()})
            return
        if not finished:
            return
        if descriptor:
            headers = {
                "X-Executor-Session": self.session_id,
                "X-Task-Token": self._credentials(task_id)["lease_token"],
            }
            with video.open("rb") as source:
                uploaded = self.client.post(
                    f"tasks/{task_id}/video", headers=headers, content=source, timeout=15
                )
            uploaded.raise_for_status()
            if uploaded.json() != descriptor:
                raise ValueError("Server did not confirm the complete recording checksum")
        response = self._post(f"tasks/{task_id}/complete", self._credentials(task_id))
        if response.get("delivered"):
            atomic_json(directory / "delivered.json", {"at_utc": now()})

    def cycle(self) -> None:
        current = self.pending()
        body = {
            "session_id": self.session_id,
            "device_id": self.config.REMOTE_DEVICE_ID,
            "configured": runtime.simulation_ready(self.local.settings)
            and self.local.settings.SIM_RECORD_VIDEO,
            "accepting": not self.stopping and not (current is None and self.local.store.active()),
            "current_task_id": current,
        }
        response = self._post("poll", body)
        assignment = response.get("assignment")
        if assignment:
            self.accept(assignment)
            current = assignment["request"]["task_id"]
            if assignment["cancel_requested"]:
                self.local.cancel(current)
        if current:
            self.relay(current)

    def stop(self, signum=None, frame=None) -> None:
        self.stopping = True

    def shutdown(self, delivery_seconds: float = 6) -> None:
        if self.client.is_closed:
            return
        self.stopping = True
        self.local.close()
        deadline = time.monotonic() + delivery_seconds
        try:
            while self.pending() and time.monotonic() < deadline:
                try:
                    self.cycle()
                except httpx.HTTPError, ValueError, ServiceError:
                    time.sleep(0.2)
            try:
                self._post(
                    "disconnect",
                    {
                        "session_id": self.session_id,
                        "device_id": self.config.REMOTE_DEVICE_ID,
                        "configured": False,
                        "accepting": False,
                        "current_task_id": self.pending(),
                    },
                )
            except httpx.HTTPError:
                pass
        finally:
            self.client.close()

    def run(self) -> None:
        last_error = None
        with execution_gate(self.config.EXECUTION_LOCK_PATH, remote=True) as gate_fd:
            self.gate_fd = gate_fd
            try:
                print(
                    "Remote simulation executor enabled; Ctrl+C cancels the current task and closes admission.",
                    flush=True,
                )
                while not self.stopping:
                    try:
                        self.cycle()
                        if last_error:
                            print(
                                "Executor connection restored; reconciling original task.",
                                flush=True,
                            )
                        last_error = None
                    except (httpx.HTTPError, ValueError, ServiceError) as error:
                        code = type(error).__name__
                        if code != last_error:
                            print(
                                f"Executor connection/report unavailable ({code}); local simulation continues, no task retry.",
                                flush=True,
                            )
                        last_error = code
                    time.sleep(self.config.REMOTE_POLL_SECONDS)
            finally:
                self.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description="Manually enable the outbound simulation executor")
    parser.add_argument("--enable-remote", action="store_true")
    args = parser.parse_args()
    if not args.enable_remote:
        parser.error("Remote execution is frozen by default; pass --enable-remote explicitly")
    executor = RemoteExecutor(settings)
    signal.signal(signal.SIGINT, executor.stop)
    signal.signal(signal.SIGTERM, executor.stop)
    executor.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
