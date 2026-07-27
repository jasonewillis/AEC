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


# Well-formed (40 lowercase hex characters) and deterministically not the
# resolved revision. CI checks out a shallow clone with exactly one commit,
# so no earlier commit exists there to reference; production only checks
# "well-formed and not equal to resolved HEAD", so this synthetic constant
# exercises the same code path without depending on repository history.
STALE_REVISION = "0" * 40


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

    def test_stale_decision_context_is_rejected_at_state_build_time(self) -> None:
        # Red canary: a decision_context whose context.revision is a
        # well-formed SHA for a DIFFERENT commit than resolved HEAD (a stale
        # decision, e.g. formed before a rebase) must be rejected by
        # `state` itself (aec/state_builder.py _bind_decision_context_revision),
        # naming both revisions. This is the CLI path a real stale decision
        # would actually take, not a hand-built state file: build_state can
        # reject this case directly, so the CLI is exercised end to end.
        # STALE_REVISION is synthetic, not a real prior commit, so this does
        # not depend on repository history (CI checks out a shallow clone).
        stale_revision = STALE_REVISION
        head_revision = current_revision()
        fixture = FIXTURES / "decision-context" / "example.json"
        decision_context = fixture.read_text(encoding="utf-8").replace(
            "__REVISION__", stale_revision
        )

        with tempfile.TemporaryDirectory() as directory:
            decision_path = Path(directory) / "stale-decision.json"
            decision_path.write_text(decision_context, encoding="utf-8")
            out_path = Path(directory) / "state.json"
            result = run_coach(
                "state",
                "--task",
                "demo-task",
                "--phase",
                "Framing",
                "--lane",
                "INFRA",
                "--decision-context",
                str(decision_path),
                "--out",
                str(out_path),
            )

            self.assertNotEqual(0, result.returncode)
            self.assertFalse(out_path.exists())
            self.assertIn(stale_revision, result.stderr)
            self.assertIn(head_revision, result.stderr)


class OutputFormatTests(unittest.TestCase):
    def test_default_format_is_human_and_json_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = build_state_file(Path(directory))

            default = run_coach("checkpoint", str(state_path))
            self.assertEqual(0, default.returncode, default.stderr)
            self.assertIn("[AEC: Project Guidance]", default.stdout)
            self.assertIn("[AEC: Mentor]", default.stdout)
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
