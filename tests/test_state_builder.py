"""Tests for aec/state_builder.py.

Ported from the HealthRAG pilot's `AEC/tests/test_build_state.py` (issues
#58, #52). The pilot drove the tool as a subprocess since it did its own
file and Git I/O; here `build_state` is pure, so these tests call it
directly against the framework's own config JSON. CLI-level behavior is
covered separately in tests/test_aec_coach.py.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from aec.state_builder import (
    AEC_SELF_PROFILE,
    BuildStateFailure,
    build_state,
    parse_blocker,
    parse_evidence,
    procedure_references,
    workflow_references,
)


ROOT = Path(__file__).resolve().parents[1]
REVISION = "0123456789abcdef0123456789abcdef01234567"


def load_json(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


CATALOG = load_json(ROOT / "config" / "procedures" / "ticket-to-pr.json")
WORKFLOW = load_json(ROOT / "config" / "workflows" / "ticket-to-pr.json")


class ParseEvidenceTests(unittest.TestCase):
    def test_qualifiers(self) -> None:
        cases = (
            ("unqualified-report", {"kind": "unqualified-report", "accepted": False}),
            (
                "focused-test-report:accepted",
                {"kind": "focused-test-report", "accepted": True},
            ),
            (
                "integration-test-report:rejected",
                {"kind": "integration-test-report", "accepted": False},
            ),
        )
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(expected, parse_evidence(raw))

    def test_empty_kind_and_unknown_qualifier_are_rejected(self) -> None:
        for raw in (":accepted", "kind:maybe"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_evidence(raw)


class ParseBlockerTests(unittest.TestCase):
    def test_default_qualifier_is_active(self) -> None:
        self.assertEqual(
            {
                "active": True,
                "identity": "missing-fixture",
                "reason_code": "ACCEPTANCE_EVIDENCE_INCOMPLETE",
            },
            parse_blocker("missing-fixture:ACCEPTANCE_EVIDENCE_INCOMPLETE"),
        )

    def test_inactive_qualifier(self) -> None:
        self.assertEqual(
            {"active": False, "identity": "x", "reason_code": "Y"},
            parse_blocker("x:Y:inactive"),
        )

    def test_malformed_and_empty_reason_code_are_rejected(self) -> None:
        for raw in ("bad", "identity:"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_blocker(raw)


class ProcedureReferencesTests(unittest.TestCase):
    def test_returns_available_and_required_for_phase(self) -> None:
        available, required = procedure_references(CATALOG, "Verify")
        self.assertEqual(9, len(available))
        self.assertEqual("verify-evidence", required["identity"])

    def test_unknown_phase_raises(self) -> None:
        with self.assertRaises(BuildStateFailure):
            procedure_references(CATALOG, "NotAPhase")


class WorkflowReferencesTests(unittest.TestCase):
    def test_derives_phase_stage_map_and_identity(self) -> None:
        phase_stage, identity, revision = workflow_references(WORKFLOW)
        self.assertEqual("Understand", phase_stage["Framing"])
        self.assertEqual("Assure & Release", phase_stage["Deploy"])
        self.assertEqual("ticket-to-pr", identity)
        self.assertEqual("ticket-to-pr:1.0.0", revision)

    def test_malformed_workflow_raises(self) -> None:
        with self.assertRaises(BuildStateFailure):
            workflow_references({"id": "x", "schema_version": "1.0.0", "stages": []})


def build(**overrides: object) -> dict[str, object]:
    """Call build_state with sensible defaults, overridable per test."""
    kwargs: dict[str, object] = {
        "task": "demo-task",
        "phase": "Framing",
        "lane": "INFRA",
        "environment": "local",
        "expires_minutes": 30,
        "evidence": [],
        "blockers": [],
        "revision": REVISION,
        "catalog": CATALOG,
        "workflow": WORKFLOW,
    }
    kwargs.update(overrides)
    return build_state(**kwargs)  # type: ignore[arg-type]


class BuildStateTests(unittest.TestCase):
    def test_every_phase_builds_with_the_pinned_stage(self) -> None:
        expected = {
            phase: stage["name"]
            for stage in WORKFLOW["stages"]
            for phase in stage["phases"]
        }
        self.assertTrue(expected, "pinned workflow declared no phases")

        for phase, stage in expected.items():
            with self.subTest(phase=phase):
                state = build(phase=phase)
                self.assertEqual(stage, state["workflow_position"]["stage"])

    def test_invalid_phase_is_rejected(self) -> None:
        with self.assertRaises(BuildStateFailure):
            build(phase="NotAPhase")

    def test_evidence_records_bind_acceptance_and_revision(self) -> None:
        state = build(
            phase="Verify",
            evidence=[
                parse_evidence("focused-test-report:accepted"),
                parse_evidence("integration-test-report:rejected"),
                parse_evidence("unqualified-report"),
            ],
        )

        by_kind = {entry["kind"]: entry for entry in state["evidence"]}
        self.assertEqual(3, len(state["evidence"]))
        self.assertTrue(by_kind["focused-test-report"]["accepted"])
        self.assertFalse(by_kind["integration-test-report"]["accepted"])
        self.assertFalse(by_kind["unqualified-report"]["accepted"])
        for entry in state["evidence"]:
            self.assertEqual(REVISION, entry["revision"])
            self.assertEqual("local", entry["environment"])

    def test_blocker_records_declare_active_blocker(self) -> None:
        state = build(
            blockers=[parse_blocker("missing-fixture:ACCEPTANCE_EVIDENCE_INCOMPLETE")]
        )

        self.assertEqual(
            [
                {
                    "active": True,
                    "identity": "missing-fixture",
                    "reason_code": "ACCEPTANCE_EVIDENCE_INCOMPLETE",
                }
            ],
            state["blockers"],
        )

    def test_blockers_default_empty_when_omitted(self) -> None:
        self.assertEqual([], build()["blockers"])

    def test_decision_context_absent_when_omitted(self) -> None:
        self.assertNotIn("decision_context", build(phase="Build"))

    def test_default_profile_is_aec_coaching_itself(self) -> None:
        self.assertEqual(AEC_SELF_PROFILE, build()["consumer_profile"])

    def test_empty_task_and_empty_lane_are_rejected(self) -> None:
        for overrides in ({"task": ""}, {"lane": ""}):
            with self.subTest(overrides=overrides), self.assertRaises(BuildStateFailure):
                build(**overrides)

    def decision_context(self, supplied_revision: str) -> dict[str, object]:
        return {
            "authority": {"owner": "agent", "reason": "x"},
            "choices": [],
            "context": {"evidence_quality": "direct-verified", "revision": supplied_revision},
            "question": "x",
            "recommendation": {},
            "schema_version": "2.0.0",
        }

    def test_placeholder_decision_context_revision_is_bound(self) -> None:
        # A non-hex placeholder (e.g. "__REVISION__") cannot have been a real
        # claim about any commit, so it is filled in, not trusted verbatim.
        supplied = self.decision_context("__REVISION__")
        state = build(decision_context=supplied)

        self.assertEqual(REVISION, state["decision_context"]["context"]["revision"])
        self.assertEqual("__REVISION__", supplied["context"]["revision"], "input untouched")

    def test_stale_decision_context_revision_is_rejected(self) -> None:
        # A well-formed SHA that disagrees with the resolved revision is a
        # real claim about a different tree: it must be rejected, not
        # silently relabeled as current.
        stale = "0" * 40
        supplied = self.decision_context(stale)

        with self.assertRaisesRegex(BuildStateFailure, f"{stale}.*{REVISION}"):
            build(decision_context=supplied)

    def test_matching_decision_context_revision_passes_through(self) -> None:
        supplied = self.decision_context(REVISION)
        state = build(decision_context=supplied)

        self.assertEqual(REVISION, state["decision_context"]["context"]["revision"])


if __name__ == "__main__":
    unittest.main()
