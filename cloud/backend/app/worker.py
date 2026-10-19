"""Per-task supervisor. Runs outside the HTTP request/server process."""

import argparse
import json
import os
import signal
import subprocess
import time
from pathlib import Path

from app.core.config import settings
from app.services import huawei, runtime
from app.services.store import (
    TERMINAL,
    ServiceError,
    TaskStore,
    atomic_json,
    identity,
    now,
    read_object,
)


def terminate_simulation(process: subprocess.Popen) -> None:
    # process owns the new session; never use a PID supplied by a client or state file.
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def inherited_gate() -> tuple[int, ...]:
    value = os.environ.get("CAMPUS_EXECUTION_GATE_FD")
    if value is None:
        return ()
    descriptor = int(value)
    os.fstat(descriptor)
    return (descriptor,)


def final_json(path: Path) -> dict:
    # The simulation prints one final JSON summary after possible library messages.
    with path.open("rb") as source:
        source.seek(max(0, path.stat().st_size - 128 * 1024))
        lines = source.read().decode("utf-8", errors="replace").splitlines()
    for line in reversed(lines):
        try:
            value = json.loads(line)
            if isinstance(value, dict) and "goal_reached" in value:
                return value
        except ValueError:
            continue
    raise RuntimeError("Simulation did not produce a final summary")


def simulation_progress(path: Path) -> dict | None:
    if not path.exists():
        return None
    with path.open("rb") as source:
        source.seek(max(0, path.stat().st_size - 64 * 1024))
        lines = source.read().splitlines()
    for line in reversed(lines):
        try:
            value = json.loads(line)
            return {
                key: value.get(key)
                for key in (
                    "step",
                    "position_xy",
                    "target_distance",
                    "goal_reached",
                    "collision",
                    "fallen",
                    "waypoint_index",
                    "waypoints_total",
                    "waypoints_reached",
                    "reached_waypoint_index",
                    "target_xy",
                )
            }
        except ValueError:
            continue
    return None


def execute_simulation(store: TaskStore, task_id: str, metadata: dict) -> None:
    directory = store.directory(task_id)
    command = runtime.simulation_command(
        settings, metadata["point"], directory, metadata.get("simulation_route")
    )
    output_path = directory / "execution.log"
    environment = os.environ.copy()
    environment.pop("PYTHONHOME", None)
    environment["PYTHONPATH"] = str(settings.SIM_SOURCE.resolve())
    environment["MUJOCO_GL"] = "egl"
    started = time.monotonic()
    process = None
    reason = None
    try:
        with output_path.open("wb") as output:
            process = subprocess.Popen(
                command,
                cwd=settings.SIM_SOURCE.resolve(),
                env=environment,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                pass_fds=inherited_gate(),
            )
            store.update(task_id, state="NAVIGATING", analysis_state="NO_CAMERA_PHOTO")
            while process.poll() is None:
                if (directory / "cancel-request.json").exists():
                    reason = "CANCELLED"
                    break
                if time.monotonic() - started >= metadata["timeout_seconds"]:
                    reason = "TASK_TIMEOUT"
                    break
                progress = simulation_progress(directory / "simulation.jsonl")
                if progress:
                    store.update(task_id, simulation_progress=progress)
                time.sleep(0.2)
            if reason:
                store.update(task_id, state="STOPPING")
                terminate_simulation(process)
        if reason:
            store.update(
                task_id,
                state="CANCELLED" if reason == "CANCELLED" else "TIMED_OUT",
                error={"code": reason, "message": "Simulation stopped"},
            )
            return
        if (directory / "cancel-request.json").exists():
            store.update(
                task_id,
                state="CANCELLED",
                error={"code": "CANCELLED", "message": "Cancelled before result handoff"},
            )
            return
        if process.returncode:
            raise RuntimeError("Simulation process failed; inspect local execution.log")
        summary = final_json(output_path)
        atomic_json(directory / "simulation-summary.json", summary)
        success = runtime.simulation_succeeded(summary, metadata.get("simulation_route"))
        video = directory / "simulation.mp4"
        progress = simulation_progress(directory / "simulation.jsonl")
        store.update(
            task_id,
            state="SUCCEEDED" if success else "FAILED",
            simulation_summary=summary,
            simulation_progress=progress,
            video_available=video.is_file() and video.stat().st_size > 0,
            error=None
            if success
            else {
                "code": "SIMULATION_GOAL_NOT_REACHED",
                "message": "Simulation did not safely reach the goal",
            },
        )
    finally:
        if process is not None and process.poll() is None:
            terminate_simulation(process)


def execute_motion(store: TaskStore, task_id: str, metadata: dict) -> None:
    directory = store.directory(task_id)
    target = runtime.runtime_directory(settings, task_id)
    command = runtime.motion_command(settings, task_id, metadata["point_id"])
    process = None
    requested = False
    stop_reason = None
    started = time.monotonic()
    try:
        with (directory / "execution.log").open("wb") as output:
            process = subprocess.Popen(
                command,
                cwd=runtime.RUNTIME,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                pass_fds=inherited_gate(),
            )
            while process.poll() is None:
                path = target / "task.json"
                if path.exists():
                    record = read_object(path)
                    if record.get("task_id") != task_id:
                        raise RuntimeError("Runtime task ID mismatch")
                    # Publish terminal success only after process exit and photo verification.
                    if record.get("state") not in TERMINAL:
                        store.update(
                            task_id,
                            **{
                                key: record.get(key)
                                for key in ("state", "error", "stop_acknowledged", "cleanup_forced")
                            },
                        )
                expired = time.monotonic() - started >= metadata["timeout_seconds"]
                cancelled = (directory / "cancel-request.json").exists()
                if (expired or cancelled) and not requested and path.exists():
                    stop_reason = "CANCELLED" if cancelled else "TASK_TIMEOUT"
                    runtime.cancel_motion(settings, task_id)
                    requested = True
                if time.monotonic() - started > metadata["timeout_seconds"] + 25:
                    raise RuntimeError("Runtime controller exceeded cleanup deadline")
                time.sleep(0.15)
        path = target / "task.json"
        if not path.is_file():
            raise RuntimeError("Runtime did not create a task record; inspect local execution.log")
        record = read_object(path)
        if record.get("task_id") != task_id or record.get("state") not in TERMINAL:
            raise RuntimeError("Runtime result is incomplete or mismatched")
        evidence_fields = {key: record.get(key) for key in ("stop_acknowledged", "cleanup_forced")}
        if stop_reason == "TASK_TIMEOUT":
            store.update(
                task_id,
                state="TIMED_OUT",
                **evidence_fields,
                error={
                    "code": "TASK_TIMEOUT",
                    "message": "Overall task deadline reached",
                    "runtime_error": record.get("error"),
                },
            )
            return
        if (directory / "cancel-request.json").exists() and record["state"] == "SUCCEEDED":
            store.update(
                task_id,
                state="CANCELLED",
                **evidence_fields,
                error={"code": "CANCELLED", "message": "Cancelled before result handoff"},
            )
            return
        if record["state"] == "SUCCEEDED" and process.returncode == 0:
            _, evidence, _ = runtime.photo_evidence(settings, task_id)
            analysis_state = (
                "NOT_REQUESTED"
                if not metadata["question"]
                else "RUNNING"
                if settings.huawei_configured
                else "NOT_CONFIGURED"
            )
            store.update(
                task_id,
                state="SUCCEEDED",
                error=None,
                **evidence_fields,
                photo_available=True,
                photo=evidence,
                analysis_state=analysis_state,
            )
            huawei.analyze(settings, store, task_id, metadata["question"])
        elif record["state"] == "SUCCEEDED":
            raise RuntimeError("Runtime exit status contradicts its success record")
        else:
            store.update(
                task_id, state=record["state"], error=record.get("error"), **evidence_fields
            )
    finally:
        if process is not None and process.poll() is None:
            # Let the existing controller perform StopMove and process-group cleanup.
            process.terminate()
            try:
                process.wait(timeout=22)
            except subprocess.TimeoutExpired:
                store.update(task_id, requires_operator_review=True, stop_acknowledged=None)
                # Do not claim a physical stop or kill unrelated robot descendants.


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["execute", "analyze"])
    parser.add_argument("task_id")
    args = parser.parse_args()
    store = TaskStore(settings.APP_DATA_DIR)
    metadata = store.metadata(args.task_id)
    directory = store.directory(args.task_id)

    def request_stop(signum, frame):
        atomic_json(directory / "cancel-request.json", {"requested_at_utc": now()})

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    atomic_json(
        directory / "process.json", {"pid": os.getpid(), "start_ticks": identity(os.getpid())}
    )
    with (directory / "worker-starts.jsonl").open("a") as output:
        output.write(
            json.dumps({"action": args.action, "pid": os.getpid(), "at_utc": now()}) + "\n"
        )
    try:
        if args.action == "analyze":
            question = read_object(directory / "analysis-request.json")["question"]
            huawei.analyze(settings, store, args.task_id, question)
        elif (directory / "cancel-request.json").exists():
            store.update(
                args.task_id,
                state="CANCELLED",
                error={"code": "CANCELLED", "message": "Cancelled before execution"},
            )
        elif metadata["mode"] == "simulation":
            execute_simulation(store, args.task_id, metadata)
        else:
            execute_motion(store, args.task_id, metadata)
    except Exception as error:
        import traceback

        traceback.print_exc()
        code = error.code if isinstance(error, ServiceError) else "EXECUTION_FAILED"
        message = (
            error.message
            if isinstance(error, ServiceError)
            else "Execution failed; inspect local worker logs"
        )
        if args.action == "analyze":
            store.update(
                args.task_id,
                analysis_state="FAILED",
                analysis_error={"code": code, "message": message},
            )
        else:
            store.update(args.task_id, state="FAILED", error={"code": code, "message": message})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
