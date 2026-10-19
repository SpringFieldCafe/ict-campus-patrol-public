"""Task acceptance, single-task admission and public representations."""

import json
import os
import subprocess
import sys
import time
import uuid

from pydantic import SecretStr

from app.core.config import BACKEND_ROOT, Settings
from app.services import huawei, runtime
from app.services.execution_gate import execution_gate, local_suspended
from app.services.store import (
    TERMINAL,
    ServiceError,
    TaskStore,
    alive,
    atomic_json,
    identity,
    now,
    read_object,
)


class TaskService:
    execution_backend = "local"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = TaskStore(settings.APP_DATA_DIR)
        self.children: list[subprocess.Popen] = []

    def _environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        for key in type(self.settings).model_fields:
            value = getattr(self.settings, key)
            if value is None:
                environment.pop(key, None)
            elif isinstance(value, SecretStr):
                environment[key] = value.get_secret_value()
            elif isinstance(value, list):
                environment[key] = json.dumps(value)
            else:
                environment[key] = str(value)
        # Export a complete settings snapshot; do not refill deliberately cleared
        # values (including executor credentials) from a different dotenv file.
        environment["CAMPUS_ENV_FILE"] = "/dev/null"
        return environment

    def _launch(self, task_id: str, action: str = "execute", gate_fd: int | None = None) -> None:
        for process in self.children[:]:
            if process.poll() is not None:
                process.wait()
                self.children.remove(process)
        directory = self.store.directory(task_id)
        environment = self._environment()
        environment.pop("CAMPUS_EXECUTION_GATE_FD", None)
        if gate_fd is not None:
            environment["CAMPUS_EXECUTION_GATE_FD"] = str(gate_fd)
        with (directory / "api-worker.log").open("ab") as output:
            process = subprocess.Popen(
                [sys.executable, "-m", "app.worker", action, task_id],
                cwd=BACKEND_ROOT,
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                pass_fds=(gate_fd,) if gate_fd is not None else (),
            )
        self.children.append(process)
        atomic_json(
            directory / "process.json", {"pid": process.pid, "start_ticks": identity(process.pid)}
        )

    def capabilities(self) -> dict:
        suspended = local_suspended(self.settings.EXECUTION_LOCK_PATH)
        return {
            "simulation_configured": runtime.simulation_ready(self.settings) and not suspended,
            "simulation_camera_photo": False,
            "simulation_video": self.settings.SIM_RECORD_VIDEO,
            "motion_enabled": self.settings.MOTION_ENABLED and not suspended,
            "huawei_configured": self.settings.huawei_configured,
            "task_timeout_seconds": self.settings.TASK_TIMEOUT_SECONDS,
            "single_task": True,
            "queue_enabled": False,
            "automatic_retry": False,
            "simulation_routes": runtime.simulation_routes(self.settings),
            "execution_backend": "local",
            "local_suspended": suspended,
            "remote": None,
        }

    def _admission_gate(self):
        return execution_gate(self.settings.EXECUTION_LOCK_PATH)

    def _validate_execution(self, mode: str, point_id: str, route: dict | None) -> None:
        if mode == "motion":
            runtime.motion_command(self.settings, "task-" + "0" * 32, point_id)
            runtime.runtime_config(self.settings)
        elif not runtime.simulation_ready(self.settings):
            raise ServiceError(
                503,
                "SIMULATION_NOT_CONFIGURED",
                "Configure the existing MuJoCo environment and assets",
            )

    def owned(self, task_id: str, owner_id: str, superuser: bool = False) -> dict:
        metadata = self.store.metadata(task_id)
        if metadata["owner_id"] != owner_id and not superuser:
            raise ServiceError(404, "TASK_NOT_FOUND", "Task not found")
        return metadata

    def create(
        self,
        point_id: str | None,
        mode: str,
        question: str,
        owner_id: str,
        simulation_route_id: str | None = None,
    ) -> dict:
        route = None
        if simulation_route_id is not None:
            if mode != "simulation" or point_id is not None:
                raise ServiceError(
                    422, "INVALID_SIMULATION_ROUTE", "Choose a simulation route without a point"
                )
            route = runtime.select_simulation_route(self.settings, simulation_route_id)
            point_id = route["id"]
            final = route["waypoints"][-1]
            point = {
                "id": point_id,
                "description": route["description"],
                "goal_forward": final["x"],
                "goal_left": final["y"],
            }
        else:
            point = runtime.select_point(self.settings, point_id)
        self._validate_execution(mode, point_id, route)
        with self._admission_gate() as gate_fd, self.store.locked():
            self._validate_execution(mode, point_id, route)
            if self.store.active():
                raise ServiceError(
                    409, "BUSY", "Another task is active or requires operator review"
                )
            task_id = "task-" + uuid.uuid4().hex
            directory = self.store.directory(task_id)
            directory.mkdir(mode=0o700)
            atomic_json(
                directory / "request.json",
                {
                    "schema_version": 1,
                    "execution_backend": self.execution_backend,
                    "task_id": task_id,
                    "point_id": point_id,
                    "point": point,
                    "simulation_route": route,
                    "point_reference": "initial_pose",
                    "mode": mode,
                    "question": question,
                    "owner_id": owner_id,
                    "created_at_utc": now(),
                    "timeout_seconds": self.settings.TASK_TIMEOUT_SECONDS,
                },
            )
            self.store.update(
                task_id,
                state="PREPARING",
                error=None,
                stop_acknowledged=None,
                cleanup_forced=False,
                photo_available=False,
                video_available=False,
                analysis_state="NOT_REQUESTED",
                requires_operator_review=False,
            )
            try:
                self._launch(task_id, gate_fd=gate_fd)
            except OSError:
                self.store.update(
                    task_id,
                    state="FAILED",
                    error={"code": "LAUNCH_FAILED", "message": "Could not start task worker"},
                )
                raise ServiceError(503, "LAUNCH_FAILED", "Could not start task worker") from None
        return self.view(task_id)

    def view(self, task_id: str) -> dict:
        metadata = self.store.metadata(task_id)
        state = self.store.reconcile(task_id)
        directory = self.store.directory(task_id)
        process = (
            read_object(directory / "process.json") if (directory / "process.json").exists() else {}
        )
        prefix = f"{self.settings.API_V1_STR}/tasks/{task_id}"
        return (
            {
                key: metadata[key]
                for key in (
                    "task_id",
                    "point_id",
                    "point",
                    "point_reference",
                    "mode",
                    "question",
                    "created_at_utc",
                    "timeout_seconds",
                )
            }
            | state
            | {
                "simulation_route": metadata.get("simulation_route"),
                "execution_backend": metadata.get("execution_backend", "local"),
                "worker_alive": alive(process),
                "cancel_requested": (directory / "cancel-request.json").exists(),
                "photo_url": prefix + "/photo" if state.get("photo_available") else None,
                "video_url": prefix + "/video" if state.get("video_available") else None,
                "answer": huawei.read_answer(self.store, task_id),
            }
        )

    def list(self, owner_id: str, superuser: bool, offset: int, limit: int) -> dict:
        selected = []
        for task_id in self.store.identifiers():
            metadata = self.store.metadata(task_id)
            if metadata["owner_id"] == owner_id or superuser:
                selected.append(metadata)
        selected.sort(key=lambda value: value["created_at_utc"], reverse=True)
        return {
            "data": [self.view(value["task_id"]) for value in selected[offset : offset + limit]],
            "count": len(selected),
        }

    def cancel(self, task_id: str) -> dict:
        state = self.store.reconcile(task_id)
        if state["state"] in TERMINAL:
            return {"task_id": task_id, "state": state["state"], "cancel_requested": False}
        atomic_json(
            self.store.directory(task_id) / "cancel-request.json", {"requested_at_utc": now()}
        )
        return {"task_id": task_id, "state": state["state"], "cancel_requested": True}

    def analyze(self, task_id: str, question: str) -> dict:
        metadata = self.store.metadata(task_id)
        with self.store.locked():
            state = self.store.reconcile(task_id)
            if state["state"] != "SUCCEEDED" or metadata["mode"] != "motion":
                raise ServiceError(
                    409, "PHOTO_NOT_READY", "Analysis requires a successful camera task"
                )
            if not self.settings.huawei_configured:
                raise ServiceError(
                    503, "HUAWEI_NOT_CONFIGURED", "Configure a Huawei vision model locally"
                )
            if state.get("analysis_state") == "RUNNING" or self.store.active():
                raise ServiceError(409, "BUSY", "Another task or analysis is running")
            runtime.photo_evidence(self.settings, task_id)
            atomic_json(
                self.store.directory(task_id) / "analysis-request.json", {"question": question}
            )
            self.store.update(task_id, analysis_state="RUNNING", analysis_error=None)
            try:
                self._launch(task_id, "analyze")
            except OSError:
                self.store.update(
                    task_id, analysis_state="FAILED", analysis_error={"code": "LAUNCH_FAILED"}
                )
                raise ServiceError(
                    503, "LAUNCH_FAILED", "Could not start analysis worker"
                ) from None
        return self.view(task_id)

    def close(self) -> None:
        # Request cleanup through the existing controller, never signal a PID read from a file.
        pending = []
        for task_id in self.store.identifiers():
            state = self.store.reconcile(task_id)
            if state["state"] not in TERMINAL:
                self.cancel(task_id)
                pending.append(task_id)
        deadline = time.monotonic() + 25
        while pending and time.monotonic() < deadline:
            pending = [
                value for value in pending if self.store.reconcile(value)["state"] not in TERMINAL
            ]
            time.sleep(0.1)
        for process in self.children:
            if process.poll() is not None:
                process.wait()
