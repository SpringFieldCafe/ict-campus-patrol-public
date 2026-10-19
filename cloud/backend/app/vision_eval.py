"""Small offline image-Q&A evaluation; no task API, camera or account initialization."""

import argparse
import csv
import hashlib
import html
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.services import huawei
from app.services.store import ServiceError, atomic_json, now, read_object

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_MANIFEST = REPO_ROOT / "evaluation/vision/manifest.example.json"
DEFAULT_RUNS = REPO_ROOT / ".local/vision-eval/runs"
REVIEW_FIELDS = ["case_id", "case_sha256", "verdict", "notes"]
MAX_IMAGE_BYTES = 10 * 1024 * 1024


class Source(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    description: str = ""
    usage_permission: str = ""


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    status: Literal["pending", "ready"]
    capture_notes: str = ""
    image: str | None = None
    image_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    source: Source
    question: str = Field(min_length=1, max_length=2000)
    reference_facts: list[str] = Field(default_factory=list)
    unanswerable_points: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def ready_requires_evidence(self) -> Self:
        if not self.question.strip():
            raise ValueError("Question must not be blank")
        if any(not text.strip() for text in self.reference_facts + self.unanswerable_points):
            raise ValueError("Reference entries must not be blank")
        if self.status == "ready" and not (
            self.image
            and self.image_sha256
            and self.source.description.strip()
            and self.source.usage_permission.strip()
            and (self.reference_facts or self.unanswerable_points)
        ):
            raise ValueError(
                "Ready cases need image/hash, source/permission and reference criteria"
            )
        return self


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal[1]
    dataset_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    cases: list[Case]

    @model_validator(mode="after")
    def unique_cases(self) -> Self:
        if len({case.id for case in self.cases}) != len(self.cases):
            raise ValueError("Duplicate case ID")
        return self


class ModelSettings(BaseSettings):
    """Only model settings; dotenv loading requires an explicit --env-file."""

    model_config = SettingsConfigDict(extra="ignore", env_ignore_empty=True)
    HUAWEI_CHAT_COMPLETIONS_URL: str
    HUAWEI_MODEL: str = Field(min_length=1)
    HUAWEI_API_KEY: SecretStr = Field(min_length=1)
    HUAWEI_TIMEOUT_SECONDS: float = Field(default=45, gt=0, le=120)

    @property
    def huawei_configured(self) -> bool:
        return True

    @model_validator(mode="after")
    def valid_endpoint(self) -> Self:
        parsed = urlparse(self.HUAWEI_CHAT_COMPLETIONS_URL)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or not self.HUAWEI_MODEL.strip()
            or not self.HUAWEI_API_KEY.get_secret_value().strip()
        ):
            raise ValueError("Model configuration is incomplete or invalid")
        return self


def digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def load_manifest(path: Path) -> tuple[Manifest, dict[str, tuple[bytes, str]]]:
    manifest = Manifest.model_validate(read_object(path))
    images = {}
    root = path.resolve().parent
    # Validate every ready case before the first request; pending cases stay empty.
    for case in manifest.cases:
        if case.status == "pending":
            continue
        relative = Path(case.image)
        image = (root / relative).resolve()
        if relative.is_absolute() or not image.is_relative_to(root):
            raise ValueError(f"{case.id}: image must stay inside the manifest directory")
        if image.stat().st_size > MAX_IMAGE_BYTES:
            raise ValueError(f"{case.id}: image exceeds 10 MiB")
        content = image.read_bytes()
        if digest(content) != case.image_sha256:
            raise ValueError(f"{case.id}: image SHA256 mismatch")
        mime = (
            "image/png"
            if content.startswith(b"\x89PNG\r\n\x1a\n")
            else "image/jpeg"
            if content.startswith(b"\xff\xd8\xff")
            else None
        )
        if not mime:
            raise ValueError(f"{case.id}: expected PNG or JPEG")
        images[case.id] = content, mime
    return manifest, images


def case_digest(case: dict) -> str:
    return digest(json.dumps(case, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def write_review_template(directory: Path, results: dict) -> None:
    with (directory / "review.csv").open("x", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        for item in results["cases"]:
            if item["state"] == "RESPONDED":
                writer.writerow({"case_id": item["case"]["id"], "case_sha256": item["case_sha256"]})


def read_reviews(directory: Path, results: dict) -> dict:
    expected = {
        item["case"]["id"]: item["case_sha256"]
        for item in results["cases"]
        if item["state"] == "RESPONDED"
    }
    reviews = {}
    with (directory / "review.csv").open(encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != REVIEW_FIELDS:
            raise ValueError("Unexpected review.csv columns")
        for row in reader:
            identifier = row["case_id"]
            if (
                identifier not in expected
                or identifier in reviews
                or row["case_sha256"] != expected[identifier]
                or row["verdict"] not in {"", "pass", "fail"}
                or row.get(None) is not None
                or row["notes"] is None
            ):
                raise ValueError("Invalid, duplicate or mismatched review row")
            reviews[identifier] = row
    return reviews


def build_report(directory: Path) -> dict:
    results = read_object(directory / "results.json")
    if results.get("schema_version") != 1 or results.get("mode") not in {"mock", "live"}:
        raise ValueError("Invalid result schema or mode")
    for item in results["cases"]:
        if case_digest(item["case"]) != item["case_sha256"]:
            raise ValueError("Result case snapshot SHA256 mismatch")
    reviews = read_reviews(directory, results)
    real = results["mode"] == "live"
    responded = sum(item["state"] == "RESPONDED" for item in results["cases"])
    reviewed = sum(bool(row["verdict"]) for row in reviews.values()) if real else 0
    passed = sum(row["verdict"] == "pass" for row in reviews.values()) if real else 0
    summary = {
        "status": results["status"],
        "mode": results["mode"],
        "total": len(results["cases"]),
        "pending": sum(item["state"] == "WAITING_FOR_IMAGE" for item in results["cases"]),
        "responded": responded,
        "failed": sum(item["state"] == "FAILED" for item in results["cases"]),
        "real_model_attempts": sum(item["attempted"] for item in results["cases"]) if real else 0,
        "mock_attempts": sum(item["attempted"] for item in results["cases"]) if not real else 0,
        "human_reviewed": reviewed,
        "human_passed": passed,
        "unreviewed_responses": responded - reviewed if real else 0,
        "human_pass_rate_on_reviewed": passed / reviewed if reviewed else None,
        "model_effect_evaluated": real and reviewed > 0,
    }

    def escape(value):
        return html.escape(str(value), quote=True)

    sections = []
    for item in results["cases"]:
        case = item["case"]
        picture = ""
        if item.get("image_file"):
            # Reports keep the exact image bytes sent, independently of later dataset changes.
            relative = item["image_file"]
            if not re.fullmatch(r"images/[A-Za-z0-9_-]{1,80}\.(png|jpg)", relative):
                raise ValueError("Invalid report image path")
            image = (directory / relative).resolve()
            if (
                not image.is_relative_to(directory.resolve())
                or digest(image.read_bytes()) != case["image_sha256"]
            ):
                raise ValueError("Report image SHA256 mismatch")
            picture = f'<img src="{escape(relative)}" alt="{escape(case["id"])}">'
        row = reviews.get(case["id"], {})
        facts = "\n".join(case["reference_facts"]) or "待填写"
        limits = "\n".join(case["unanswerable_points"]) or "未单列"
        answer = item.get("response", {}).get("answer", "尚无回答")
        sections.append(
            f"<section><h2>{escape(case['id'])}</h2><p>{escape(item['state'])}</p>{picture}"
            f"<p>来源：{escape(case['source']['description'] or '待补充')}</p>"
            f"<p>使用依据：{escape(case['source']['usage_permission'] or '待补充')}</p>"
            f"<h3>问题</h3><pre>{escape(case['question'])}</pre>"
            f"<h3>参考事实</h3><pre>{escape(facts)}</pre>"
            f"<h3>无法判断的内容</h3><pre>{escape(limits)}</pre>"
            f"<h3>原始回答</h3><pre>{escape(answer)}</pre>"
            f"<p>核对：{escape(row.get('verdict') or '未核对')} {escape(row.get('notes', ''))}</p>"
            f"<pre>{escape(json.dumps(item.get('error'), ensure_ascii=False)) if item.get('error') else ''}</pre></section>"
        )
    banner = (
        "流程替身运行：所有回答均为固定测试文本，不计入模型效果或人工通过率。"
        if not real
        else "真实模型运行：通过率仅计算已人工核对的回答；请求失败与未核对数量单列。"
    )
    rate = summary["human_pass_rate_on_reviewed"]
    rate_text = f"{rate:.1%}" if rate is not None else "未评测"
    document = (
        '<!doctype html><html lang="zh-CN"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        "<title>离线视觉评测</title><style>body{font:16px sans-serif;max-width:960px;"
        "margin:32px auto;padding:0 20px}section{border-top:1px solid #ccc;margin-top:24px}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere}img{max-width:100%;max-height:420px}"
        ".banner{background:#fff0bf;padding:16px}</style>"
        f"<h1>离线视觉评测：{escape(results['dataset_id'])}</h1>"
        f'<p class="banner">{escape(banner)}</p>'
        "<p>这是独立图片问答评测，不作为机器人到点采图或实机闭环证据。</p>"
        f"<p>清单条目：{summary['total']}；待补图条目：{summary['pending']}；"
        f"收到回答：{responded}；请求失败：{summary['failed']}。</p>"
        f"<p>已人工核对：{reviewed}；通过：{passed}；已核对回答通过率：{rate_text}。</p>"
        f"<pre>{escape(json.dumps(summary, ensure_ascii=False, indent=2))}</pre>"
        "<p>编辑本目录 review.csv 的 verdict（pass/fail）与 notes，再运行 report 更新。</p>"
        + "".join(sections)
        + "</html>"
    )
    atomic_json(directory / "summary.json", summary)
    (directory / "report.html").write_text(document, encoding="utf-8")
    return summary


def run_evaluation(
    manifest_path: Path,
    directory: Path,
    *,
    mode: Literal["mock", "live"],
    settings: ModelSettings | None = None,
    transport: httpx.BaseTransport | None = None,
) -> dict:
    manifest, images = load_manifest(manifest_path)
    if mode == "live" and (not images or settings is None):
        raise ValueError("Live run requires ready images and explicit model configuration")
    if mode == "mock":
        settings = ModelSettings(
            HUAWEI_CHAT_COMPLETIONS_URL="https://workflow.invalid/v1/chat/completions",
            HUAWEI_MODEL="workflow-only",
            HUAWEI_API_KEY="workflow-only",
            HUAWEI_TIMEOUT_SECONDS=45,
        )
        transport = httpx.MockTransport(
            lambda _: httpx.Response(
                200,
                json={
                    "id": "workflow-only",
                    "choices": [
                        {
                            "message": {
                                "content": "【流程替身】此固定文本只验证调用和记录流程，没有进行图片识别。"
                            }
                        }
                    ],
                },
            )
        )
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    results = {
        "schema_version": 1,
        "dataset_id": manifest.dataset_id,
        "mode": mode,
        "model": settings.HUAWEI_MODEL,
        "request_options": {
            "stream": False,
            "max_tokens": 1024,
            "timeout_seconds": settings.HUAWEI_TIMEOUT_SECONDS,
        },
        "started_at_utc": now(),
        "finished_at_utc": None,
        "status": "RUNNING",
        "cases": [],
    }
    atomic_json(directory / "results.json", results)
    for case in manifest.cases:
        snapshot = case.model_dump()
        item = {
            "case": snapshot,
            "case_sha256": case_digest(snapshot),
            "state": "WAITING_FOR_IMAGE",
            "attempted": False,
        }
        results["cases"].append(item)
        if case.id in images:
            content, mime = images[case.id]
            (directory / "images").mkdir(mode=0o700, exist_ok=True)
            extension = "png" if mime == "image/png" else "jpg"
            item["image_file"] = f"images/{case.id}.{extension}"
            (directory / item["image_file"]).write_bytes(content)
            item.update(attempted=True, state="REQUESTING")
            atomic_json(directory / "results.json", results)
            started = time.monotonic()
            try:
                # References are saved for review, never sent to the model.
                response = huawei.ask_image(settings, content, mime, case.question, transport)
                if mode == "mock":
                    response["provider"] = "workflow_mock"
                item.update(state="RESPONDED", response=response)
            except ServiceError as error:
                item.update(state="FAILED", error={"code": error.code, "message": error.message})
            item["elapsed_seconds"] = round(time.monotonic() - started, 4)
        atomic_json(directory / "results.json", results)
    results["status"] = "COMPLETED" if images else "WAITING_FOR_IMAGES"
    results["finished_at_utc"] = now()
    atomic_json(directory / "results.json", results)
    write_review_template(directory, results)
    return build_report(directory)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser(
        "check", help="Check manifest and image hashes; never calls a model"
    )
    check.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    run = commands.add_parser("run", help="Save answers and a report in a new private directory")
    run.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    mode = run.add_mutually_exclusive_group(required=True)
    mode.add_argument("--mock", action="store_true", help="Fixed workflow responses; no network")
    mode.add_argument(
        "--live", action="store_true", help="Explicit real model call; may incur charges"
    )
    run.add_argument("--env-file", type=Path, help="Explicit model dotenv file, only with --live")
    run.add_argument(
        "--output-dir", type=Path, help="New directory; existing paths are never overwritten"
    )
    report = commands.add_parser(
        "report", help="Refresh HTML/summary from results and manual review CSV"
    )
    report.add_argument("directory", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            manifest, images = load_manifest(args.manifest)
            print(
                json.dumps(
                    {
                        "status": "READY" if images else "WAITING_FOR_IMAGES",
                        "dataset_id": manifest.dataset_id,
                        "total": len(manifest.cases),
                        "ready": len(images),
                        "pending": len(manifest.cases) - len(images),
                        "model_effect_evaluated": False,
                    },
                    ensure_ascii=False,
                )
            )
            return 0
        if args.command == "report":
            summary = build_report(args.directory)
            directory = args.directory
        else:
            if args.mock and args.env_file:
                raise ValueError("--env-file is only accepted with --live")
            settings = None
            if args.live:
                _, images = load_manifest(args.manifest)
                if not images:
                    raise ValueError("WAITING_FOR_IMAGES: add ready images before a live run")
                if args.env_file and not args.env_file.is_file():
                    raise ValueError("Explicit model env file does not exist")
                try:
                    settings = ModelSettings(_env_file=args.env_file)
                except ValidationError:
                    raise ValueError(
                        "Model configuration is incomplete or invalid; check HUAWEI_* locally"
                    ) from None
            directory = args.output_dir or DEFAULT_RUNS / (
                now().replace(":", "-") + "-" + uuid.uuid4().hex[:8]
            )
            summary = run_evaluation(
                args.manifest,
                directory,
                mode="live" if args.live else "mock",
                settings=settings,
            )
        print(json.dumps({"directory": str(directory), **summary}, ensure_ascii=False))
        return 1 if summary["failed"] else 0
    except ValidationError as error:
        # No input values in diagnostics; dotenv validation may contain credentials.
        details = [".".join(map(str, item["loc"])) for item in error.errors(include_input=False)]
        print("Invalid manifest fields: " + ", ".join(details), file=sys.stderr)
    except (OSError, ValueError, KeyError) as error:
        print(f"Evaluation error: {error}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
