"""No model calls: verify exclusive welfare routing and truthful local receipts."""

import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location(
    "codearts_free", Path(__file__).parents[1] / "codearts_free.py"
)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


class WelfareHelperTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.home = self.root / "user"
        binary = self.home / ".codeartsdoer/installers/bin/codearts"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"artificial-native-test-fixture")
        binary.chmod(0o700)
        self.binary = binary
        for active in (
            patch.object(helper, "REPO", self.repo),
            patch.object(
                helper, "NATIVE_SHA256", hashlib.sha256(binary.read_bytes()).hexdigest()
            ),
            patch.object(Path, "home", return_value=self.home),
            patch.dict(
                os.environ,
                {
                    "CODEARTS_CLI_AK": "synthetic-access-key",
                    "CODEARTS_CLI_SK": "synthetic-secret-key",
                    "NODE_TLS_REJECT_UNAUTHORIZED": "0",
                    "OPENCODE_CONFIG_CONTENT": '{"model":"ordinary-paid-model"}',
                },
                clear=True,
            ),
        ):
            active.start()
            self.addCleanup(active.stop)

    def test_error_event_with_zero_exit_code_is_failure_without_fallback(self):
        process = Mock(returncode=0)
        process.communicate.return_value = (
            json.dumps({"type": "error", "error": {"message": "No welfare quota"}}),
            "",
        )
        with patch.object(helper.subprocess, "Popen", return_value=process) as start:
            answer, directory, receipt = helper.execute("test")
        start.assert_called_once()
        command = start.call_args.args[0]
        self.assertEqual(command[command.index("--model") + 1], helper.MODEL)
        env = start.call_args.kwargs["env"]
        config = json.loads(env["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual(config["model"], helper.MODEL)
        self.assertEqual(config["small_model"], helper.MODEL)
        self.assertEqual(
            config["provider"]["benefit-model"]["models"]["glm-5.3-flash"]["headers"],
            {"maas_type": "benefit"},
        )
        self.assertNotIn("NODE_TLS_REJECT_UNAUTHORIZED", env)
        self.assertEqual(answer, "")
        self.assertEqual(receipt["status"], "failed")
        self.assertTrue((directory / "receipt.json").is_file())

    def test_unknown_native_version_is_refused_before_any_request(self):
        self.binary.write_bytes(b"changed-version")
        with patch.object(helper.subprocess, "Popen") as start:
            with self.assertRaisesRegex(ValueError, "differs from verified"):
                helper.execute("test")
        start.assert_not_called()

    def test_missing_credentials_are_reported_without_request(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(helper.subprocess, "Popen") as start,
        ):
            with self.assertRaisesRegex(ValueError, "CODEARTS_CLI_AK"):
                helper.execute("test")
        start.assert_not_called()

    def test_response_and_attachments_are_recorded_with_secrets_redacted(self):
        source = self.repo / "public.md"
        source.write_text("public source", encoding="utf-8")
        process = Mock(returncode=0)
        process.communicate.return_value = (
            json.dumps(
                {"type": "text", "part": {"text": "answer synthetic-secret-key"}}
            )
            + "\n"
            + json.dumps(
                {"type": "step_finish", "part": {"cost": 0, "tokens": {"total": 9}}}
            ),
            "synthetic-access-key",
        )
        with patch.object(helper.subprocess, "Popen", return_value=process):
            answer, directory, receipt = helper.execute("test", [str(source)])
        self.assertEqual(answer, "answer [REDACTED]")
        self.assertEqual(receipt["status"], "response_received")
        self.assertEqual(receipt["reported_cost_sum"], 0)
        self.assertIn("public.md", receipt["sanitized_attachment_sha256"])
        self.assertEqual((directory / "events.jsonl").stat().st_mode & 0o077, 0)
        for path in directory.iterdir():
            if path.is_file():
                self.assertNotIn("synthetic-secret-key", path.read_text())
                self.assertNotIn("synthetic-access-key", path.read_text())

    def test_credential_attachment_is_refused(self):
        source = self.repo / ".env"
        source.write_text("private", encoding="utf-8")
        with patch.object(helper.subprocess, "Popen") as start:
            with self.assertRaisesRegex(ValueError, "public text"):
                helper.execute("test", [str(source)])
        start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
