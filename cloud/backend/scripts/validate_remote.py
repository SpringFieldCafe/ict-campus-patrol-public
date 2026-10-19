"""Opt-in real MuJoCo validation with two HTTP processes and a cuttable TCP link.

No hardware or cloud resources. Uses the private remote-demo configs, creates
fresh data directories, and stops only processes started by this script.
"""

import argparse
import contextlib
import hashlib
import json
import os
import select
import socket
import socketserver
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import httpx

from app.core.config import BACKEND_ROOT, REPO_ROOT, Settings
from app.services import runtime
from app.services.execution_gate import local_suspended
from app.services.store import TERMINAL, alive, atomic_json, now, read_object
from app.services.tasks import TaskService


def wait_for(check, description, seconds=100):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except httpx.TransportError, FileNotFoundError:
            pass
        time.sleep(0.2)
    raise AssertionError(f"Timed out: {description}")


class FaultLink(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, target_port):
        self.target_port = target_port
        self.connected = True
        self.channels = set()
        self.mutex = threading.Lock()
        super().__init__(("127.0.0.1", 0), Forward)

    def disconnect(self):
        with self.mutex:
            self.connected = False
            for channel in self.channels:
                with contextlib.suppress(OSError):
                    channel.shutdown(socket.SHUT_RDWR)


class Forward(socketserver.BaseRequestHandler):
    def handle(self):
        with contextlib.ExitStack() as resources:
            try:
                with self.server.mutex:
                    if not self.server.connected:
                        return
                    upstream = socket.create_connection(("127.0.0.1", self.server.target_port))
                    resources.enter_context(upstream)
                    channels = [self.request, upstream]
                    self.server.channels.update(channels)
                while self.server.connected:
                    readable, _, _ = select.select(channels, [], [], 0.2)
                    for source in readable:
                        data = source.recv(65536)
                        if not data:
                            return
                        (upstream if source is self.request else self.request).sendall(data)
            except OSError:
                pass
            finally:
                with self.server.mutex:
                    self.server.channels.discard(self.request)
                    if "upstream" in locals():
                        self.server.channels.discard(upstream)


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def stop(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
            raise AssertionError("Owned validation process did not shut down cleanly") from None


def main():
    parser = argparse.ArgumentParser(description="Opt-in real simulation protocol validation")
    parser.add_argument(
        "--browser", action="store_true", help="Also run the existing judge browser smoke"
    )
    parser.add_argument(
        "--check-timeout",
        action="store_true",
        help="Also check a real local simulation's short total deadline",
    )
    args = parser.parse_args()
    private = REPO_ROOT / ".local/remote-demo"
    if not (private / "server.env").is_file() or not (private / "executor.env").is_file():
        raise ValueError("Run remote-demo.sh init first")
    server_config = Settings(_env_file=private / "server.env")
    executor_config = Settings(_env_file=private / "executor.env")
    if not runtime.simulation_ready(executor_config):
        raise ValueError("Prepare the existing isolated simulation and authorized policies first")
    if local_suspended(executor_config.EXECUTION_LOCK_PATH):
        raise ValueError("Stop the manually running executor before this opt-in validation")
    root = REPO_ROOT / ".local/remote-validation"
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    run = Path(tempfile.mkdtemp(prefix="run-", dir=root))
    report = {"started_at_utc": now(), "checks": [], "tasks": {}, "result": "running"}
    server = agent = timeout_server = None
    port = free_port()
    link = FaultLink(port)
    thread = threading.Thread(target=link.serve_forever, daemon=True)
    thread.start()
    environment = os.environ.copy()
    for key in ("PYTHONPATH", "PYTHONHOME"):
        environment.pop(key, None)
    environment["PYTHONUNBUFFERED"] = "1"
    try:
        with contextlib.ExitStack() as resources:
            server_log = resources.enter_context((run / "server.log").open("wb"))
            agent_log = resources.enter_context((run / "executor.log").open("wb"))
            server = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(port),
                    "--workers",
                    "1",
                ],
                cwd=BACKEND_ROOT,
                env=environment
                | {
                    "CAMPUS_ENV_FILE": str(private / "server.env"),
                    "APP_DATA_DIR": str(run / "server"),
                },
                stdout=server_log,
                stderr=subprocess.STDOUT,
            )
            client = resources.enter_context(
                httpx.Client(
                    base_url=f"http://127.0.0.1:{port}",
                    timeout=5,
                    trust_env=False,
                )
            )
            wait_for(lambda: client.get("/healthz").status_code == 200, "server health", 15)
            login = client.post(
                "/api/v1/login/access-token",
                data={
                    "username": server_config.REMOTE_DEMO_USER,
                    "password": server_config.REMOTE_DEMO_PASSWORD.get_secret_value(),
                },
            )
            login.raise_for_status()
            client.headers["Authorization"] = "Bearer " + login.json()["access_token"]
            assert client.get("/api/v1/users/me").json()["is_superuser"] is False
            assert runtime.simulation_ready(server_config) is False
            report["checks"].append(
                "judge is non-admin; coordinator has no simulation dependencies"
            )
            agent = subprocess.Popen(
                [sys.executable, "-m", "app.remote_agent", "--enable-remote"],
                cwd=BACKEND_ROOT,
                env=environment
                | {
                    "CAMPUS_ENV_FILE": str(private / "executor.env"),
                    "APP_DATA_DIR": str(run / "executor"),
                    "REMOTE_SERVER_URL": f"http://127.0.0.1:{link.server_address[1]}",
                },
                stdout=agent_log,
                stderr=subprocess.STDOUT,
            )

            def ready():
                return client.get("/api/v1/capabilities").json()["remote"]["ready"]

            def view(task_id):
                response = client.get(f"/api/v1/tasks/{task_id}")
                response.raise_for_status()
                return response.json()

            def create():
                wait_for(ready, "executor admission", 15)
                response = client.post(
                    "/api/v1/tasks",
                    json={
                        "mode": "simulation",
                        "simulation_route_id": server_config.REMOTE_ROUTE_ID,
                    },
                )
                assert response.status_code == 202, response.text
                task_id = response.json()["task_id"]
                wait_for(lambda: view(task_id)["state"] == "NAVIGATING", "real navigation", 30)
                return task_id

            def finished(task_id):
                value = view(task_id)
                return value if value["state"] in TERMINAL and not value["remote_pending"] else None

            def local_finished(task_id):
                directory = run / "executor/tasks" / task_id
                state = read_object(directory / "state.json")
                process = read_object(directory / "process.json")
                return state if state["state"] in TERMINAL and not alive(process) else None

            def record(name, task_id, value):
                directory = run / "executor/tasks" / task_id
                starts = [
                    json.loads(line)
                    for line in (directory / "worker-starts.jsonl").read_text().splitlines()
                ]
                assert sum(row["action"] == "execute" for row in starts) == 1
                assert value["requires_operator_review"] is False
                report["tasks"][name] = {
                    "task_id": task_id,
                    "state": value["state"],
                    "execute_starts": 1,
                    "video_available": value["video_available"],
                    "simulation_summary": value.get("simulation_summary"),
                }

            wait_for(ready, "initial heartbeat", 15)
            native = TaskService(
                executor_config.model_copy(update={"APP_DATA_DIR": run / "native"})
            )
            assert native.capabilities()["local_suspended"] is True
            report["checks"].append("remote executor suspends original local task admission")
            if args.browser:
                node = REPO_ROOT / ".local/toolchains/node-v24.22.0-linux-x64/bin/node"
                with (run / "browser.log").open("wb") as browser_log:
                    subprocess.run(
                        [str(node), "apps/web/tests/e2e/live-smoke.mjs"],
                        cwd=REPO_ROOT,
                        check=True,
                        timeout=180,
                        env=environment
                        | {
                            "WEB_QA_ORIGIN": f"http://127.0.0.1:{port}",
                            "WEB_QA_ENV_FILE": str(private / "server.env"),
                            "WEB_QA_ACCOUNT": "judge",
                            "WEB_QA_RUN_SIM": "1",
                            "WEB_QA_ROUTE": server_config.REMOTE_ROUTE_ID,
                        },
                        stdout=browser_log,
                        stderr=subprocess.STDOUT,
                    )
                report["checks"].append(
                    "real judge browser selected the configured route, completed MuJoCo and decoded the uploaded video"
                )
            task_id = create()
            link.disconnect()
            wait_for(
                lambda: not client.get("/api/v1/capabilities").json()["remote"]["online"],
                "heartbeat offline",
                server_config.REMOTE_OFFLINE_SECONDS + 5,
            )
            stale = view(task_id)
            assert stale["state"] == "NAVIGATING" and stale["remote_pending"]
            assert client.get("/api/v1/tasks").status_code == 200
            rejected = client.post(
                "/api/v1/tasks",
                json={
                    "mode": "simulation",
                    "simulation_route_id": server_config.REMOTE_ROUTE_ID,
                },
            )
            assert rejected.status_code == 503
            assert rejected.json()["detail"]["code"] == "EXECUTOR_OFFLINE"
            local = wait_for(lambda: local_finished(task_id), "offline simulation completes")
            assert local["state"] == "SUCCEEDED"
            original = run / "executor/tasks" / task_id / "simulation.mp4"
            checksum = hashlib.sha256(original.read_bytes()).hexdigest()
            link.connected = True
            delivered = wait_for(
                lambda: finished(task_id), "reconnect delivers original recording", 30
            )
            assert delivered["state"] == "SUCCEEDED"
            archived = client.get(f"/api/v1/tasks/{task_id}/video")
            assert archived.status_code == 200
            assert hashlib.sha256(archived.content).hexdigest() == checksum
            record("outage_recovery", task_id, delivered)
            report["tasks"]["outage_recovery"]["video_sha256"] = checksum
            report["checks"].append(
                "cut TCP link: local completion, offline rejection, history readable, exact original MP4 delivered without re-execution"
            )
            print(
                "Passed real simulation with a cut TCP link and checksum-verified recovery.",
                flush=True,
            )

            task_id = create()
            cancelled = client.post(f"/api/v1/tasks/{task_id}/cancel")
            assert cancelled.status_code == 200
            delivered = wait_for(lambda: finished(task_id), "confirmed remote cancellation", 30)
            assert delivered["state"] == "CANCELLED" and not delivered["video_available"]
            record("remote_cancel", task_id, delivered)
            report["checks"].append(
                "remote cancellation waits for executor cleanup; incomplete recording is not exposed"
            )

            task_id = create()
            stop(agent)
            assert agent.returncode == 0
            delivered = wait_for(lambda: finished(task_id), "operator shutdown cancellation", 10)
            assert delivered["state"] == "CANCELLED"
            record("operator_shutdown", task_id, delivered)
            assert native.capabilities()["local_suspended"] is False
            assert client.get("/api/v1/capabilities").json()["remote"]["online"] is False
            assert all(
                not alive(read_object(path))
                for path in (run / "executor/tasks").glob("*/process.json")
            )
            report["checks"].append(
                "operator SIGTERM cancels, delivers confirmation, disconnects and restores local admission; no surviving workers"
            )
            if args.check_timeout:
                timeout_port = free_port()
                timeout_log = resources.enter_context((run / "timeout-server.log").open("wb"))
                timeout_server = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "uvicorn",
                        "app.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(timeout_port),
                        "--workers",
                        "1",
                    ],
                    cwd=BACKEND_ROOT,
                    env=environment
                    | {
                        "CAMPUS_ENV_FILE": str(private / "executor.env"),
                        "APP_DATA_DIR": str(run / "local-timeout"),
                        "TASK_TIMEOUT_SECONDS": "6",
                        "REMOTE_ENABLED": "false",
                    },
                    stdout=timeout_log,
                    stderr=subprocess.STDOUT,
                )
                with httpx.Client(
                    base_url=f"http://127.0.0.1:{timeout_port}", timeout=5, trust_env=False
                ) as short:
                    wait_for(lambda: short.get("/healthz").status_code == 200, "timeout server", 15)
                    login = short.post(
                        "/api/v1/login/access-token",
                        data={
                            "username": executor_config.FIRST_SUPERUSER,
                            "password": executor_config.FIRST_SUPERUSER_PASSWORD,
                        },
                    )
                    login.raise_for_status()
                    short.headers["Authorization"] = "Bearer " + login.json()["access_token"]
                    created = short.post(
                        "/api/v1/tasks",
                        json={
                            "mode": "simulation",
                            "simulation_route_id": server_config.REMOTE_ROUTE_ID,
                        },
                    )
                    assert created.status_code == 202
                    timeout_id = created.json()["task_id"]

                    def expired():
                        task = short.get(f"/api/v1/tasks/{timeout_id}").json()
                        return (
                            task
                            if task["state"] == "TIMED_OUT" and not task["worker_alive"]
                            else None
                        )

                    task = wait_for(expired, "real local simulation timeout", 25)
                    directory = run / "local-timeout/tasks" / timeout_id
                    progress = [
                        json.loads(line)
                        for line in (directory / "simulation.jsonl").read_text().splitlines()
                    ]
                    assert progress[-1]["step"] > 0
                    assert not task["video_available"] and task["error"]["code"] == "TASK_TIMEOUT"
                    report["tasks"]["local_timeout"] = {
                        "task_id": timeout_id,
                        "state": task["state"],
                        "last_simulation_step": progress[-1]["step"],
                        "video_available": False,
                        "worker_alive": False,
                    }
                    report["checks"].append(
                        "real MuJoCo made physical steps, exceeded a 6-second API deadline, cleaned up and did not expose incomplete video"
                    )
                stop(timeout_server)
            report["result"] = "passed"
    except BaseException as error:
        report["result"] = "failed"
        report["error_type"] = type(error).__name__
        raise
    finally:
        link.connected = True
        try:
            try:
                stop(timeout_server)
            finally:
                stop(agent)
        finally:
            stop(server)
            link.disconnect()
            link.shutdown()
            link.server_close()
            report["finished_at_utc"] = now()
            atomic_json(run / "report.json", report)
            print(
                f"Validation result: {report['result']}; private artifacts: {run.relative_to(REPO_ROOT)}",
                flush=True,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
