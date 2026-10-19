"""Adapt existing local CLI/file contracts without importing robot SDKs."""

import hashlib
import importlib.util
import math
import os
import re
import shutil
import subprocess
from pathlib import Path

from app.core.config import REPO_ROOT, Settings
from app.services.store import ServiceError, read_object

RUNTIME = REPO_ROOT / "edge/go2/runtime"
SIM_SCENES = {"himloco_flat", "flat_obstacle", "staggered_walls"}


def simulation_succeeded(summary: dict, route: dict | None = None) -> bool:
    success = (
        summary.get("goal_reached") is True
        and summary.get("fallen") is False
        and summary.get("collision") is False
    )
    if route:
        total = len(route["waypoints"])
        success = success and (
            summary.get("waypoints_total") == total
            and summary.get("waypoints_reached") == total
            and summary.get("reached_indices") == list(range(total))
        )
    return success


def simulation_routes(settings: Settings) -> list[dict]:
    """Small server-owned route catalog, separate from hardware observation points."""
    catalog = read_object(settings.SIM_ROUTES)
    if catalog.get("schema_version") != 1 or not isinstance(catalog.get("routes"), list):
        raise ValueError("Invalid simulation route catalog")
    seen = set()
    for route in catalog["routes"]:
        identifier = route.get("id")
        if (
            not isinstance(identifier, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", identifier)
            or identifier in seen
        ):
            raise ValueError("Invalid or duplicate simulation route ID")
        seen.add(identifier)
        if route.get("scene") not in SIM_SCENES or not isinstance(route.get("description"), str):
            raise ValueError("Invalid simulation route scene or description")
        if "control" in route:
            control = route["control"]
            if not isinstance(control, dict) or set(control) - {
                "speed_scale",
                "command_filter_alpha",
                "turn_lateral_limit",
            }:
                raise ValueError("Invalid simulation control fields")
            if any(
                type(v) not in (float, int) or not math.isfinite(v) or not 0 < v <= 1
                for v in control.values()
            ):
                raise ValueError("Simulation control values must be finite and in (0, 1]")
        waypoints = route.get("waypoints")
        if not isinstance(waypoints, list) or not 1 <= len(waypoints) <= 20:
            raise ValueError("Simulation routes require 1–20 checkpoints")
        for point in waypoints:
            if not isinstance(point, dict) or set(point) != {"x", "y", "radius"}:
                raise ValueError("Invalid checkpoint fields")
            if any(
                type(point[k]) not in (float, int) or not math.isfinite(point[k]) for k in point
            ):
                raise ValueError("Checkpoint values must be finite numbers")
            if point["radius"] <= 0:
                raise ValueError("Checkpoint radius must be positive")
    return catalog["routes"]


def select_simulation_route(settings: Settings, route_id: str) -> dict:
    try:
        for route in simulation_routes(settings):
            if route["id"] == route_id:
                return route
    except OSError, ValueError, TypeError, AttributeError:
        raise ServiceError(
            503, "SIMULATION_ROUTES_INVALID", "Simulation route catalog is invalid"
        ) from None
    raise ServiceError(422, "UNKNOWN_SIMULATION_ROUTE", "Unknown simulation route")


def runtime_config(settings: Settings) -> dict:
    # cli.py is standard-library-only at import time. Load under a private module name.
    spec = importlib.util.spec_from_file_location("_campus_go2_config", RUNTIME / "cli.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.read_config(str(settings.GO2_CONFIG))


def points(settings: Settings) -> dict:
    catalog = read_object(settings.GO2_POINTS)
    if catalog.get("schema_version") != 1 or catalog.get("reference") != "initial_pose":
        raise ValueError("Observation points require schema_version=1 and reference=initial_pose")
    entries = catalog.get("points")
    if not isinstance(entries, list) or not entries:
        raise ValueError("No observation points configured")
    seen = set()
    for point in entries:
        if not isinstance(point, dict) or set(point) - {
            "id",
            "description",
            "goal_forward",
            "goal_left",
        }:
            raise ValueError("Unsupported observation point fields")
        identifier = point.get("id")
        if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", identifier):
            raise ValueError("Invalid observation point ID")
        if identifier in seen or not isinstance(point.get("description", ""), str):
            raise ValueError("Duplicate point or invalid description")
        seen.add(identifier)
        for key in ("goal_forward", "goal_left"):
            if type(point.get(key)) not in (float, int) or not math.isfinite(point[key]):
                raise ValueError("Point coordinates must be finite numbers")
        if point["goal_forward"] == 0 and point["goal_left"] == 0:
            raise ValueError("Point offset must be nonzero")
    return {
        "reference": "initial_pose",
        "example_configuration": settings.GO2_POINTS.name.endswith(".example.json"),
        "points": entries,
    }


def select_point(settings: Settings, point_id: str) -> dict:
    try:
        for point in points(settings)["points"]:
            if point["id"] == point_id:
                return point
    except OSError, ValueError, TypeError:
        raise ServiceError(
            503, "POINTS_NOT_CONFIGURED", "Observation point configuration is invalid"
        ) from None
    raise ServiceError(422, "UNKNOWN_POINT", "Unknown observation point")


def executable(value: str | None) -> bool:
    return bool(
        value and (shutil.which(value) or (Path(value).is_file() and os.access(value, os.X_OK)))
    )


def simulation_ready(settings: Settings) -> bool:
    return bool(
        executable(settings.SIM_PYTHON)
        and (settings.SIM_SOURCE / "mujoco_sim/run.py").is_file()
        and settings.SIM_HIMLOCO_POLICY
        and settings.SIM_HIMLOCO_POLICY.is_file()
        and settings.SIM_NAVIGATION_POLICY
        and settings.SIM_NAVIGATION_POLICY.is_file()
        and settings.SIM_SCENE in SIM_SCENES
        and (not settings.SIM_RECORD_VIDEO or shutil.which("ffmpeg"))
    )


def simulation_command(
    settings: Settings, point: dict, directory: Path, route: dict | None = None
) -> list[str]:
    if not simulation_ready(settings):
        raise ServiceError(
            503, "SIMULATION_NOT_CONFIGURED", "Configure the existing MuJoCo environment and assets"
        )
    command = [
        settings.SIM_PYTHON,
        "-m",
        "mujoco_sim.run",
        "--scene",
        route["scene"] if route else settings.SIM_SCENE,
        "--himloco-policy",
        str(settings.SIM_HIMLOCO_POLICY.resolve()),
        "--navigation-policy",
        str(settings.SIM_NAVIGATION_POLICY.resolve()),
        "--goal-x",
        str(point["goal_forward"]),
        "--goal-y",
        str(point["goal_left"]),
        "--goal-radius",
        "0.15",
        "--steps",
        str(settings.SIM_STEPS),
        "--seed",
        "0",
        "--stop-on-goal",
        "--no-viewer",
        "--device",
        "cpu",
        "--log",
        str(directory / "simulation.jsonl"),
    ]
    if route:
        # Snapshot the accepted route; never accept client-supplied filesystem paths.
        from app.services.store import atomic_json

        waypoint_path = directory / "waypoints.json"
        atomic_json(waypoint_path, route["waypoints"])
        command += ["--waypoints", str(waypoint_path.resolve())]
        for key, value in route.get("control", {}).items():
            command += ["--" + key.replace("_", "-"), str(value)]
    if settings.SIM_RECORD_VIDEO:
        command += ["--record", str(directory / "simulation.mp4")]
    return command


def motion_command(settings: Settings, task_id: str, point_id: str) -> list[str]:
    if not settings.MOTION_ENABLED:
        raise ServiceError(
            409, "MOTION_DISABLED", "Real robot execution is disabled in local configuration"
        )
    command = [
        settings.GO2_PYTHON,
        str(RUNTIME / "cli.py"),
        "task-run",
        "--config",
        str(settings.GO2_CONFIG.resolve()),
        "--points",
        str(settings.GO2_POINTS.resolve()),
        "--point-id",
        point_id,
        "--task-id",
        task_id,
        "--enable-motion",
        "--task-timeout",
        str(settings.TASK_TIMEOUT_SECONDS),
        "--source",
        settings.CAMERA_SOURCE,
    ]
    if settings.CAPTURE_PYTHON:
        command += ["--capture-python", settings.CAPTURE_PYTHON]
    if settings.CAMERA_SOURCE == "dock":
        if not settings.DOCK_HOST:
            raise ServiceError(503, "CAMERA_NOT_CONFIGURED", "Configure DOCK_HOST before executing")
        command += [
            "--host",
            settings.DOCK_HOST,
            "--user",
            settings.DOCK_USER,
            "--device",
            settings.DOCK_DEVICE,
        ]
    return command


def runtime_directory(settings: Settings, task_id: str) -> Path:
    return Path(runtime_config(settings)["output_dir"]).resolve() / "tasks" / task_id


def cancel_motion(settings: Settings, task_id: str) -> None:
    completed = subprocess.run(
        [
            settings.GO2_PYTHON,
            str(RUNTIME / "cli.py"),
            "task-cancel",
            "--config",
            str(settings.GO2_CONFIG.resolve()),
            "--task-id",
            task_id,
        ],
        capture_output=True,
        timeout=5,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError("Runtime did not acknowledge cancellation request")


def inside(path: Path, root: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
        raise ServiceError(409, "INVALID_ARTIFACT", "Artifact path is invalid or missing")
    return resolved


def photo_evidence(settings: Settings, task_id: str) -> tuple[Path, dict, str]:
    """Recheck the real task's successful handoff before serving or uploading a photo."""
    directory = runtime_directory(settings, task_id)
    try:
        record = read_object(directory / "task.json")
        if (
            record.get("task_id") != task_id
            or record.get("state") != "SUCCEEDED"
            or not record.get("result")
        ):
            raise ValueError("No successful photo handoff")
        result_path = inside(directory / record["result"], directory)
        result = read_object(result_path)
        if (
            result.get("task_id") != task_id
            or result.get("state") != "PHOTO_READY"
            or result.get("mode") != "motion"
            or result.get("stop_acknowledged") is not True
        ):
            raise ValueError("Photo does not match a successful motion task")
        image = inside(result_path.parent / result["image"], directory)
        metadata_path = inside(result_path.parent / result["metadata"], directory)
        metadata = read_object(metadata_path)
        if image.stat().st_size > settings.MAX_PHOTO_BYTES:
            raise ServiceError(413, "PHOTO_TOO_LARGE", "Photo exceeds configured size limit")
        content = image.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        if digest != result.get("image_sha256") or digest != metadata.get("image_sha256"):
            raise ValueError("Photo integrity check failed")
        if result.get("source") not in {"unitree", "dock"} or metadata.get("mode") != "camera":
            raise ValueError("Photo is not from a configured live camera")
        if (
            metadata.get("source") != result["source"]
            or metadata.get("captured_at_utc") != result.get("captured_at_utc")
            or not result.get("captured_at_utc")
        ):
            raise ValueError("Photo metadata mismatch")
        if any(
            type(result.get(key)) is not int or result[key] <= 0 or metadata.get(key) != result[key]
            for key in ("width", "height")
        ):
            raise ValueError("Photo dimensions mismatch")
        mime = (
            "image/png"
            if content.startswith(b"\x89PNG\r\n\x1a\n")
            else ("image/jpeg" if content.startswith(b"\xff\xd8\xff") else None)
        )
        if not mime:
            raise ValueError("Unsupported photo encoding")
        public = {
            key: result.get(key)
            for key in (
                "source",
                "captured_at_utc",
                "capture_time_basis",
                "width",
                "height",
                "image_sha256",
            )
        }
        return image, public, mime
    except OSError, ValueError, KeyError, TypeError:
        raise ServiceError(
            409, "PHOTO_NOT_READY", "No verified camera photo is available"
        ) from None
