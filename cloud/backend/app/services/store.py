"""Durable task records; a separate process owns each execution."""

import fcntl
import json
import os
import re
import tempfile
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT", "REJECTED"}


class ServiceError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message
        super().__init__(message)


def now() -> str:
    return datetime.now(UTC).isoformat()


def read_object(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(value, output, ensure_ascii=False, allow_nan=False)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def identity(pid: int | None) -> str | None:
    if not pid:
        return None
    try:
        fields = Path("/proc", str(pid), "stat").read_text().rsplit(")", 1)[1].split()
        return fields[19] if fields[0] != "Z" else None
    except OSError, IndexError:
        return None


def alive(record: dict) -> bool:
    return bool(record.get("start_ticks")) and identity(record.get("pid")) == record["start_ticks"]


class TaskStore:
    def __init__(self, data_dir: Path):
        self.root = data_dir.resolve() / "tasks"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._mutex = threading.RLock()
        self._lock_depth = 0

    def directory(self, task_id: str) -> Path:
        if not re.fullmatch(r"task-[a-f0-9]{32}", task_id):
            raise ServiceError(404, "TASK_NOT_FOUND", "Task not found")
        path = self.root / task_id
        if path.is_symlink():
            raise ServiceError(404, "TASK_NOT_FOUND", "Task not found")
        return path

    @contextmanager
    def locked(self):
        with self._mutex:
            if self._lock_depth:
                self._lock_depth += 1
                try:
                    yield
                finally:
                    self._lock_depth -= 1
                return
            with (self.root / ".submit.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                self._lock_depth = 1
                try:
                    yield
                finally:
                    self._lock_depth = 0
                    fcntl.flock(lock, fcntl.LOCK_UN)

    def metadata(self, task_id: str) -> dict:
        try:
            return read_object(self.directory(task_id) / "request.json")
        except FileNotFoundError:
            raise ServiceError(404, "TASK_NOT_FOUND", "Task not found") from None

    def state(self, task_id: str) -> dict:
        return read_object(self.directory(task_id) / "state.json")

    def update(self, task_id: str, **changes) -> dict:
        with self.locked():
            return self._update(task_id, **changes)

    def _update(self, task_id: str, **changes) -> dict:
        directory = self.directory(task_id)
        state = self.state(task_id) if (directory / "state.json").is_file() else {}
        before = state.get("state")
        state.update(changes, updated_at_utc=now())
        atomic_json(directory / "state.json", state)
        if state.get("state") != before:
            with (directory / "events.jsonl").open("a", encoding="utf-8") as output:
                output.write(
                    json.dumps(
                        {
                            "state": state["state"],
                            "at_utc": state["updated_at_utc"],
                            "error": state.get("error"),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        return state

    def reconcile(self, task_id: str) -> dict:
        with self.locked():
            return self._reconcile(task_id)

    def _reconcile(self, task_id: str) -> dict:
        state = self.state(task_id)
        if self.metadata(task_id).get("execution_backend") == "remote":
            # Network liveness is handled by RemoteTaskStore, never by a local PID.
            return state
        directory = self.directory(task_id)
        if state["state"] in TERMINAL and state.get("analysis_state") != "RUNNING":
            return state
        process_path = directory / "process.json"
        if process_path.is_file() and alive(read_object(process_path)):
            return state
        if state.get("analysis_state") == "RUNNING":
            updated = datetime.fromisoformat(state["updated_at_utc"])
            # An explicit analysis can start long after the robot task. During
            # launch, process.json may still describe its previous, exited worker.
            if (datetime.now(UTC) - updated).total_seconds() < 10:
                return state
        created = datetime.fromisoformat(self.metadata(task_id)["created_at_utc"])
        if not process_path.exists() and (datetime.now(UTC) - created).total_seconds() < 10:
            return state
        if state["state"] in TERMINAL:
            return self.update(
                task_id,
                analysis_state="FAILED",
                analysis_error={
                    "code": "WORKER_LOST",
                    "message": "Analysis worker exited unexpectedly",
                },
            )
        # Never guess that a vanished motion controller has physically stopped.
        return self.update(
            task_id,
            state="FAILED",
            error={
                "code": "WORKER_LOST",
                "message": "Task worker exited unexpectedly; inspect local logs",
            },
            requires_operator_review=True,
        )

    def identifiers(self) -> list[str]:
        return sorted(
            (p.name for p in self.root.glob("task-*") if p.is_dir() and not p.is_symlink()),
            reverse=True,
        )

    def active(self) -> list[str]:
        result = []
        for task_id in self.identifiers():
            state = self.reconcile(task_id)
            process_path = self.directory(task_id) / "process.json"
            worker_alive = process_path.is_file() and alive(read_object(process_path))
            if (
                state["state"] not in TERMINAL
                or state.get("requires_operator_review")
                or state.get("analysis_state") == "RUNNING"
                or worker_alive
            ):
                result.append(task_id)
        return result
