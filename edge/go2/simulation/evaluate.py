"""Bounded, immutable simulation campaigns. No robot/cloud imports or execution retry."""

import csv
import hashlib
import importlib.metadata
import json
import math
import os
import random
import signal
import statistics
import subprocess
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
STATES = (
    "SUCCEEDED",
    "COLLISION",
    "FALLEN",
    "STEP_LIMIT",
    "WALL_TIMEOUT",
    "ERROR",
    "CANCELLED",
)


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources():
    files = [
        ROOT / "cli.py",
        ROOT / "evaluate.py",
        ROOT / "evaluation.json",
        ROOT / "routes.json",
    ]
    files += sorted(
        p for p in (ROOT / "src").rglob("*") if p.suffix in {".py", ".xml", ".obj"}
    )
    return {str(p.relative_to(ROOT)): sha(p) for p in files}


def source_digest():
    return hashlib.sha256(json.dumps(sources(), sort_keys=True).encode()).hexdigest()


def validate_config(config):
    if config.get("schema_version") != 1:
        raise ValueError("Unsupported evaluation schema")
    if not 1 <= len(config["seeds"]) <= 50 or len(set(config["seeds"])) != len(
        config["seeds"]
    ):
        raise ValueError("Evaluation requires 1–50 distinct seeds")
    if any(type(seed) is not int or seed < 0 for seed in config["seeds"]):
        raise ValueError("Seeds must be nonnegative integers")
    if (
        not 1 <= config["steps"] <= 120000
        or not 1 <= config["wall_timeout_seconds"] <= 600
    ):
        raise ValueError("Invalid evaluation time/step limit")
    for key, value in config["spawn_jitter"].items():
        if (
            key not in {"x", "y", "yaw"}
            or not math.isfinite(value)
            or not 0 <= value <= 0.2
        ):
            raise ValueError(
                "Only small, finite initial-pose perturbations are supported"
            )
    if set(config["spawn_jitter"]) != {"x", "y", "yaw"}:
        raise ValueError("Initial-pose perturbations require x, y and yaw")
    if any(not math.isfinite(v) or not 0 < v <= 1 for v in config["control"].values()):
        raise ValueError("Invalid control parameters")


def build_cases(config, catalog):
    validate_config(config)
    routes = {route["id"]: route for route in catalog["routes"]}
    cases = []
    for route_id in config["route_ids"]:
        route = routes[route_id]
        for variant in config["variants"]:
            if not math.isfinite(variant["y_offset"]) or abs(variant["y_offset"]) > 0.2:
                raise ValueError("Target offsets must remain small and finite")
            points = [
                point | {"y": point["y"] + variant["y_offset"]}
                for point in route["waypoints"]
            ]
            for seed in config["seeds"]:
                generator = random.Random(seed)
                pose = {
                    key: generator.uniform(-bound, bound)
                    for key, bound in config["spawn_jitter"].items()
                }
                cases.append(
                    {
                        "id": f"{route_id}-{variant['id']}-s{seed:02}",
                        "route_id": route_id,
                        "variant": variant["id"],
                        "scene": route["scene"],
                        "seed": seed,
                        "initial_pose": pose,
                        "waypoints": points,
                        "steps": config["steps"],
                        "wall_timeout_seconds": config["wall_timeout_seconds"],
                        "control": config["control"]
                        | route.get("control", {})
                        | config.get("control_override", {}),
                    }
                )
    if (
        not cases
        or len(cases) > 300
        or len({case["id"] for case in cases}) != len(cases)
    ):
        raise ValueError("Evaluation requires 1–300 distinct cases")
    return cases


def classify(summary):
    if summary.get("collision") is True:
        return "COLLISION"
    if summary.get("fallen") is True:
        return "FALLEN"
    total = len(summary.get("waypoints", []))
    if (
        total > 0
        and summary.get("goal_reached") is True
        and summary.get("collision") is False
        and summary.get("fallen") is False
        and summary.get("waypoints_reached") == total
        and summary.get("reached_indices") == list(range(total))
    ):
        return "SUCCEEDED"
    return "STEP_LIMIT"


def run_case(case, directory, expected_digest, stopped, record=False):
    directory.mkdir(parents=True, exist_ok=False)
    write_json(directory / "case.json", case)
    write_json(directory / "waypoints.json", case["waypoints"])
    result = {"case": case, "state": "ERROR", "summary": None}
    start = time.monotonic()
    process = None
    try:
        if source_digest() != expected_digest:
            raise ValueError("Simulation sources changed during the campaign")
        pose, control = case["initial_pose"], case["control"]
        command = [
            sys.executable,
            "-m",
            "mujoco_sim.run",
            "--scene",
            case["scene"],
            "--navigation-policy",
            str(ROOT / "assets/navigation.pt"),
            "--himloco-policy",
            str(ROOT / "assets/himloco.pt"),
            "--waypoints",
            str(directory / "waypoints.json"),
            "--seed",
            str(case["seed"]),
            "--steps",
            str(case["steps"]),
            "--initial-x",
            str(pose["x"]),
            "--initial-y",
            str(pose["y"]),
            "--initial-yaw",
            str(pose["yaw"]),
            "--speed-scale",
            str(control["speed_scale"]),
            "--command-filter-alpha",
            str(control["command_filter_alpha"]),
            "--turn-lateral-limit",
            str(control["turn_lateral_limit"]),
            "--stop-on-goal",
            "--no-viewer",
            "--device",
            "cpu",
            "--log",
            str(directory / "simulation.jsonl"),
        ]
        if record:
            command += ["--record", str(directory / "simulation.mp4")]
        environment = os.environ.copy()
        environment.pop("PYTHONHOME", None)
        environment["PYTHONPATH"] = str(ROOT / "src")
        with (directory / "execution.log").open("w") as log:
            if stopped.is_set():
                result["state"] = "CANCELLED"
            else:
                process = subprocess.Popen(
                    command,
                    env=environment,
                    cwd=ROOT / "src",
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                while process.poll() is None:
                    if (
                        stopped.is_set()
                        or time.monotonic() - start >= case["wall_timeout_seconds"]
                    ):
                        result["state"] = (
                            "CANCELLED" if stopped.is_set() else "WALL_TIMEOUT"
                        )
                        os.killpg(process.pid, signal.SIGTERM)
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            os.killpg(process.pid, signal.SIGKILL)
                            process.wait(timeout=5)
                        break
                    time.sleep(0.1)
        if process is not None:
            result["returncode"] = process.returncode
            if process.returncode == 0:
                summary = json.loads(
                    (directory / "execution.log").read_text().splitlines()[-1]
                )
                result.update(state=classify(summary), summary=summary)
                write_json(directory / "summary.json", summary)
    except (ValueError, OSError, IndexError) as error:
        result["error"] = str(error)
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        result["process_wall_seconds"] = time.monotonic() - start
        write_json(directory / "result.json", result)
    return result


def aggregate(results):
    counts = Counter(result["state"] for result in results)
    success = [
        result["summary"] for result in results if result["state"] == "SUCCEEDED"
    ]
    return {
        "safety_unknown_trials": sum(r["summary"] is None for r in results),
        "trials": len(results),
        "states": {key: counts[key] for key in STATES},
        "success_rate": counts["SUCCEEDED"] / len(results) if results else None,
        "collision_rate": sum(
            bool((r["summary"] or {}).get("collision")) for r in results
        )
        / len(results)
        if results
        else None,
        "fall_rate": sum(bool((r["summary"] or {}).get("fallen")) for r in results)
        / len(results)
        if results
        else None,
        "successful_simulated_seconds_mean": statistics.mean(
            s["simulated_seconds"] for s in success
        )
        if success
        else None,
        "successful_runner_wall_seconds_mean": statistics.mean(
            s["elapsed_s"] for s in success
        )
        if success
        else None,
    }


def save_report(output, manifest, results):
    report = {
        "schema_version": 1,
        "kind": "MUJOCO_SIMULATION_ONLY",
        "manifest": manifest,
        "overall": aggregate(results),
        "by_scene": {
            scene: aggregate([r for r in results if r["case"]["scene"] == scene])
            for scene in sorted({r["case"]["scene"] for r in results})
        },
        "results": sorted(results, key=lambda result: result["case"]["id"]),
    }
    write_json(output / "report.json", report)
    with (output / "results.csv").open("w", newline="") as target:
        writer = csv.writer(target)
        writer.writerow(
            [
                "case_id",
                "scene",
                "variant",
                "seed",
                "state",
                "initial_x",
                "initial_y",
                "initial_yaw",
                "checkpoints_reached",
                "simulated_seconds",
                "runner_wall_seconds",
                "process_wall_seconds",
                "path_length",
                "collision",
                "fallen",
            ]
        )
        for result in report["results"]:
            case, summary = result["case"], result["summary"] or {}
            writer.writerow(
                [
                    case["id"],
                    case["scene"],
                    case["variant"],
                    case["seed"],
                    result["state"],
                    *(case["initial_pose"][key] for key in ("x", "y", "yaw")),
                    summary.get("waypoints_reached"),
                    summary.get("simulated_seconds"),
                    summary.get("elapsed_s"),
                    result["process_wall_seconds"],
                    summary.get("path_length"),
                    summary.get("collision"),
                    summary.get("fallen"),
                ]
            )
    lines = [
        "# 仿真批量评测",
        "",
        "仅为当前模型在固定小场景与小幅初始位姿扰动下的结果，不代表实机成绩。",
        "",
        "| 场景 | 次数 | 成功 | 碰撞终止 | 跌倒终止 | 步数耗尽 | 运行超时 | 执行错误 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for scene, group in report["by_scene"].items():
        counts = group["states"]
        lines.append(
            f"| {scene} | {group['trials']} | {counts['SUCCEEDED']} | {counts['COLLISION']} | {counts['FALLEN']} | {counts['STEP_LIMIT']} | {counts['WALL_TIMEOUT']} | {counts['ERROR']} |"
        )
    lines += [
        "",
        "成功要求按顺序到达全部 checkpoint、全过程无碰撞／跌倒。失败不删除、不重试。",
        "",
        "模拟耗时与电脑运行耗时分开记录；并行数影响电脑耗时。碰撞／跌倒率按全部运行结果分别统计。",
        "",
        "完整配置、模型与源码哈希见 report.json；逐次结果见 results.csv 和各任务目录。",
    ]
    (output / "report.md").write_text("\n".join(lines) + "\n")
    return report


def main(args):
    from cli import check_models, models

    check_models()
    config = json.loads(args.config.read_text())
    cases = build_cases(config, json.loads((ROOT / "routes.json").read_text()))
    snapshot = sources()
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    for case in cases:
        case["source_digest"] = digest
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config": config,
        "sources": snapshot,
        "source_digest": digest,
        "model_sha256": {item["id"]: item["sha256"] for item in models()},
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "torch", "mujoco")
        },
        "python": sys.version.split()[0],
        "jobs": args.jobs,
        "case_count": len(cases),
        "cases": cases,
    }
    write_json(output / "manifest.json", manifest)
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    results = []
    if args.replay:
        case = json.loads(args.replay.read_text())
        if case.get("source_digest") != digest:
            raise ValueError(
                "Replay requires the campaign's exact simulation source version"
            )
        # Replay is explicit and saved separately; it never overwrites campaign evidence.
        manifest["replay_of"] = str(args.replay)
        cases = [case]
        manifest.update(cases=cases, case_count=1)
        write_json(output / "manifest.json", manifest)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        pending = [
            pool.submit(
                run_case, case, output / case["id"], digest, stopped, bool(args.replay)
            )
            for case in cases
        ]
        for future in as_completed(pending):
            result = future.result()
            results.append(result)
            save_report(output, manifest, results)
            print(
                f"{len(results)}/{len(cases)} {result['case']['id']}: {result['state']}",
                flush=True,
            )
    report = save_report(output, manifest, results)
    print(json.dumps(report["overall"], ensure_ascii=False), flush=True)
    return 130 if stopped.is_set() else 1 if report["overall"]["states"]["ERROR"] else 0
