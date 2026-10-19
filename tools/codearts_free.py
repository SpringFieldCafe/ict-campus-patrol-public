"""Local CodeArts 26.9.26 welfare integration, not an official CLI entitlement interface.

Uses only benefit-model/glm-5.3-flash. No paid-model fallback, purchases, tool
execution or permanent config edits. Requires the user's existing CLI AK/SK.
"""

import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import re
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MODEL = "benefit-model/glm-5.3-flash"
PROBE = "只回复 FREE_BENEFIT_OK，不要调用工具。"
NATIVE_SHA256 = "d0600f85f7483931e762f98075f84673aca133d56719c6af1c56be9107375dfb"


def benefit_environment():
    env = os.environ.copy()
    missing = [
        name for name in ("CODEARTS_CLI_AK", "CODEARTS_CLI_SK") if not env.get(name)
    ]
    if missing:
        raise ValueError(
            "Missing existing CLI credential variables: " + ", ".join(missing)
        )
    # Use the native executable without the launcher's TLS override or inherited model overrides.
    env.pop("NODE_TLS_REJECT_UNAUTHORIZED", None)
    env.update(
        {
            "SCENARIO": "codeartsdoer",
            "PLUGIN_ENV": "hc",
            "OPENCODE_MODE": "cli",
            "KERNEL_ACP": "acp",
            "CODEARTS_ENV": "ai-devSpace",
            "KERNEL_DATA_DIR": str(Path.home() / ".codeartsdoer/cli-data"),
            "KERNEL_CONFIG_DIR": str(Path.home() / ".codeartsdoer"),
            "OPENCODE_CONFIG": str(Path.home() / ".codeartsdoer/codearts_cli.json"),
            "OPENCODE_CONFIG_FILE": "codearts_cli.json,codearts_cli.jsonc",
            "OPENCODE_DISABLE_MODELS_FETCH": "1",
            "OPENCODE_DISABLE_AUTOUPDATE": "true",
        }
    )
    env["OPENCODE_CONFIG_CONTENT"] = json.dumps(
        {
            "model": MODEL,
            "small_model": MODEL,
            "permission": {"*": "deny"},
            "provider": {
                "benefit-model": {
                    "models": {
                        "glm-5.3-flash": {"headers": {"maas_type": "benefit"}},
                    }
                }
            },
        }
    )
    return env


def sanitizer(env):
    values = [
        value
        for key, value in env.items()
        if len(value) >= 8
        and any(
            part in key.upper()
            for part in (
                "SECRET",
                "TOKEN",
                "PASSWORD",
                "API_KEY",
                "CODEARTS_CLI_AK",
                "CODEARTS_CLI_SK",
            )
        )
    ]

    def clean(text):
        for value in sorted(values, key=len, reverse=True):
            text = text.replace(value, "[REDACTED]")
        text = text.replace(str(REPO), "LOCAL_REPOSITORY").replace(
            str(Path.home()), "LOCAL_HOME"
        )
        return re.sub(r"(?i)Bearer\s+[A-Za-z0-9._~+/-]{16,}", "Bearer [REDACTED]", text)

    return clean


def execute(prompt, attachments=(), timeout=180):
    env = benefit_environment()
    clean = sanitizer(env)
    binary = Path.home() / ".codeartsdoer/installers/bin/codearts"
    if not binary.is_file() or not os.access(binary, os.X_OK):
        raise ValueError(
            "CodeArts native CLI is missing; this helper does not install or upgrade it"
        )
    binary_hash = hashlib.sha256(binary.read_bytes()).hexdigest()
    if binary_hash != NATIVE_SHA256:
        raise ValueError(
            "Native CLI differs from verified 26.9.26; revalidate welfare routing first"
        )
    sources = []
    for name in attachments:
        path = (Path.cwd() / name).resolve()
        if (
            not path.is_relative_to(REPO)
            or any(
                part
                in {".local", ".git", ".venv", "node_modules", "private", "secrets"}
                for part in path.relative_to(REPO).parts
            )
            or path.name.startswith((".env", "credentials"))
            or path.suffix
            not in {".md", ".py", ".ts", ".vue", ".json", ".toml", ".sh", ".txt"}
        ):
            raise ValueError(
                "Attachment must be selected public text within the repository"
            )
        if path.stat().st_size > 120_000:
            raise ValueError("Attachment exceeds 120 KB")
        body = path.read_text(encoding="utf-8")
        if "\x00" in body:
            raise ValueError("Binary attachment refused")
        sources.append((str(path.relative_to(REPO)), clean(body)))
    if sum(len(body) for _, body in sources) > 300_000:
        raise ValueError("Attachment set is too large")
    output = (
        REPO
        / ".local/codearts/free-cli"
        / (
            dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + "-"
            + uuid.uuid4().hex[:8]
        )
    )
    output.mkdir(parents=True, mode=0o700)
    sandbox = output / "sandbox"
    sandbox.mkdir(mode=0o700)

    def write(name, text):
        path = output / name
        path.write_text(clean(text), encoding="utf-8")
        path.chmod(0o600)

    files, hashes = [], {}
    for index, (name, body) in enumerate(sources):
        path = sandbox / (f"{index:02d}-" + Path(name).name)
        path.write_text(f"Source: {name}\n\n{body}", encoding="utf-8")
        path.chmod(0o600)
        files.append(str(path))
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    prompt = clean(prompt)
    write("request.md", prompt + "\n")
    argv = [
        str(binary),
        "run",
        prompt,
        "--pure",
        "--model",
        MODEL,
        "--format",
        "json",
        "--title",
        "Local free-benefit task",
    ]
    if files:
        argv.extend(["--file", *files])
    started = time.monotonic()
    started_utc = dt.datetime.now(dt.timezone.utc).isoformat()
    process = subprocess.Popen(
        argv,
        cwd=sandbox,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        timed_out = isinstance(error, subprocess.TimeoutExpired)
        os.killpg(process.pid, signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
    stdout, stderr = clean(stdout), clean(stderr)
    write("events.jsonl", stdout)
    write("stderr.txt", stderr)
    events = []
    for line in stdout.splitlines():
        try:
            value = json.loads(line)
            if isinstance(value, dict):
                events.append(value)
        except json.JSONDecodeError:
            pass
    counts = collections.Counter(event.get("type", "unknown") for event in events)
    response = "\n\n".join(
        event.get("part", {}).get("text", "")
        for event in events
        if event.get("type") == "text"
    ).strip()
    write("response.md", response + "\n" if response else "")
    steps = [
        event.get("part", {}) for event in events if event.get("type") == "step_finish"
    ]
    # A zero exit code alone is insufficient: the native CLI may emit an error event.
    success = (
        bool(response)
        and process.returncode == 0
        and not timed_out
        and not counts["error"]
    )
    receipt = {
        "status": "response_received" if success else "failed",
        "provider_model": MODEL,
        "started_utc": started_utc,
        "finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "duration_seconds": round(time.monotonic() - started, 2),
        "returncode": process.returncode,
        "timed_out": timed_out,
        "event_counts": dict(counts),
        "response_characters": len(response),
        "reported_cost_sum": sum(step.get("cost", 0) for step in steps),
        "reported_tokens": [step.get("tokens", {}) for step in steps],
        "codearts_native_binary_sha256": binary_hash,
        "sanitized_attachment_sha256": hashes,
        "requested_permission": {"*": "deny"},
        "execution_mode": "Local native-kernel integration; ordinary launcher and permanent config unchanged",
        "billing_note": "Benefit provider/header only; event cost is not an account billing receipt",
        "artifact_sha256": {
            name: hashlib.sha256((output / name).read_bytes()).hexdigest()
            for name in ("request.md", "events.jsonl", "stderr.txt", "response.md")
        },
    }
    write("receipt.json", json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    return response, output, receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    prompts = parser.add_mutually_exclusive_group(required=True)
    prompts.add_argument(
        "prompt", nargs="?", help="Text question or request; tools are disabled"
    )
    prompts.add_argument("--prompt-file", type=Path, help="UTF-8 request file")
    prompts.add_argument(
        "--probe", action="store_true", help="Minimal real welfare request"
    )
    parser.add_argument(
        "--file",
        action="append",
        default=[],
        help="Selected public repository text; repeatable",
    )
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args(argv)
    if not 1 <= args.timeout <= 300:
        parser.error("timeout must be in 1..300 seconds")
    try:
        prompt = (
            PROBE
            if args.probe
            else args.prompt_file.read_text(encoding="utf-8")
            if args.prompt_file
            else args.prompt
        )
        if not prompt or not prompt.strip() or len(prompt) > 30_000:
            raise ValueError("Request must contain 1..30000 characters")
        response, output, receipt = execute(prompt, args.file, args.timeout)
        print(
            json.dumps(
                {
                    "status": receipt["status"],
                    "provider_model": MODEL,
                    "record": str(output.relative_to(REPO)),
                },
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        if response:
            print(response)
        if receipt["status"] != "response_received" or (
            args.probe and response != "FREE_BENEFIT_OK"
        ):
            print(
                "福利请求未成功；没有切换到付费模型。请检查当天领取状态及本次私有记录。",
                file=sys.stderr,
            )
            return 1
        return 0
    except (OSError, ValueError) as error:
        print(f"CodeArts welfare helper: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
