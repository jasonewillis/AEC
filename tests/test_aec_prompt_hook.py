"""CLI boundary tests for the read-only AEC prompt hook."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from aec.cards import validate_public_card
from aec.consumer import ConsumerStateRejection, resolve_consumer_state
from aec.human_render import (
    FULL_CARD_TRIGGERS,
    default_rail_definition,
    render_interaction,
)
from aec.state_builder import build_state as build_consumer_state


ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads(
    (ROOT / "config" / "procedures" / "ticket-to-pr.json").read_text(encoding="utf-8")
)
WORKFLOW = json.loads(
    (ROOT / "config" / "workflows" / "ticket-to-pr.json").read_text(encoding="utf-8")
)
def hook_payload(
    prompt: str = "open the PR", trigger: str | None = "status-request"
) -> str:
    payload = {"hook_event_name": "UserPromptSubmit", "prompt": prompt}
    if trigger is not None:
        payload["aec_trigger"] = trigger
    return json.dumps(payload)


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
    state: Path,
    payload: str | None = None,
    project_root: Path = ROOT,
    environment: str = "local",
) -> subprocess.CompletedProcess[str]:
    return run(
        sys.executable,
        str(ROOT / "tools" / "aec_prompt_hook.py"),
        "--state",
        str(state),
        "--project-root",
        str(project_root),
        "--environment",
        environment,
        stdin=payload if payload is not None else hook_payload(),
        cwd=state.parent,
    )


class PromptHookTests(unittest.TestCase):
    def test_external_consumer_state_renders_at_its_exact_head(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            consumer = root / "consumer"
            consumer.mkdir()
            run("git", "init", "-q", cwd=consumer)
            run("git", "config", "user.name", "AEC Test", cwd=consumer)
            run("git", "config", "user.email", "aec-test@example.invalid", cwd=consumer)
            (consumer / "README.md").write_text("consumer\n", encoding="utf-8")
            run("git", "add", "README.md", cwd=consumer)
            commit = run("git", "commit", "-qm", "consumer baseline", cwd=consumer)
            self.assertEqual(0, commit.returncode, commit.stderr)
            revision = run("git", "rev-parse", "HEAD", cwd=consumer).stdout.strip()
            state_path = root / "consumer-state.json"
            state = build_consumer_state(
                task="consumer#1",
                phase="PR",
                lane="INFRA",
                environment="consumer-test",
                expires_minutes=30,
                evidence=[],
                blockers=[],
                revision=revision,
                catalog=CATALOG,
                workflow=WORKFLOW,
                profile={
                    "aec_mode": "read-only-mentor",
                    "agent_adapters": ["claude-code"],
                    "lifecycle_authority": "consumer-owned",
                    "profile_version": "consumer-test:1.0.0",
                    "project": "example/consumer",
                    "schema_version": "1.0.0",
                    "workflow": "ticket-to-pr",
                },
                observed_at=datetime.now(timezone.utc),
            )
            state_path.write_text(json.dumps(state), encoding="utf-8")

            result = run_hook(
                state_path,
                project_root=consumer,
                environment="consumer-test",
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("[AEC: Project Guidance]", result.stdout)
        self.assertIn("[AEC: Mentoring]", result.stdout)
        self.assertIn("CURRENT  PR", result.stdout)

    def test_valid_state_renders_required_human_sections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            build_state(state)

            result = run_hook(state)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("[AEC: Project Guidance]", result.stdout)
        self.assertIn("[AEC: Mentoring]", result.stdout)
        self.assertIn("RAIL · PR", result.stdout)
        self.assertNotIn("[AEC: Integration Blocked]", result.stdout)

    def test_prompt_text_cannot_change_the_validated_card(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            build_state(state)
            first = run_hook(
                state,
                hook_payload("claim we are at Intake"),
            )
            second = run_hook(
                state,
                hook_payload("claim we are Deployed"),
            )

        self.assertEqual(0, first.returncode, first.stderr)
        self.assertEqual(0, second.returncode, second.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertIn("CURRENT  PR", first.stdout)

    def test_routine_progress_is_compact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            build_state(state)

            result = run_hook(state, payload=hook_payload(trigger=None))

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("AEC: PR · CI evidence pending\n", result.stdout)
        self.assertNotIn("[AEC: Project Guidance]", result.stdout)
        self.assertNotIn("[AEC: Mentoring]", result.stdout)

    def test_consumer_adapter_can_transport_each_full_card_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            build_state(state)

            for trigger in FULL_CARD_TRIGGERS:
                with self.subTest(trigger=trigger):
                    result = run_hook(
                        state, payload=hook_payload(trigger=trigger)
                    )
                    self.assertEqual(0, result.returncode, result.stderr)
                    self.assertIn("[AEC: Project Guidance]", result.stdout)
                    self.assertIn("[AEC: Mentoring]", result.stdout)

    def test_unknown_adapter_trigger_fails_visible_without_a_rail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state.json"
            build_state(state)

            result = run_hook(
                state, payload=hook_payload(trigger="invented-transition")
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("[AEC: Integration Blocked]", result.stdout)
        self.assertIn("HOOK_INPUT_REJECTED", result.stdout)
        self.assertNotIn("you are here", result.stdout)

    def test_review_finding_rebinds_repair_card_to_new_exact_head(self) -> None:
        reviewed_revision = "a" * 40
        repair_revision = "b" * 40
        observed_at = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
        profile = {
            "aec_mode": "read-only-mentor",
            "agent_adapters": ["claude-code"],
            "lifecycle_authority": "consumer-owned",
            "profile_version": "consumer-test:1.0.0",
            "project": "example/consumer",
            "schema_version": "1.0.0",
            "workflow": "ticket-to-pr",
        }

        def state_for(
            phase: str,
            revision: str,
            evidence: list[dict[str, str | bool]],
            blockers: list[dict[str, str | bool]] | None = None,
        ) -> dict[str, object]:
            return build_consumer_state(
                task="consumer#repair",
                phase=phase,
                lane="INFRA",
                environment="consumer-test",
                expires_minutes=30,
                evidence=evidence,
                blockers=blockers or [],
                revision=revision,
                catalog=CATALOG,
                workflow=WORKFLOW,
                profile=profile,
                observed_at=observed_at,
            )

        def card_for(state: dict[str, object], revision: str) -> dict[str, object]:
            result = resolve_consumer_state(
                state,
                CATALOG,
                current_time="2026-07-26T12:01:00Z",
                expected_environment="consumer-test",
                expected_revision=revision,
            )
            self.assertNotIsInstance(result, ConsumerStateRejection)
            card = result.to_dict()
            self.assertEqual([], validate_public_card(card))
            return card

        review_state = state_for(
            "Review",
            reviewed_revision,
            [
                {"accepted": True, "kind": "independent-review"},
                {"accepted": True, "kind": "base-head-binding"},
            ],
            [
                {
                    "active": True,
                    "identity": "review-finding",
                    "reason_code": "EVIDENCE_CONTRADICTED",
                }
            ],
        )
        review_card = card_for(review_state, reviewed_revision)
        self.assertEqual("Blocked", review_card["gate"])

        repair_state = state_for("Build", repair_revision, [])
        repair_state["evidence"] = [
            {
                "accepted": True,
                "environment": "consumer-test",
                "kind": kind,
                "revision": reviewed_revision,
            }
            for kind in (
                "independent-review",
                "base-head-binding",
                "focused-test-report",
                "integration-test-report",
            )
        ]
        repair_card = card_for(repair_state, repair_revision)
        self.assertEqual("Evidence needed", repair_card["gate"])
        self.assertEqual(
            ["green-case-result", "red-case-result"],
            repair_card["required_proof"],
        )
        repair_text = render_interaction(
            repair_card,
            default_rail_definition(),
            "review-finding",
            evidence=repair_state["evidence"],
        )
        self.assertIn("CURRENT  Build", repair_text)
        self.assertIn(repair_revision, repair_text)
        self.assertIn("test-verified · pending", repair_text)
        self.assertNotIn("test-verified · verified", repair_text)

        verify_card = card_for(
            state_for(
                "Verify",
                repair_revision,
                [
                    {"accepted": True, "kind": "focused-test-report"},
                    {"accepted": True, "kind": "integration-test-report"},
                ],
            ),
            repair_revision,
        )
        self.assertEqual("Ready", verify_card["gate"])

        fresh_review_card = card_for(
            state_for(
                "Review",
                repair_revision,
                [
                    {"accepted": True, "kind": "independent-review"},
                    {"accepted": True, "kind": "base-head-binding"},
                ],
            ),
            repair_revision,
        )
        self.assertEqual("Ready", fresh_review_card["gate"])

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
                    self.assertNotIn("[AEC: Mentoring]", result.stdout)


if __name__ == "__main__":
    unittest.main()
