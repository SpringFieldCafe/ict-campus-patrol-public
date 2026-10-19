"""Offline evaluation contracts; tiny artificial PNGs and mock HTTP, never a model."""

import base64
import csv
import json
import os
import struct
import subprocess
import sys
import zlib
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from app.vision_eval import (
    DEFAULT_MANIFEST,
    REVIEW_FIELDS,
    ModelSettings,
    build_report,
    digest,
    load_manifest,
    main,
    run_evaluation,
)


def png_chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


# Valid 1x1 PNG for file/request tests, with no scene or recognition significance.
PNG = (
    b"\x89PNG\r\n\x1a\n"
    + png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    + png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
    + png_chunk(b"IEND", b"")
)
BACKEND = Path(__file__).resolve().parents[1]


def ready_manifest(tmp_path, count=1):
    (tmp_path / "image.png").write_bytes(PNG)
    value = {
        "schema_version": 1,
        "dataset_id": "artificial-test-only",
        "cases": [
            {
                "id": f"case-{index}",
                "status": "ready",
                "image": "image.png",
                "image_sha256": digest(PNG),
                "source": {
                    "description": "Artificial 1x1 test PNG",
                    "usage_permission": "Test only",
                },
                "question": "<script>alert('question')</script>",
                "reference_facts": ["reference-must-never-reach-model"],
                "unanswerable_points": ["No actual scene in this artificial test"],
            }
            for index in range(count)
        ],
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path, value


def save_manifest(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def review_all(directory, verdict="pass"):
    with (directory / "review.csv").open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    for row in rows:
        row.update(verdict=verdict, notes="<script>alert('notes')</script>")
    with (directory / "review.csv").open("w", encoding="utf-8-sig", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=REVIEW_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return rows


def test_clean_process_pending_workflow_requires_no_backend_configuration(tmp_path):
    # conftest initializes account config; a clean child proves the CLI does not depend on it.
    env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONIOENCODING": "utf-8",
        "CAMPUS_ENV_FILE": str(tmp_path / "absent.env"),
    }
    code = """
import socket, sys
def no_network(*args, **kwargs):
    raise AssertionError('Offline command attempted network access')
socket.socket.connect = no_network
socket.create_connection = no_network
from app.vision_eval import main
assert 'app.core.config' not in sys.modules
assert 'app.services.runtime' not in sys.modules
raise SystemExit(main(sys.argv[1:]))
"""
    for arguments in (
        ["--help"],
        ["check"],
        ["run", "--mock", "--output-dir", str(tmp_path / "pending-run")],
    ):
        completed = subprocess.run(
            [sys.executable, "-c", code, *arguments],
            cwd=BACKEND,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert completed.returncode == 0, completed.stderr
    results = json.loads((tmp_path / "pending-run/results.json").read_text())
    summary = json.loads((tmp_path / "pending-run/summary.json").read_text())
    assert results["status"] == "WAITING_FOR_IMAGES"
    assert all(item["state"] == "WAITING_FOR_IMAGE" for item in results["cases"])
    assert summary["real_model_attempts"] == summary["mock_attempts"] == 0
    assert summary["human_pass_rate_on_reviewed"] is None
    assert summary["model_effect_evaluated"] is False
    assert not (tmp_path / "pending-run/images").exists()


@pytest.mark.parametrize(
    "problem",
    ["missing_reference", "missing_source", "duplicate", "wrong_hash", "outside", "bad_encoding"],
)
def test_invalid_ready_cases_fail_preflight_without_creating_run(tmp_path, problem):
    path, value = ready_manifest(tmp_path)
    case = value["cases"][0]
    if problem == "missing_reference":
        case["reference_facts"] = case["unanswerable_points"] = []
    elif problem == "missing_source":
        case["source"]["usage_permission"] = ""
    elif problem == "duplicate":
        value["cases"].append(dict(case))
    elif problem == "wrong_hash":
        case["image_sha256"] = "0" * 64
    elif problem == "outside":
        case["image"] = "../outside.png"
    else:
        content = b"not-an-image"
        (tmp_path / "image.png").write_bytes(content)
        case["image_sha256"] = digest(content)
    save_manifest(path, value)
    with pytest.raises((ValueError, ValidationError)):
        run_evaluation(path, tmp_path / "rejected", mode="mock")
    assert not (tmp_path / "rejected").exists()


def test_mock_response_keeps_image_snapshot_and_never_becomes_model_score(tmp_path):
    path, _ = ready_manifest(tmp_path)
    directory = tmp_path / "mock-run"
    summary = run_evaluation(path, directory, mode="mock")
    results = json.loads((directory / "results.json").read_text())
    item = results["cases"][0]
    assert item["response"]["provider"] == "workflow_mock"
    assert (directory / item["image_file"]).read_bytes() == PNG
    assert summary["mock_attempts"] == 1 and summary["real_model_attempts"] == 0
    review_all(directory)
    summary = build_report(directory)
    assert summary["human_reviewed"] == 0
    assert summary["human_pass_rate_on_reviewed"] is None
    assert summary["model_effect_evaluated"] is False
    document = (directory / "report.html").read_text()
    assert "<script>" not in document and "&lt;script&gt;" in document
    assert "流程替身" in document
    with pytest.raises(FileExistsError):
        run_evaluation(path, directory, mode="mock")
    (directory / item["image_file"]).write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA256"):
        build_report(directory)


def test_live_error_retention_review_coverage_and_no_reference_leak(tmp_path):
    path, _ = ready_manifest(tmp_path, count=3)
    settings = ModelSettings(
        HUAWEI_CHAT_COMPLETIONS_URL="https://example.invalid/v1/chat/completions",
        HUAWEI_MODEL="artificial-model",
        HUAWEI_API_KEY="private-test-secret",
    )
    requests = []

    def respond(request):
        requests.append(request)
        body = json.loads(request.content)
        assert body["model"] == "artificial-model"
        text, image = body["messages"][0]["content"]
        assert text["text"] == "<script>alert('question')</script>"
        assert base64.b64decode(image["image_url"]["url"].split(",", 1)[1]) == PNG
        assert "reference-must-never-reach-model" not in request.content.decode()
        if len(requests) == 1:
            raise httpx.ReadTimeout("artificial timeout")
        if len(requests) == 2:
            return httpx.Response(429)
        return httpx.Response(
            200,
            json={
                "id": "artificial-request",
                "choices": [{"message": {"content": "<script>answer</script>"}}],
            },
        )

    directory = tmp_path / "live-protocol-test"
    summary = run_evaluation(
        path,
        directory,
        mode="live",
        settings=settings,
        transport=httpx.MockTransport(respond),
    )
    assert len(requests) == 3  # Exactly once per case, including failures.
    assert summary["failed"] == 2 and summary["responded"] == 1
    assert summary["unreviewed_responses"] == 1
    assert summary["human_pass_rate_on_reviewed"] is None
    results = json.loads((directory / "results.json").read_text())
    assert [row["error"]["code"] for row in results["cases"][:2]] == [
        "MODEL_TIMEOUT",
        "MODEL_REQUEST_FAILED",
    ]
    rows = review_all(directory)
    assert len(rows) == 1 and rows[0]["case_id"] == "case-2"
    summary = build_report(directory)
    assert summary["human_reviewed"] == 1 and summary["human_passed"] == 1
    assert summary["human_pass_rate_on_reviewed"] == 1.0
    assert summary["failed"] == 2  # Not hidden by the reviewed-only pass rate.
    assert "private-test-secret" not in (directory / "results.json").read_text()
    assert "private-test-secret" not in (directory / "report.html").read_text()
    assert "<script>" not in (directory / "report.html").read_text()
    assert (directory / "results.json").stat().st_mode & 0o077 == 0
    with (directory / "review.csv").open("a", encoding="utf-8", newline="") as output:
        csv.DictWriter(output, fieldnames=REVIEW_FIELDS).writerow(rows[0])
    with pytest.raises(ValueError, match="review row"):
        build_report(directory)


def test_review_rejects_scores_from_a_different_case_snapshot(tmp_path):
    path, _ = ready_manifest(tmp_path)
    directory = tmp_path / "review-run"
    run_evaluation(path, directory, mode="mock")
    review = (directory / "review.csv").read_text(encoding="utf-8-sig")
    results = json.loads((directory / "results.json").read_text())
    original = results["cases"][0]["case_sha256"]
    (directory / "review.csv").write_text(review.replace(original, "0" * 64), encoding="utf-8-sig")
    with pytest.raises(ValueError, match="review row"):
        build_report(directory)


def test_live_requires_images_and_explicit_valid_settings(tmp_path, monkeypatch, capsys):
    directory = tmp_path / "no-run"
    assert main(["run", "--live", "--output-dir", str(directory)]) == 2
    assert "WAITING_FOR_IMAGES" in capsys.readouterr().err
    path, _ = ready_manifest(tmp_path)
    for variable in ("HUAWEI_CHAT_COMPLETIONS_URL", "HUAWEI_MODEL", "HUAWEI_API_KEY"):
        monkeypatch.delenv(variable, raising=False)
    assert main(["run", "--live", "--manifest", str(path), "--output-dir", str(directory)]) == 2
    assert not directory.exists()
    env_file = tmp_path / "model.env"
    env_file.write_text("HUAWEI_API_KEY=private-test-secret\nHUAWEI_TIMEOUT_SECONDS=invalid\n")
    assert main(["run", "--live", "--manifest", str(path), "--env-file", str(env_file)]) == 2
    assert "private-test-secret" not in capsys.readouterr().err


def test_default_template_is_explicitly_pending():
    manifest, images = load_manifest(DEFAULT_MANIFEST)
    assert len(manifest.cases) == 3 and not images
    assert all(not case.reference_facts and not case.unanswerable_points for case in manifest.cases)
