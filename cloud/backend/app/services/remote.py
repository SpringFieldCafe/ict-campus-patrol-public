"""Remote simulation coordinator; reuses task records, views and browser APIs.

Only a bounded, unstarted handoff can expire. Once execution is granted, network
loss holds admission until the same task's durable result is reconciled.
"""

import hashlib
import secrets
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings
from app.remote_schemas import DeliveryRequest, PollRequest, TaskReport
from app.services import runtime
from app.services.store import TERMINAL, ServiceError, TaskStore, atomic_json, now, read_object
from app.services.tasks import TaskService


def age(timestamp: str) -> float:
    return (datetime.now(UTC) - datetime.fromisoformat(timestamp)).total_seconds()


class RemoteTaskStore(TaskStore):
    def __init__(self, settings: Settings):
        super().__init__(settings.APP_DATA_DIR)
        self.settings = settings

    def reconcile(self, task_id: str) -> dict:
        with self.locked():
            state = self.state(task_id)
            if state["state"] in TERMINAL:
                return state
            delivery = read_object(self.directory(task_id) / "delivery.json")
            if not delivery["start_granted"]:
                cancelled = (self.directory(task_id) / "cancel-request.json").exists()
                expired = (
                    age(self.metadata(task_id)["created_at_utc"])
                    > self.settings.REMOTE_DISPATCH_SECONDS
                )
                if cancelled or expired:
                    return self.update(
                        task_id,
                        state="CANCELLED" if cancelled else "REJECTED",
                        remote_pending=False,
                        remote_phase="DELIVERED",
                        error={
                            "code": "CANCELLED_BEFORE_START" if cancelled else "DISPATCH_EXPIRED",
                            "message": "Task cancelled before execution"
                            if cancelled
                            else "Executor did not start in time; submit a new task manually",
                        },
                    )
            return state


class RemoteTaskService(TaskService):
    execution_backend = "remote"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = RemoteTaskStore(settings)
        self.children = []
        self.executor_path = settings.APP_DATA_DIR / "executor.json"

    def _admission_gate(self):
        # The server can be on a different machine; the agent owns the machine gate.
        return nullcontext(None)

    def executor(self) -> dict:
        record = read_object(self.executor_path) if self.executor_path.exists() else {}
        online = bool(
            record.get("connected")
            and record.get("last_seen_utc")
            and age(record["last_seen_utc"]) <= self.settings.REMOTE_OFFLINE_SECONDS
        )
        return {
            "online": online,
            "ready": online
            and record.get("configured", False)
            and record.get("accepting", False)
            and not record.get("current_task_id"),
            "configured": record.get("configured", False),
            "device_id": self.settings.REMOTE_DEVICE_ID,
            "last_seen_utc": record.get("last_seen_utc"),
        }

    def capabilities(self) -> dict:
        executor = self.executor()
        route = runtime.select_simulation_route(self.settings, self.settings.REMOTE_ROUTE_ID)
        return {
            "simulation_configured": executor["online"] and executor["configured"],
            "simulation_camera_photo": False,
            "simulation_video": True,
            "motion_enabled": False,
            "huawei_configured": False,
            "task_timeout_seconds": self.settings.TASK_TIMEOUT_SECONDS,
            "single_task": True,
            "queue_enabled": False,
            "automatic_retry": False,
            "simulation_routes": [route],
            "execution_backend": "remote",
            "local_suspended": False,
            "remote": executor,
        }

    def _validate_execution(self, mode: str, point_id: str, route: dict | None) -> None:
        if mode != "simulation" or not route or route["id"] != self.settings.REMOTE_ROUTE_ID:
            raise ServiceError(
                409,
                "REMOTE_SIMULATION_ONLY",
                "Remote demo only accepts its preset simulation route",
            )
        executor = self.executor()
        if not executor["online"]:
            raise ServiceError(503, "EXECUTOR_OFFLINE", "Executor is offline; tasks are not queued")
        if not executor["ready"]:
            raise ServiceError(
                409, "EXECUTOR_NOT_READY", "Executor is busy, recovering or not configured"
            )

    def _launch(self, task_id: str, action: str = "execute", gate_fd: int | None = None) -> None:
        if action != "execute":
            raise ServiceError(
                409, "REMOTE_SIMULATION_ONLY", "Remote demo does not analyze camera photos"
            )
        atomic_json(
            self.store.directory(task_id) / "delivery.json",
            {
                "lease_token": secrets.token_urlsafe(36),
                "session_id": None,
                "start_granted": False,
                "sequence": 0,
                "result": None,
                "video_verified": False,
            },
        )
        self.store.update(
            task_id, analysis_state="NO_CAMERA_PHOTO", remote_pending=True, remote_phase="WAITING"
        )

    def view(self, task_id: str) -> dict:
        value = super().view(task_id)
        value.update(worker_alive=False, executor_online=self.executor()["online"])
        return value

    def close(self) -> None:
        # Stopping/restarting this HTTP service is a network outage, not an operator
        # request to cancel the independently supervised simulation.
        pass

    def _session(self, session_id: str) -> dict:
        record = read_object(self.executor_path) if self.executor_path.exists() else {}
        if record.get("session_id") != session_id:
            raise ServiceError(409, "EXECUTOR_SESSION_CONFLICT", "Executor session does not match")
        return record

    def _touch(self, session_id: str) -> None:
        record = self._session(session_id)
        atomic_json(self.executor_path, record | {"last_seen_utc": now(), "connected": True})

    def poll(self, body: PollRequest) -> dict:
        session_id = str(body.session_id)
        with self.store.locked():
            if body.device_id != self.settings.REMOTE_DEVICE_ID:
                raise ServiceError(403, "EXECUTOR_DEVICE_MISMATCH", "Unknown executor device")
            active = self.store.active()
            previous = read_object(self.executor_path) if self.executor_path.exists() else {}
            if previous.get("session_id") not in (None, session_id):
                if self.executor()["online"] or active:
                    raise ServiceError(
                        409,
                        "EXECUTOR_SESSION_CONFLICT",
                        "Another executor session owns this service",
                    )
            if body.current_task_id:
                self.store.metadata(body.current_task_id)
                old = read_object(self.store.directory(body.current_task_id) / "delivery.json")
                if old["session_id"] != session_id:
                    raise ServiceError(
                        409, "EXECUTOR_TASK_MISMATCH", "Recovered task belongs to another session"
                    )
            if active and body.current_task_id and active[0] != body.current_task_id:
                raise ServiceError(
                    409, "EXECUTOR_TASK_MISMATCH", "Executor and server disagree on the active task"
                )
            atomic_json(
                self.executor_path,
                {
                    "session_id": session_id,
                    "last_seen_utc": now(),
                    "connected": True,
                    "configured": body.configured,
                    "accepting": body.accepting,
                    "current_task_id": body.current_task_id,
                },
            )
            task_id = body.current_task_id or (active[0] if active and body.accepting else None)
            assignment = None
            if task_id:
                delivery_path = self.store.directory(task_id) / "delivery.json"
                delivery = read_object(delivery_path)
                if delivery["session_id"] not in (None, session_id):
                    raise ServiceError(
                        409, "EXECUTOR_SESSION_CONFLICT", "Task belongs to another session"
                    )
                if delivery["session_id"] is None:
                    delivery["session_id"] = session_id
                    atomic_json(delivery_path, delivery)
                assignment = {
                    "request": self.store.metadata(task_id),
                    "lease_token": delivery["lease_token"],
                    "cancel_requested": (
                        self.store.directory(task_id) / "cancel-request.json"
                    ).exists(),
                }
            return {"assignment": assignment}

    def _delivery(self, task_id: str, body: DeliveryRequest) -> tuple[Path, dict]:
        self._session(str(body.session_id))
        directory = self.store.directory(task_id)
        self.store.metadata(task_id)
        path = directory / "delivery.json"
        delivery = read_object(path)
        if delivery["session_id"] != str(body.session_id) or not secrets.compare_digest(
            delivery["lease_token"].encode(), body.lease_token.encode()
        ):
            raise ServiceError(403, "TASK_LEASE_MISMATCH", "Task delivery credentials do not match")
        return path, delivery

    def start(self, task_id: str, body: DeliveryRequest) -> dict:
        with self.store.locked():
            path, delivery = self._delivery(task_id, body)
            state = self.store.reconcile(task_id)
            self._touch(str(body.session_id))
            if state["state"] in TERMINAL:
                return {"start": False, "state": state["state"]}
            # A lost start response must not allow a new launch much later.
            if (
                age(self.store.metadata(task_id)["created_at_utc"])
                > self.settings.REMOTE_DISPATCH_SECONDS
            ):
                return {"start": False, "state": "REJECTED"}
            delivery["start_granted"] = True
            atomic_json(path, delivery)
            return {"start": True}

    def report(self, task_id: str, body: TaskReport) -> dict:
        with self.store.locked():
            path, delivery = self._delivery(task_id, body)
            self._touch(str(body.session_id))
            state = self.store.reconcile(task_id)
            if state["state"] in TERMINAL:
                return {"delivered": True}
            if not delivery["start_granted"]:
                # Pre-launch failures/cancellation can be safely finalized without
                # granting execution, but a NAVIGATING claim cannot.
                if not body.execution_finished or body.state == "SUCCEEDED":
                    raise ServiceError(409, "START_NOT_GRANTED", "Execution was not granted")
            if body.sequence <= delivery["sequence"]:
                return {
                    "delivered": False,
                    "cancel_requested": (path.parent / "cancel-request.json").exists(),
                }
            if delivery["result"] is not None:
                return {"delivered": False, "cancel_requested": False}
            if body.execution_finished != (body.state in TERMINAL):
                raise ServiceError(
                    422, "INVALID_EXECUTION_REPORT", "Finished flag and task state disagree"
                )
            if body.state == "SUCCEEDED" and not runtime.simulation_succeeded(
                body.simulation_summary or {}, self.store.metadata(task_id)["simulation_route"]
            ):
                raise ServiceError(
                    422,
                    "INVALID_SIMULATION_RESULT",
                    "Successful result must include every checkpoint without collision or fall",
                )
            if body.video and (
                not body.execution_finished
                or body.video.size > self.settings.REMOTE_MAX_VIDEO_BYTES
            ):
                raise ServiceError(
                    413, "INVALID_VIDEO", "Video is not finalized or exceeds the upload limit"
                )
            if body.state == "SUCCEEDED" and not body.video:
                raise ServiceError(
                    422, "VIDEO_REQUIRED", "Successful remote demo requires its completed recording"
                )
            delivery["sequence"] = body.sequence
            changes = {"simulation_progress": body.simulation_progress}
            if body.execution_finished:
                delivery["result"] = body.model_dump(
                    mode="json", exclude={"session_id", "lease_token", "sequence"}
                )
                changes.update(remote_phase="UPLOADING")
            else:
                # Ignore a delayed PREPARING report after navigation has started.
                ranks = {"PREPARING": 0, "NAVIGATING": 1, "STOPPING": 2}
                if ranks.get(body.state, -1) >= ranks.get(state["state"], -1):
                    changes["state"] = body.state
                changes["remote_phase"] = "RUNNING"
            atomic_json(path, delivery)
            self.store.update(task_id, **changes)
            return {
                "delivered": False,
                "cancel_requested": (path.parent / "cancel-request.json").exists(),
            }

    def expected_video(self, task_id: str, body: DeliveryRequest) -> dict:
        with self.store.locked():
            _, delivery = self._delivery(task_id, body)
            self._touch(str(body.session_id))
            descriptor = (delivery.get("result") or {}).get("video")
            if not descriptor:
                raise ServiceError(
                    409, "VIDEO_NOT_EXPECTED", "Report a finalized recording before upload"
                )
            return descriptor

    def accept_video(self, task_id: str, body: DeliveryRequest, temporary: Path) -> dict:
        with self.store.locked():
            path, delivery = self._delivery(task_id, body)
            expected = (delivery.get("result") or {}).get("video")
            if (
                not expected
                or temporary.stat().st_size != expected["size"]
                or hashlib.sha256(temporary.read_bytes()).hexdigest() != expected["sha256"]
            ):
                raise ServiceError(
                    422, "VIDEO_INTEGRITY_MISMATCH", "Recording size or SHA256 does not match"
                )
            with temporary.open("rb") as source:
                if source.read(12)[4:8] != b"ftyp":
                    raise ServiceError(422, "INVALID_VIDEO", "Recording is not an MP4 container")
            temporary.replace(path.parent / "simulation.mp4")
            delivery["video_verified"] = True
            atomic_json(path, delivery)
            self._touch(str(body.session_id))
            return {"sha256": expected["sha256"], "size": expected["size"]}

    def complete(self, task_id: str, body: DeliveryRequest) -> dict:
        with self.store.locked():
            path, delivery = self._delivery(task_id, body)
            self._touch(str(body.session_id))
            if self.store.reconcile(task_id)["state"] in TERMINAL:
                return {"delivered": True}
            result = delivery.get("result")
            if not result:
                raise ServiceError(409, "RESULT_NOT_READY", "Execution result is not finalized")
            if result["video"]:
                video = path.parent / "simulation.mp4"
                if (
                    not delivery["video_verified"]
                    or not video.exists()
                    or hashlib.sha256(video.read_bytes()).hexdigest() != result["video"]["sha256"]
                ):
                    raise ServiceError(409, "VIDEO_NOT_READY", "Verified recording has not arrived")
            self.store.update(
                task_id,
                state=result["state"],
                error=result["error"],
                simulation_summary=result["simulation_summary"],
                simulation_progress=result["simulation_progress"],
                video_available=bool(result["video"]),
                remote_pending=False,
                remote_phase="DELIVERED",
                requires_operator_review=result["requires_operator_review"],
            )
            return {"delivered": True}

    def disconnect(self, body: PollRequest) -> dict:
        with self.store.locked():
            record = self._session(str(body.session_id))
            for task_id in self.store.active():
                delivery = read_object(self.store.directory(task_id) / "delivery.json")
                if not delivery["start_granted"]:
                    atomic_json(
                        self.store.directory(task_id) / "cancel-request.json",
                        {"requested_at_utc": now()},
                    )
                    self.store.reconcile(task_id)
            atomic_json(self.executor_path, record | {"connected": False, "accepting": False})
            return {"disconnected": True}
