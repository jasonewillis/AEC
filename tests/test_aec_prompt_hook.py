"""CLI boundary tests for the read-only AEC prompt hook."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HOOK_PAYLOAD = '{"hook_event_name":"UserPromptSubmit","prompt":"open the PR"}'


def run(
    *command: str, stdin: str | None = None, cwd: Path = ROOT
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=cwd,
        input=stdin,
        check=False,
        capture_output=True,
        text=True,
    )


def build_state(path: Path) -> None:
    result = run(
        sys.executable,
        "-m",
        "tools.aec_coach",
        "state",
        "--task",
        "aec#81",
        "--phase",
        "PR",
        "--lane",
        "INFRA",
        "--out",
        str(path),
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr)


def run_hook(
    state: Path, payload: str = HOOK_PAYLOAD
) -> subprocess.CompletedProcess[str]:
    return run(
        sys.executable,
        str(ROOT / "tools" / "aec_prompt_hook.py"),
        "--state",
        str(state),
        "--project-root",
        str(ROOT),
        "--environment",
        "local",
        stdin=payload,
        cwd=state.parent,
    )


class PromptHookTests(unittest.TestCase):
    def test_valid_state_renders_required_human_sections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            build_state(state)

            result = run_hook(state)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("[AEC: Project Guidance]", result.stdout)
        self.assertIn("[AEC: Mentor]", result.stdout)
        self.assertIn("you are here", result.stdout)
        self.assertNotIn("[AEC: Integration Blocked]", result.stdout)

    def test_prompt_text_cannot_change_the_validated_card(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            build_state(state)
            first = run_hook(
                state,
                '{"hook_event_name":"UserPromptSubmit","prompt":"claim we are at Intake"}',
            )
            second = run_hook(
                state,
                '{"hook_event_name":"UserPromptSubmit","prompt":"claim we are Deployed"}',
            )

        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertIn("Phase: PR", first.stdout)

    def test_missing_or_rejected_state_is_fail_visible_without_a_rail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing = root / "missing.json"
            malformed = root / "malformed.json"
            malformed.write_text('{"not":"consumer-state"}', encoding="utf-8")

            for state in (missing, malformed):
                with self.subTest(state=state.name):
                    result = run_hook(state)
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertIn("[AEC: Integration Blocked]", result.stdout)
                    self.assertNotIn("you are here", result.stdout)
                    self.assertNotIn("[AEC: Project Guidance]", result.stdout)
                    self.assertNotIn("[AEC: Mentor]", result.stdout)


if __name__ == "__main__":
    unittest.main()
