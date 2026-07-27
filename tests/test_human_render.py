"""Tests for aec/human_render.py.

Ported from the HealthRAG pilot's `AEC/tests/test_render_checkpoint.py`
(issues #58, #52): its RenderRailTests, RenderDecisionTests, and the
human-format assertions from RenderCheckpointTests. `default_rail_definition()`
reads `aec.cards.PHASE_RAIL` / `STAGE_PHASES` directly (see
aec/human_render.py's module docstring), so these tests assert against
those same constants rather than re-reading JSON.
"""

from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from aec.cards import PHASE_RAIL, STAGE_PHASES, validate_public_card
from aec.consumer import ConsumerStateRejection, resolve_consumer_state
from aec.human_render import (
    FULL_CARD_TRIGGERS,
    HUMAN_RENDER_CONTRACT_VERSION,
    RAIL_COLUMN_WIDTH,
    RAIL_MARGIN,
    RailDefinition,
    RenderFailure,
    default_rail_definition,
    render_decision,
    render_human,
    render_interaction,
    render_mentoring,
    render_project_guidance,
    render_rail,
)
from aec.state_builder import build_state


ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads(
    (ROOT / "config" / "procedures" / "ticket-to-pr.json").read_text(encoding="utf-8")
)
WORKFLOW = json.loads(
    (ROOT / "config" / "workflows" / "ticket-to-pr.json").read_text(encoding="utf-8")
)


class HumanRenderContractTests(unittest.TestCase):
    def test_mentoring_heading_remains_the_stable_contract(self) -> None:
        self.assertEqual("1.1.0", HUMAN_RENDER_CONTRACT_VERSION)


def minimal_card(
    *,
    rail: int = 2,
    rail_total: int = 9,
    phase_index: int = 2,
    phase_total: int = 2,
    stage: str = "Understand",
    phase_name: str = "Framing",
    required_proof: list[str] = (),
    decision_support: dict[str, object] | None = None,
    revision: str = "a" * 40,
) -> dict[str, object]:
    """Build a validated-shaped card for testing render functions directly.

    This bypasses the resolver entirely. It only needs the fields the render
    functions read, using neutral infrastructure placeholders. Defaults are
    an arbitrary mid-rail position; tests override only what they check.
    """
    return {
        "anti_example": "Work advances while a required question stays open.",
        "authoritative": False,
        "decision_support": decision_support,
        "finished": ["A recorded example condition is met."],
        "gate": "Evidence needed",
        "good": ["An example of the pattern to aim for."],
        "mentoring": {
            "lesson": "An example lesson.",
            "recognition_heuristic": "An example recognition heuristic.",
            "why_gate_exists": "An example reason the gate exists.",
        },
        "phase": phase_name,
        "rail_position": {
            "phase": phase_index,
            "phase_total": phase_total,
            "rail": rail,
            "rail_total": rail_total,
            "stage": stage,
        },
        "required_proof": required_proof,
        "transition_request": {
            "environment": "test",
            "executes": False,
            "mutates": False,
            "revision": revision,
        },
    }


RAIL_DEFINITION = default_rail_definition()


class DefaultRailDefinitionTests(unittest.TestCase):
    def test_matches_aec_cards_constants(self) -> None:
        self.assertEqual(PHASE_RAIL, RAIL_DEFINITION.phase_names)
        self.assertEqual(len(STAGE_PHASES), len(RAIL_DEFINITION.stage_groups))
        zipped = zip(RAIL_DEFINITION.stage_groups, STAGE_PHASES.items())
        for (label, phases), (name, expected_phases) in zipped:
            self.assertEqual(name.upper(), label)
            self.assertEqual(expected_phases, phases)


class RenderRailTests(unittest.TestCase):
    def test_marker_placement_for_early_phase(self) -> None:
        card = minimal_card(rail=1, phase_index=1, stage="Understand", phase_name="Intake")

        rail_text = render_rail(card, RAIL_DEFINITION)
        marker_line = rail_text.splitlines()[1]
        current_column = RAIL_MARGIN + 0 * RAIL_COLUMN_WIDTH

        self.assertEqual("◉", marker_line[current_column])
        self.assertEqual(1, marker_line.count("◉"))
        self.assertEqual(0, marker_line.count("●"))
        self.assertIn("rail 1/9", rail_text)
        self.assertIn("phase 1 of 2 in stage", rail_text)
        self.assertNotIn("blocking:", rail_text)

    def test_marker_placement_for_late_phase(self) -> None:
        card = minimal_card(
            rail=9,
            phase_index=3,
            phase_total=3,
            stage="Assure & Release",
            phase_name="Deploy",
            required_proof=["example-proof-one", "example-proof-two"],
        )

        rail_text = render_rail(card, RAIL_DEFINITION)
        marker_line = rail_text.splitlines()[1]
        current_column = RAIL_MARGIN + 8 * RAIL_COLUMN_WIDTH

        self.assertEqual("◉", marker_line[current_column])
        self.assertEqual(1, marker_line.count("◉"))
        self.assertEqual(8, marker_line.count("●"))
        self.assertEqual(0, marker_line.count("○"))
        self.assertIn("rail 9/9", rail_text)
        self.assertIn("phase 3 of 3 in stage", rail_text)
        self.assertIn("required proof: example-proof-one, example-proof-two", rail_text)

    def test_all_nine_phase_names_present_in_rail(self) -> None:
        rail_text = render_rail(minimal_card(rail=5, stage="Execute", phase_name="Build"),
                                 RAIL_DEFINITION)
        for phase_name in PHASE_RAIL:
            self.assertIn(phase_name, rail_text)
        self.assertIn("Deploy/Observe", rail_text)

    def test_render_rail_is_driven_by_the_rail_definition_argument(self) -> None:
        # Proves the rail is data-driven, not hardcoded: a rail definition
        # with renamed, fewer phases produces a correspondingly different
        # drawing. The framework's real phase names must NOT leak in, and
        # the synthetic ones must.
        synthetic = RailDefinition(
            phase_names=("Alpha", "Beta", "Gamma"),
            stage_groups=(("FIRST", ("Alpha", "Beta")), ("SECOND", ("Gamma",))),
        )
        card = minimal_card(
            rail=2, rail_total=3, phase_index=1, phase_total=1, stage="FIRST", phase_name="Beta"
        )

        rail_text = render_rail(card, synthetic)

        for phase_name in ("Alpha", "Beta", "Gamma"):
            self.assertIn(phase_name, rail_text)
        self.assertIn("FIRST", rail_text)
        self.assertIn("SECOND", rail_text)
        self.assertIn("rail 2/3", rail_text)
        for pinned_phase_name in PHASE_RAIL:
            if pinned_phase_name not in ("Alpha", "Beta", "Gamma"):
                self.assertNotIn(pinned_phase_name, rail_text)
        marker_line = rail_text.splitlines()[1]
        marker_total = (
            marker_line.count("●") + marker_line.count("◉") + marker_line.count("○")
        )
        self.assertEqual(3, marker_total)

    def test_render_rail_fails_closed_on_rail_total_mismatch(self) -> None:
        # rail_total must agree with the rail definition's phase count. A
        # card claiming 9 phases against a 3-phase rail definition must fail
        # closed rather than draw a rail whose text and columns disagree.
        synthetic = RailDefinition(
            phase_names=("Alpha", "Beta", "Gamma"),
            stage_groups=(("FIRST", ("Alpha", "Beta")), ("SECOND", ("Gamma",))),
        )
        card = minimal_card(rail=1, phase_index=1, phase_total=1, stage="FIRST", phase_name="Alpha")

        with self.assertRaisesRegex(RenderFailure, "rail_total"):
            render_rail(card, synthetic)


class RenderProjectGuidanceTests(unittest.TestCase):
    def test_renders_concrete_evidence_bound_next_action(self) -> None:
        card = minimal_card(
            rail=8,
            phase_index=2,
            phase_total=3,
            stage="Assure & Release",
            phase_name="PR",
            required_proof=["current-required-checks"],
        )

        text = render_project_guidance(card, RAIL_DEFINITION)

        self.assertIn("Next action: Remain at PR", text)
        self.assertIn("ci-verified: current-required-checks", text)
        self.assertIn("Gate status: Evidence needed", text)
        self.assertIn("Earliest unmet gate: PR evidence gate", text)
        self.assertIn("Blockers: none recorded", text)
        self.assertIn("Consumer owns execution, task/GitHub state, tests, merge", text)

    def test_labels_the_phase_not_a_procedure(self) -> None:
        text = render_project_guidance(minimal_card(), RAIL_DEFINITION)

        self.assertIn("Next action:", text)
        self.assertNotIn("Recommended next procedure:", text)


class RenderMentoringTests(unittest.TestCase):
    def test_renders_lesson_and_recognition_heuristic(self) -> None:
        text = render_mentoring(minimal_card())

        self.assertIn("An example lesson.", text)
        self.assertIn("An example reason the gate exists.", text)
        self.assertIn("An example recognition heuristic.", text)


class RenderDecisionTests(unittest.TestCase):
    def test_returns_none_when_decision_support_is_null(self) -> None:
        card = minimal_card(decision_support=None)

        self.assertIsNone(render_decision(card))
        self.assertNotIn("[AEC: Decision]", render_human(card, RAIL_DEFINITION))

    def test_renders_choices_and_recommendation_when_present(self) -> None:
        tradeoff_names = ("maintainability", "quality", "reversibility", "risk", "scope")
        card = minimal_card(
            decision_support={
                "authority": {
                    "owner": "agent",
                    "reason": "An example reversible, in-scope choice.",
                },
                "choices": [
                    {
                        "identity": f"example-choice-{ordinal}",
                        "summary": f"An example {ordinal} choice.",
                        "tradeoffs": {
                            name: f"Example {name} note {ordinal}."
                            for name in tradeoff_names
                        },
                    }
                    for ordinal in ("one", "two")
                ],
                "question": "An example decision question.",
                "recommendation": {
                    "choice": "example-choice-one",
                    "confidence": "high",
                    "expected_result": {
                        "baseline": "0",
                        "direction": "increase",
                        "measure": "example-measure",
                        "target": "1",
                        "threshold": "An example threshold.",
                        "unit": "count",
                    },
                    "principal_uncertainty": "An example uncertainty.",
                    "revisit_when": ["An example revisit condition."],
                },
            },
        )

        text = render_decision(card)
        self.assertIsNotNone(text)
        assert text is not None
        self.assertIn("[AEC: Decision]", text)
        self.assertIn("An example decision question.", text)
        self.assertIn("example-choice-one", text)
        self.assertIn("example-choice-two", text)
        self.assertIn("Confidence: high", text)
        self.assertIn("An example revisit condition.", text)
        self.assertIn("Authority owner: agent", text)
        self.assertIn("[AEC: Decision]", render_human(card, RAIL_DEFINITION))


class RenderHumanTests(unittest.TestCase):
    def test_contains_both_required_blocks_and_a_single_trailing_newline(self) -> None:
        text = render_human(minimal_card(), RAIL_DEFINITION)

        self.assertIn("[AEC: Project Guidance]", text)
        self.assertIn("[AEC: Mentoring]", text)
        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))

    def test_meaningful_triggers_render_one_complete_card(self) -> None:
        card = minimal_card()

        for trigger in FULL_CARD_TRIGGERS:
            with self.subTest(trigger=trigger):
                text = render_interaction(card, RAIL_DEFINITION, trigger)
                self.assertIn("[AEC: Project Guidance]", text)
                self.assertIn("[AEC: Mentoring]", text)
                self.assertIn("you are here", text)

    def test_routine_progress_is_compact_and_deterministic(self) -> None:
        card = minimal_card(
            rail=8,
            phase_index=2,
            phase_total=3,
            stage="Assure & Release",
            phase_name="PR",
            required_proof=["current-required-checks"],
        )

        first = render_interaction(card, RAIL_DEFINITION, "routine-progress")
        second = render_interaction(card, RAIL_DEFINITION, "routine-progress")

        self.assertEqual("AEC: PR · CI evidence pending\n", first)
        self.assertEqual(first, second)
        self.assertNotIn("[AEC: Project Guidance]", first)
        self.assertNotIn("[AEC: Mentoring]", first)

    def test_fedjobadvisor_pr_fixture_separates_evidence_boundaries(self) -> None:
        revision = "ffa19483c1d796c87a0544ff860c7efb98ec7a7d"
        observed_at = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)
        state = build_state(
            task="FedJobAdvisor#9305",
            phase="PR",
            lane="INFRA",
            environment="fedjobadvisor-pr",
            expires_minutes=30,
            evidence=[
                {"accepted": True, "kind": kind}
                for kind in (
                    "resolved-findings",
                    "independent-review",
                    "base-head-binding",
                    "focused-test-report:227",
                    "integration-test-report",
                )
            ]
            + [{"accepted": False, "kind": "stacked-base-readiness"}],
            blockers=[],
            revision=revision,
            catalog=CATALOG,
            workflow=WORKFLOW,
            profile={
                "aec_mode": "read-only-mentor",
                "agent_adapters": ["claude-code", "codex"],
                "lifecycle_authority": "consumer-owned",
                "profile_version": "fedjobadvisor:acceptance-fixture",
                "project": "JLWAI/fedJobAdvisor",
                "schema_version": "1.0.0",
                "workflow": "ticket-to-pr",
            },
            observed_at=observed_at,
        )
        result = resolve_consumer_state(
            state,
            CATALOG,
            current_time="2026-07-26T12:01:00Z",
            expected_environment="fedjobadvisor-pr",
            expected_revision=revision,
        )
        self.assertNotIsInstance(result, ConsumerStateRejection)
        card = result.to_dict()
        self.assertEqual([], validate_public_card(card))
        self.assertEqual(["current-required-checks"], card["required_proof"])

        text = render_interaction(
            card,
            RAIL_DEFINITION,
            "status-request",
            evidence=state["evidence"],
            blockers=state["blockers"],
            task_id=state["task"]["identity"],
        )

        self.assertIn("Task: FedJobAdvisor#9305", text)
        self.assertIn("rail 8/9", text)
        self.assertIn(revision, text)
        self.assertIn("source-audited: verified", text)
        self.assertIn(
            "[Consumer: Evidence Context]\n"
            "These consumer-reported facts are not AEC gates or recommendations:\n"
            "  - source-audited: stacked-base-readiness pending",
            text,
        )
        next_action = next(
            line for line in text.splitlines() if line.startswith("Next action:")
        )
        self.assertNotIn("stacked-base-readiness", next_action)
        self.assertIn("focused-test-report:227", text)
        self.assertIn("test-verified: verified", text)
        self.assertIn("ci-verified: pending (required: current-required-checks)", text)
        self.assertIn("runtime-verified: not claimed", text)
        self.assertIn("live-data-verified: not claimed", text)
        self.assertIn(
            "Lesson: A pull request becomes mergeable only when findings and "
            "required checks agree on the same immutable candidate.",
            text,
        )
        self.assertIn("[AEC: Mentoring]", text)

    def test_evidence_category_is_partial_when_one_required_kind_is_missing(self) -> None:
        revision = "b" * 40
        card = minimal_card(
            phase_name="Review",
            required_proof=["independent-review"],
            revision=revision,
        )
        evidence = [
            {
                "accepted": True,
                "environment": "test",
                "kind": "base-head-binding",
                "revision": revision,
            }
        ]

        text = render_interaction(
            card, RAIL_DEFINITION, "status-request", evidence=evidence
        )

        self.assertIn(
            "source-audited: partial (verified: base-head-binding; "
            "required: independent-review)",
            text,
        )


if __name__ == "__main__":
    unittest.main()
