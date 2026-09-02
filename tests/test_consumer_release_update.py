"""Executable proof for the consumer-owned AEC release notifier."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "docs" / "consumer-kit" / "check_aec_release.py"
WORKFLOW = ROOT / "docs" / "consumer-kit" / "aec-release-notification.yml"
INSTALL_DOC = ROOT / "docs" / "consumer-kit" / "register-hook.md"


def release_manifest(revision: str = "b" * 40) -> dict[str, object]:
    return {
        "consumer_update": {
            "auto_merge_allowed": False,
            "compatibility": "validation-required",
            "required_probes": ["human-render", "material", "routine"],
        },
        "contracts": {
            "consumer_state": "1.0.0",
            "human_render": "1.5.0",
            "public_card": "3.0.0",
            "resolution_decision": "4.0.0",
            "resolution_request": "2.0.0",
            "workflow": "1.0.0",
        },
        "release": {
            "channel": "beta",
            "notes_url": "https://github.com/jasonewillis/AEC/releases/tag/v9.8.7",
            "published_at": "2026-09-02T17:00:00Z",
            "revision": revision,
            "tag": "v9.8.7",
            "version": "9.8.7",
        },
        "repository": "jasonewillis/AEC",
        "schema_version": "1.0.0",
    }


def run_checker(pin: str, manifest: object) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        pin_path = root / ".aec-pin"
        manifest_path = root / "aec-release-manifest.json"
        pin_path.write_text(pin + "\n", encoding="utf-8")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        return subprocess.run(
            [
                sys.executable,
                str(CHECKER),
                "--pin",
                str(pin_path),
                "--manifest",
                str(manifest_path),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )


def load_checker():
    spec = importlib.util.spec_from_file_location("consumer_release_check", CHECKER)
    if spec is None or spec.loader is None:
        raise AssertionError("consumer checker cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ConsumerReleaseCheckTests(unittest.TestCase):
    def test_cli_reports_current_and_update_available_as_closed_json(self) -> None:
        latest = "b" * 40
        current = run_checker(latest, release_manifest(latest))
        update = run_checker("a" * 40, release_manifest(latest))

        self.assertEqual(0, current.returncode, current.stderr)
        self.assertEqual(0, update.returncode, update.stderr)
        current_result = json.loads(current.stdout)
        update_result = json.loads(update.stdout)
        self.assertEqual("current", current_result["status"])
        self.assertEqual("update_available", update_result["status"])
        self.assertEqual(
            {
                "compatibility",
                "current_revision",
                "latest_revision",
                "latest_tag",
                "notification",
                "required_probes",
                "schema_version",
                "status",
            },
            set(update_result),
        )
        self.assertEqual("not_requested", update_result["notification"])
        self.assertEqual(latest, update_result["latest_revision"])
        self.assertEqual("v9.8.7", update_result["latest_tag"])

    def test_untrusted_manifest_and_floating_pin_fail_closed(self) -> None:
        cases: list[tuple[str, object]] = []
        unknown = release_manifest()
        unknown["surprise"] = True
        cases.append(("a" * 40, unknown))
        wrong_repository = release_manifest()
        wrong_repository["repository"] = "fork/AEC"
        cases.append(("a" * 40, wrong_repository))
        floating_release = release_manifest()
        floating_release["release"]["revision"] = "main"
        cases.append(("a" * 40, floating_release))
        auto_merge = release_manifest()
        auto_merge["consumer_update"]["auto_merge_allowed"] = True
        cases.append(("a" * 40, auto_merge))
        unknown_nested = release_manifest()
        unknown_nested["release"]["branch"] = "main"
        cases.append(("a" * 40, unknown_nested))
        malformed_time = release_manifest()
        malformed_time["release"]["published_at"] = "2026-09-02"
        cases.append(("a" * 40, malformed_time))
        cases.append(("main", release_manifest()))

        for pin, manifest in cases:
            with self.subTest(pin=pin, repository=manifest.get("repository")):
                result = run_checker(pin, manifest)
                self.assertEqual(1, result.returncode)
                self.assertEqual("", result.stdout)
                self.assertIn("aec update: FAIL:", result.stderr)

    def test_duplicate_json_fields_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pin = root / ".aec-pin"
            manifest = root / "manifest.json"
            pin.write_text("a" * 40 + "\n", encoding="utf-8")
            manifest.write_text(
                '{"schema_version":"1.0.0","schema_version":"1.0.0"}',
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(CHECKER), "--pin", str(pin), "--manifest", str(manifest)],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

        self.assertEqual(1, result.returncode)
        self.assertEqual("", result.stdout)
        self.assertIn("duplicate JSON field", result.stderr)

    def test_notification_is_consumer_owned_and_deduplicated_by_release(self) -> None:
        checker = load_checker()
        current = checker.compare_release("b" * 40, release_manifest())
        with mock.patch.object(checker.subprocess, "run") as run:
            self.assertEqual("not_needed", checker.notify(current, "owner/consumer"))
        run.assert_not_called()

        result = checker.compare_release("a" * 40, release_manifest())
        existing = subprocess.CompletedProcess(
            args=[], returncode=0, stdout='[{"title":"[AEC UPDATE] v9.8.7 available"}]', stderr=""
        )
        with mock.patch.object(checker.subprocess, "run", return_value=existing) as run:
            self.assertEqual("existing", checker.notify(result, "owner/consumer"))
        self.assertEqual(1, run.call_count)
        self.assertIn("all", run.call_args.args[0])
        self.assertIn("--search", run.call_args.args[0])

        missing = subprocess.CompletedProcess(args=[], returncode=0, stdout="[]", stderr="")
        created = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        with mock.patch.object(checker.subprocess, "run", side_effect=[missing, created]) as run:
            self.assertEqual("created", checker.notify(result, "owner/consumer"))
        self.assertEqual(2, run.call_count)
        create_command = run.call_args_list[1].args[0]
        self.assertEqual("create", create_command[2])
        rendered_command = "\n".join(create_command)
        self.assertIn("b" * 40, rendered_command)
        self.assertIn("validation-required", rendered_command)
        self.assertIn("human-render, material, routine", rendered_command)
        self.assertNotIn("merge", create_command)

    def test_failed_lookup_never_attempts_issue_creation(self) -> None:
        checker = load_checker()
        result = checker.compare_release("a" * 40, release_manifest())
        failed = subprocess.CompletedProcess(
            args=[], returncode=1, stdout="", stderr="authentication failed"
        )
        with mock.patch.object(checker.subprocess, "run", return_value=failed) as run:
            with self.assertRaises(checker.UpdateCheckFailure):
                checker.notify(result, "owner/consumer")
        self.assertEqual(1, run.call_count)


class ConsumerNotificationTemplateTests(unittest.TestCase):
    def test_workflow_is_scheduled_manual_consumer_owned_and_bounded(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("schedule:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("issues: write", workflow)
        self.assertIn("group: aec-release-notification", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn(
            "https://github.com/jasonewillis/AEC/releases/latest/download/"
            "aec-release-manifest.json",
            workflow,
        )
        self.assertNotIn("gh release download", workflow)
        self.assertIn("aec-release-manifest.json", workflow)
        self.assertIn("scripts/check_aec_release.py", workflow)
        self.assertIn("--notify-repository", workflow)
        for forbidden in ("git push", "gh pr", "checkout main", "auto-merge"):
            self.assertNotIn(forbidden, workflow)

    def test_install_kit_tracks_one_pin_and_copies_the_notifier(self) -> None:
        document = INSTALL_DOC.read_text(encoding="utf-8")
        self.assertIn(".aec-pin", document)
        self.assertIn('checkout "$(cat .aec-pin)"', document)
        self.assertIn("check_aec_release.py", document)
        self.assertIn("aec-release-notification.yml", document)


if __name__ == "__main__":
    unittest.main()
