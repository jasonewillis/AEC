"""CLI-level tests for tools/aec_coach.py.

Ported from the HealthRAG pilot's `AEC/tests/test_build_state.py` and
`AEC/tests/test_render_checkpoint.py` (issues #58, #52). One behavior is
deliberately inverted from the pilot: the pilot's `render_checkpoint.py`
defaulted to `json`; here the default is `human` and `--format json` is
explicit, matching docs/architecture/coaching-interaction.md and this
task's Decision Gates G2/G3/G6.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tools.aec_coach as aec_coach


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=False, cwd=ROOT, capture_output=True, text=True)


def run_coach(*args: str) -> subprocess.CompletedProcess[str]:
    return run([sys.executable, "-m", "tools.aec_coach", *args])


def current_revision() -> str:
    result = run(["git", "rev-parse", "HEAD"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


def build_state_file(directory: Path, /, phase: str = "Intake", **extra: str) -> Path:
    out_path = directory / "state.json"
    args = ["state", "--task", "demo-task", "--phase", phase, "--lane", "INFRA"]
    for flag, value in extra.items():
        args += [f"--{flag.replace('_', '-')}", value]
    args += ["--out", str(out_path)]
    result = run_coach(*args)
    if result.returncode != 0:
        raise AssertionError(result.stderr)
    return out_path


class HelpTests(unittest.TestCase):
    def test_help_exits_zero(self) -> None:
        result = run_coach("--help")

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("state", result.stdout)
        self.assertIn("checkpoint", result.stdout)


class StateThenCheckpointTests(unittest.TestCase):
    def test_generated_state_renders_through_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            out_path = build_state_file(Path(directory), phase="Framing")
            rendered = run_coach("checkpoint", str(out_path), "--format", "json")
            self.assertEqual(0, rendered.returncode, rendered.stderr)
            self.assertIn("gate", json.loads(rendered.stdout))

    def test_invalid_phase_and_malformed_blocker_are_rejected(self) -> None:
        cases = ({"phase": "NotAPhase"}, {"blocker": "bad"})
        for extra in cases:
            with self.subTest(extra=extra), tempfile.TemporaryDirectory() as directory:
                out_path = Path(directory) / "state.json"
                result = run_coach(
                    "state",
                    "--task",
                    "demo-task",
                    "--phase",
                    extra.get("phase", "Framing"),
                    "--lane",
                    "INFRA",
                    *(["--blocker", extra["blocker"]] if "blocker" in extra else []),
                    "--out",
                    str(out_path),
                )
                self.assertNotEqual(0, result.returncode)
                self.assertFalse(out_path.exists())

    def test_decision_context_flows_through_to_the_decision_block(self) -> None:
        # The fixture ships an unresolvable "__REVISION__" placeholder for
        # context.revision, on purpose: build_state must bind that field to
        # the resolved HEAD itself (aec/state_builder.py
        # _bind_decision_context_revision), not trust a caller-supplied
        # value it cannot have known in advance. The fixture is consumed
        # exactly as committed, with no substitution here.
        fixture = FIXTURES / "decision-context" / "example.json"

        with tempfile.TemporaryDirectory() as directory:
            out_path = build_state_file(
                Path(directory),
                phase="Framing",
                decision_context=str(fixture),
            )

            rendered = run_coach("checkpoint", str(out_path))
            self.assertEqual(0, rendered.returncode, rendered.stderr)
            self.assertIn("[AEC: Decision]", rendered.stdout)
            self.assertIn(
                "How should AEC invoke the pinned mentoring adapter?", rendered.stdout
            )

    def test_decision_context_revision_mismatch_is_rejected(self) -> None:
        # Red canary: a decision_context whose context.revision is a
        # well-formed but WRONG commit must still be rejected by the
        # existing resolver validation (aec/mentoring.py _validate_context),
        # even though build_state itself can no longer produce that shape
        # through the `state` subcommand. Constructed by hand to bypass the
        # subcommand's own binding and exercise that downstream check.
        fixture = FIXTURES / "decision-context" / "example.json"
        wrong_revision = "f" * 40
        decision_context = json.loads(
            fixture.read_text(encoding="utf-8").replace("__REVISION__", wrong_revision)
        )

        with tempfile.TemporaryDirectory() as directory:
            out_path = build_state_file(Path(directory), phase="Framing")
            state = json.loads(out_path.read_text(encoding="utf-8"))
            state["decision_context"] = decision_context
            out_path.write_text(json.dumps(state), encoding="utf-8")

            rendered = run_coach("checkpoint", str(out_path))
            self.assertNotEqual(0, rendered.returncode)
            self.assertIn("must equal the resolved revision", rendered.stderr)


class OutputFormatTests(unittest.TestCase):
    def test_default_format_is_human_and_json_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = build_state_file(Path(directory))

            default = run_coach("checkpoint", str(state_path))
            self.assertEqual(0, default.returncode, default.stderr)
            self.assertIn("[AEC: Project Guidance]", default.stdout)
            self.assertIn("[AEC: Mentoring]", default.stdout)
            with self.assertRaises(json.JSONDecodeError):
                json.loads(default.stdout)
            self.assertNotIn("[AEC: Decision]", default.stdout)

            explicit = run_coach("checkpoint", str(state_path), "--format", "json")
            self.assertEqual(0, explicit.returncode, explicit.stderr)
            self.assertEqual("{", explicit.stdout[0])
            json.loads(explicit.stdout)


class RejectedStateTests(unittest.TestCase):
    def test_malformed_and_expired_states_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            malformed_path = Path(directory) / "malformed.json"
            malformed_path.write_text(json.dumps({"nonsense": True}), encoding="utf-8")
            expired_path = build_state_file(
                Path(directory), expires_minutes="0"
            )

            for state_path in (malformed_path, expired_path):
                with self.subTest(state_path=state_path.name):
                    result = run_coach("checkpoint", str(state_path))
                    self.assertNotEqual(0, result.returncode)
                    self.assertEqual("", result.stdout)
                    self.assertIn("rejected", result.stderr.lower())


class HeadChangeTests(unittest.TestCase):
    def test_head_change_during_render_fails_closed(self) -> None:
        revision = current_revision()
        with tempfile.TemporaryDirectory() as directory:
            out_path = build_state_file(Path(directory))
            arguments = aec_coach.parse_arguments(["checkpoint", str(out_path)])
            with patch.object(
                aec_coach, "current_revision", side_effect=[revision, "0" * 40]
            ):
                exit_code = aec_coach.run_checkpoint(arguments)
            self.assertNotEqual(0, exit_code)


if __name__ == "__main__":
    unittest.main()
