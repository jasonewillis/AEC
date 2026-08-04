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
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path

from aec.cards import PHASE_RAIL, STAGE_PHASES, validate_public_card
from aec.consumer import ConsumerStateRejection, resolve_consumer_state
from aec.human_render import (
    EVIDENCE_CLASS_BY_KIND,
    EVIDENCE_CLASS_ORDER,
    FULL_CARD_TRIGGERS,
    HUMAN_RENDER_CONTRACT_VERSION,
    ORIENTATION_TRIGGERS,
    RAIL_CONNECTOR,
    TEXT_WIDTH,
    PHASE_DISPLAY_NAMES,
    RailDefinition,
    RenderFailure,
    default_rail_definition,
    evidence_class,
    render_decision,
    render_human,
    render_interaction,
    render_mentoring,
    render_project_guidance,
    render_rail,
)
from aec.state_builder import AEC_SELF_PROFILE, build_state


ROOT = Path(__file__).resolve().parents[1]
CATALOG = json.loads(
    (ROOT / "config" / "procedures" / "ticket-to-pr.json").read_text(encoding="utf-8")
)
WORKFLOW = json.loads(
    (ROOT / "config" / "workflows" / "ticket-to-pr.json").read_text(encoding="utf-8")
)


class HumanRenderContractTests(unittest.TestCase):
    def test_mentoring_heading_remains_the_stable_contract(self) -> None:
        self.assertEqual("1.5.0", HUMAN_RENDER_CONTRACT_VERSION)


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

        self.assertIn("Intake ◉", marker_line)
        self.assertEqual(1, marker_line.count("◉"))
        self.assertEqual(0, marker_line.count("●"))
        # Twice, and deliberately: once as an unlabeled `◉` on the marker line,
        # once in words on the summary. The dense render suppresses the marker
        # legend, so the graphic alone does not name the phase to a reader who
        # was never given the key.
        self.assertIn("RAIL · Intake · step 1/9 · Understand 1/2", rail_text)
        self.assertEqual(2, rail_text.count("Intake"))
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

        self.assertIn("Deploy/Observe ◉", marker_line)
        self.assertEqual(1, marker_line.count("◉"))
        self.assertEqual(8, marker_line.count("●"))
        self.assertEqual(0, marker_line.count("○"))
        self.assertIn(
            "RAIL · Deploy/Observe · step 9/9 · Assure & Release 3/3",
            rail_text,
        )
        self.assertNotIn("required proof:", rail_text)

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
        self.assertIn("RAIL · Beta · step 2/3 · FIRST 1/1", rail_text)
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

    def test_each_stage_label_is_bracketed_within_its_phase_token_columns(self) -> None:
        card = minimal_card(rail=1, phase_index=1, stage="Understand", phase_name="Intake")
        rail_text = render_rail(card, RAIL_DEFINITION)
        header_line = rail_text.splitlines()[0]
        phase_line = rail_text.splitlines()[1]

        # One ├ and one ┤ per stage group.
        self.assertEqual(len(RAIL_DEFINITION.stage_groups), header_line.count("├"))
        self.assertEqual(len(RAIL_DEFINITION.stage_groups), header_line.count("┤"))

        # Every bracket sits within its group's phase-token columns
        # (neither overflows into a neighbouring stage's span).
        tokens = phase_line.split("───")
        token_starts = []
        cursor = 0
        for token in tokens:
            token_starts.append(cursor)
            cursor += len(token) + 3  # RAIL_CONNECTOR length
        phase_cursor = 0
        for _label, phases in RAIL_DEFINITION.stage_groups:
            first = phase_cursor
            last = phase_cursor + len(phases) - 1
            span_start = token_starts[first]
            span_end = token_starts[last] + len(tokens[last])
            span = header_line[span_start:span_end]
            self.assertEqual(1, span.count("├"), span)
            self.assertEqual(1, span.count("┤"), span)
            # ├ is the leftmost span char, ┤ the rightmost.
            self.assertTrue(span.startswith("├"), span)
            self.assertTrue(span.endswith("┤"), span)
            phase_cursor += len(phases)

    def test_long_stage_label_over_narrow_span_falls_back_to_plain_or_truncated(
        self,
    ) -> None:
        # A single-phase span with a stage label wider than the phase
        # token cannot fit brackets; the renderer must degrade rather
        # than overflow into the neighbouring stage.
        synthetic = RailDefinition(
            phase_names=("A", "B"),
            stage_groups=(
                ("VERY-LONG-STAGE-LABEL", ("A",)),
                ("S", ("B",)),
            ),
        )
        card = minimal_card(rail=1, rail_total=2, phase_index=1, phase_total=1,
                            stage="VERY-LONG-STAGE-LABEL", phase_name="A")
        rail_text = render_rail(card, synthetic)
        header_line = rail_text.splitlines()[0]
        phase_line = rail_text.splitlines()[1]

        # First stage span cannot fit brackets → header must not use them
        # in that span. Header must not exceed the phase line width.
        self.assertLessEqual(len(header_line), len(phase_line))
        # No bracket has spilled into or past the neighbouring stage.
        first_token_end = phase_line.index("───")
        first_span = header_line[:first_token_end]
        self.assertNotIn("├", first_span)
        self.assertNotIn("┤", first_span)

    def test_rail_lines_never_exceed_the_width_contract(self) -> None:
        # Header and phase lines must both stay <= TEXT_WIDTH regardless
        # of which phase is current. Prove it for the first and last
        # phase indices, since marker glyphs are 1 column each so width
        # is invariant to phase position but the assertion is cheap.
        for rail_index, phase_name in ((1, "Intake"), (9, "Deploy")):
            card = minimal_card(
                rail=rail_index,
                phase_index=1,
                phase_total=2 if phase_name == "Intake" else 3,
                stage="Understand" if phase_name == "Intake" else "Assure & Release",
                phase_name=phase_name,
            )
            rail_text = render_rail(card, RAIL_DEFINITION)
            for line in rail_text.splitlines()[:2]:
                self.assertLessEqual(len(line), TEXT_WIDTH, (phase_name, line))

    def test_default_rail_phase_line_keeps_headroom_against_text_width(self) -> None:
        # A one-character phase display-name rename (for example lengthening
        # "Deploy/Observe") must not push the phase line over TEXT_WIDTH.
        # Pin real headroom, not just exact equality, so this test fails
        # loudly before render_rail starts raising RenderFailure.
        tokens = [
            f"{PHASE_DISPLAY_NAMES.get(name, name)} ●"
            for name in RAIL_DEFINITION.phase_names
        ]
        phase_line = RAIL_CONNECTOR.join(tokens)
        headroom = TEXT_WIDTH - len(phase_line)
        self.assertGreaterEqual(
            headroom,
            8,
            f"rail phase line has only {headroom} columns of headroom "
            f"against TEXT_WIDTH={TEXT_WIDTH}",
        )


class RenderProjectGuidanceTests(unittest.TestCase):
    def test_uses_scannable_terminal_safe_hierarchy(self) -> None:
        text = render_project_guidance(
            minimal_card(required_proof=["independent-review"]),
            RAIL_DEFINITION,
        )

        lines = text.splitlines()
        self.assertEqual("[AEC: Project Guidance]", lines[0])
        self.assertEqual("═" * 64, lines[1])
        # The rail summary replaced CURRENT, which was a strict subset of it.
        self.assertIn("RAIL · Framing · step 2/9 · Understand 2/2", text)
        self.assertNotIn("CURRENT", text)
        self.assertIn("GATE     Evidence needed", text)
        self.assertIn("NEXT     Stay in this phase.", text)
        self.assertIn("PROOF    source-audited · independent-review", text)
        self.assertIn("DONE WHEN A recorded example condition is met.", text)
        self.assertIn("AEC is advisory and read-only.", text)
        self.assertNotIn("Gate status:", text)
        self.assertNotIn("Earliest unmet gate:", text)

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

        # The phase is named on the RAIL summary, not restated here.
        self.assertIn("RAIL · PR · step 8/9", text)
        self.assertIn("NEXT     Stay in this phase.", text)
        self.assertIn("PROOF    ci-verified · current-required-checks", text)
        self.assertIn("GATE     Evidence needed", text)
        # Nothing is blocking, so the card says nothing about blockers.
        self.assertNotIn("BLOCKERS", text)
        self.assertIn("You own execution, task/GitHub state, tests, merge", text)

    def test_labels_the_phase_not_a_procedure(self) -> None:
        text = render_project_guidance(minimal_card(), RAIL_DEFINITION)

        self.assertIn("NEXT     ", text)
        self.assertNotIn("Recommended next procedure:", text)


class RenderMentoringTests(unittest.TestCase):
    def test_renders_lesson_and_recognition_heuristic(self) -> None:
        text = render_mentoring(minimal_card())

        self.assertEqual("[AEC: Mentoring]", text.splitlines()[0])
        self.assertEqual("═" * 64, text.splitlines()[1])
        self.assertIn("LESSON   An example lesson.", text)
        self.assertIn("WHY      An example reason the gate exists.", text)
        self.assertIn("WHEN     An example recognition heuristic.", text)
        self.assertIn("AVOID    Work advances while a required question stays open.", text)
        self.assertIn("AIM FOR  An example of the pattern to aim for.", text)
        self.assertIn("An example lesson.", text)
        self.assertIn("An example reason the gate exists.", text)
        self.assertIn("An example recognition heuristic.", text)

    def test_wraps_long_context_under_its_label(self) -> None:
        card = minimal_card()
        card["mentoring"]["lesson"] = "word " * 30

        text = render_mentoring(card)
        lesson_lines = [
            line for line in text.splitlines() if line.startswith(("LESSON", "         "))
        ]

        self.assertGreater(len(lesson_lines), 1)
        self.assertTrue(all(len(line) <= TEXT_WIDTH for line in lesson_lines))

    def test_removes_redundant_recognition_boilerplate(self) -> None:
        card = minimal_card()
        card["mentoring"]["recognition_heuristic"] = (
            "Use this procedure when the exact candidate needs review."
        )

        text = render_mentoring(card)

        self.assertIn("WHEN     The exact candidate needs review.", text)
        self.assertNotIn("Use this procedure when", text)


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
                    "falsifier": "An example refuting observation.",
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
        self.assertIn("CONFIDENCE high", text)
        self.assertIn("An example revisit condition.", text)
        self.assertIn("OWNER    agent", text)
        self.assertIn("[AEC: Decision]", render_human(card, RAIL_DEFINITION))


class RenderHumanTests(unittest.TestCase):
    def test_contains_both_required_blocks_and_a_single_trailing_newline(self) -> None:
        text = render_human(minimal_card(), RAIL_DEFINITION, orientation=True)

        self.assertIn("[AEC: Project Guidance]", text)
        self.assertIn("[AEC: Mentoring]", text)
        self.assertIn("\n────────────────────────────────────────────────────────────────\n", text)
        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))

    def test_dense_render_keeps_both_required_blocks_and_one_trailing_newline(
        self,
    ) -> None:
        text = render_human(minimal_card(), RAIL_DEFINITION)

        self.assertIn("[AEC: Project Guidance]", text)
        self.assertIn("[AEC: Mentoring]", text)
        self.assertNotIn("────", text)
        self.assertNotIn("═", text)
        self.assertTrue(text.endswith("\n"))
        self.assertFalse(text.endswith("\n\n"))

    def test_meaningful_triggers_render_one_complete_card(self) -> None:
        card = minimal_card()

        for trigger in FULL_CARD_TRIGGERS:
            with self.subTest(trigger=trigger):
                text = render_interaction(card, RAIL_DEFINITION, trigger)
                self.assertIn("[AEC: Project Guidance]", text)
                self.assertIn("[AEC: Mentoring]", text)
                self.assertIn("RAIL · Framing · step 2/9", text)

    def test_complete_card_respects_the_plain_text_width_contract(self) -> None:
        card = minimal_card(
            decision_support={
                "authority": {"owner": "consumer", "reason": "Owns the decision."},
                "choices": [
                    {
                        "identity": "bounded-choice",
                        "summary": "A deliberately long summary " * 8,
                        "tradeoffs": {
                            name: f"A deliberately long {name} tradeoff " * 6
                            for name in (
                                "maintainability",
                                "quality",
                                "reversibility",
                                "risk",
                                "scope",
                            )
                        },
                    }
                ],
                "question": "A deliberately long material question " * 6,
                "recommendation": {
                    "choice": "bounded-choice",
                    "confidence": "medium",
                    "expected_result": {
                        "baseline": "0",
                        "direction": "increase",
                        "measure": "bounded-measure",
                        "target": "1",
                        "threshold": "A long measurable threshold " * 4,
                        "unit": "count",
                    },
                    "falsifier": "A deliberately long falsifier " * 6,
                    "principal_uncertainty": "A deliberately long uncertainty " * 6,
                    "revisit_when": ["A deliberately long revisit condition " * 6],
                },
            }
        )
        evidence = [
            {
                "accepted": False,
                "environment": "test",
                "kind": "consumer-context-with-a-deliberately-long-identity",
                "revision": "a" * 40,
            }
        ]

        text = render_human(
            card,
            RAIL_DEFINITION,
            evidence=evidence,
            task_id="task-" + "x" * 200,
        )

        self.assertIn("[AEC: Decision]", text)
        self.assertIn("[Consumer: Evidence Context]", text)
        self.assertLessEqual(max(map(len, text.splitlines())), TEXT_WIDTH)

    def test_oversized_identifier_cannot_escape_the_width_contract(self) -> None:
        text = render_human(
            minimal_card(),
            RAIL_DEFINITION,
            task_id="task-" + "x" * 200,
        )

        self.assertLessEqual(max(map(len, text.splitlines())), TEXT_WIDTH)
        self.assertIn("TASK     task-", text)

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

        self.assertIn("TASK     FedJobAdvisor#9305", text)
        self.assertIn("RAIL · PR · step 8/9", text)
        self.assertIn(revision, text)
        self.assertIn("source-audited · verified", text)
        self.assertIn(
            "[Consumer: Evidence Context]",
            text,
        )
        self.assertIn(
            "PENDING  source-audited · stacked-base-readiness. Consumer fact only; "
            "not an AEC gate.",
            text,
        )
        next_action = next(
            line for line in text.splitlines() if line.startswith("NEXT")
        )
        self.assertNotIn("stacked-base-readiness", next_action)
        self.assertIn("focused-test-report:227", text)
        self.assertIn("test-verified · verified", text)
        self.assertIn(
            "ci-verified · pending (required: current-required-checks)",
            text,
        )
        self.assertNotIn("runtime-verified", text)
        self.assertNotIn("live-data-verified", text)
        self.assertIn(
            "LESSON   A pull request becomes mergeable only when findings and required checks",
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
            "source-audited · partial (verified: base-head-binding; "
            "required: independent-review)",
            text,
        )


def resolved_card_for_phase(phase: str, *, revision: str = "c" * 40) -> dict[str, object]:
    """Resolve one real AEC-self card at `phase`, bypassing no validation."""
    state = build_state(
        task="aec#115",
        phase=phase,
        lane="INFRA",
        environment="local",
        expires_minutes=30,
        evidence=[],
        blockers=[],
        revision=revision,
        catalog=CATALOG,
        workflow=WORKFLOW,
        profile=AEC_SELF_PROFILE,
        observed_at=datetime(2026, 8, 3, 12, 0, tzinfo=timezone.utc),
    )
    result = resolve_consumer_state(
        state,
        CATALOG,
        current_time="2026-08-03T12:01:00Z",
        expected_environment="local",
        expected_revision=revision,
    )
    if isinstance(result, ConsumerStateRejection):  # pragma: no cover - guard
        raise AssertionError(f"fixture state rejected at {phase}")
    return result.to_dict()


def invariant_chrome_lines(text: str, other: str) -> list[str]:
    """Return the lines of `text` that carry no phase-specific information.

    This is issue #115's two-phase diff, applied in-process: a line is
    invariant chrome when it is blank, is a horizontal rule, or is
    byte-identical to a line of a card rendered at a different phase.
    """
    lines = text.splitlines()
    common = set(lines) & set(other.splitlines())
    return [
        line
        for line in lines
        if not line.strip()
        or set(line.strip()) <= set("=-═─")
        or line in common
    ]


def phase_mentions(text: str, phase: str) -> int:
    """Count whole-word mentions of one phase name.

    Substring counting is wrong at short phase names: `"PROOF".count("PR")`
    is 1, so a `PR` card would score every PROOF label as a phase mention and
    the repetition budget below would measure the renderer's vocabulary
    instead of its repetition.
    """
    return len(re.findall(rf"\b{re.escape(phase)}\b", text))


class CardDensityTests(unittest.TestCase):
    """Pins issue #115: a card must be mostly card, not mostly frame."""

    def setUp(self) -> None:
        self.intake = resolved_card_for_phase("Intake")
        self.review = resolved_card_for_phase("Review")
        self.intake_text = render_human(self.intake, RAIL_DEFINITION)
        self.review_text = render_human(self.review, RAIL_DEFINITION)

    def test_dense_card_carries_under_a_quarter_invariant_chrome(self) -> None:
        for text, other in (
            (self.intake_text, self.review_text),
            (self.review_text, self.intake_text),
        ):
            chrome = invariant_chrome_lines(text, other)
            total = len(text.splitlines())
            with self.subTest(total=total):
                self.assertLess(
                    len(chrome) / total,
                    0.25,
                    f"{len(chrome)}/{total} lines are invariant chrome: {chrome}",
                )

    def test_dense_card_names_its_phase_at_most_twice(self) -> None:
        for card, text in (
            (self.intake, self.intake_text),
            (self.review, self.review_text),
        ):
            phase = str(card["phase"])
            with self.subTest(phase=phase):
                self.assertLessEqual(phase_mentions(text, phase), 2, text)

    def test_orientation_render_restores_the_teaching_frame(self) -> None:
        # The suppressed chrome is a render-time choice, not a deletion: the
        # first interaction of a task still teaches the surface.
        text = render_interaction(self.intake, RAIL_DEFINITION, "task-intake")

        self.assertIn("● complete   ◉ current   ○ not reached", text)
        self.assertIn("AEC is advisory and read-only.", text)
        self.assertIn("├", text)
        self.assertIn("═" * 64, text)
        # Even the teaching render does not restate the phase more than twice.
        self.assertLessEqual(
            phase_mentions(text, str(self.intake["phase"])), 2, text
        )

    def test_orientation_triggers_stay_a_pinned_minority(self) -> None:
        # Without this the suppression canary below is vacuous: growing
        # ORIENTATION_TRIGGERS to cover every full-card trigger restores the
        # full frame everywhere - undoing issue #115 - while every `continue`
        # skips its way to green.
        self.assertEqual(
            {"task-intake", "status-request", "phase-transition"},
            set(ORIENTATION_TRIGGERS),
        )
        self.assertEqual(
            ["gate-transition", "gate-failure", "review-finding", "pr-created",
             "deploy-observe"],
            [item for item in FULL_CARD_TRIGGERS if item not in ORIENTATION_TRIGGERS],
        )

    def test_repeat_interaction_render_stays_dense(self) -> None:
        # The density measurement above calls `render_human` directly, so it
        # cannot see a trigger-routing change. This one goes through the real
        # `render_interaction` entry point that consumers use.
        intake = render_interaction(self.intake, RAIL_DEFINITION, "gate-failure")
        review = render_interaction(self.review, RAIL_DEFINITION, "gate-failure")
        for text, other in ((intake, review), (review, intake)):
            chrome = invariant_chrome_lines(text, other)
            total = len(text.splitlines())
            with self.subTest(total=total):
                self.assertLess(
                    len(chrome) / total,
                    0.25,
                    f"{len(chrome)}/{total} lines are invariant chrome: {chrome}",
                )

    def test_repeat_interactions_suppress_the_teaching_frame(self) -> None:
        dense_triggers = [
            item for item in FULL_CARD_TRIGGERS if item not in ORIENTATION_TRIGGERS
        ]
        self.assertTrue(
            dense_triggers,
            "every full-card trigger now orients: the suppression is dead",
        )
        for trigger in dense_triggers:
            with self.subTest(trigger=trigger):
                text = render_interaction(self.intake, RAIL_DEFINITION, trigger)
                self.assertNotIn("● complete   ◉ current   ○ not reached", text)
                self.assertNotIn("AEC is advisory and read-only.", text)
                self.assertNotIn("═" * 64, text)
                # The lesson, the reason for the gate, and the recognition
                # heuristic are never chrome and are never suppressed.
                self.assertIn("LESSON", text)
                self.assertIn("WHY", text)
                self.assertIn("WHEN", text)


class NegativeSpaceSuppressionTests(unittest.TestCase):
    """Red canary for issue #115: suppression must be conditional.

    A change that deletes the BLOCKERS and EVIDENCE lines outright would
    improve the average card by making an exceptional card lie. These tests
    fail on that change and pass on conditional suppression.
    """

    def test_absent_blockers_and_evidence_produce_no_negative_space(self) -> None:
        text = render_human(minimal_card(), RAIL_DEFINITION)

        self.assertNotIn("BLOCKERS", text)
        self.assertNotIn("EVIDENCE", text)

    def test_present_blocker_and_accepted_evidence_still_render(self) -> None:
        revision = "d" * 40
        card = minimal_card(
            phase_name="Review",
            required_proof=["independent-review"],
            revision=revision,
        )
        text = render_human(
            card,
            RAIL_DEFINITION,
            evidence=[
                {
                    "accepted": True,
                    "environment": "test",
                    "kind": "base-head-binding",
                    "revision": revision,
                }
            ],
            blockers=[
                {
                    "active": True,
                    "identity": "consumer-blocker-one",
                    "reason_code": "AUTHORITY_CONFLICT",
                }
            ],
        )

        self.assertIn(
            "BLOCKERS consumer-blocker-one (AUTHORITY_CONFLICT)",
            text,
        )
        self.assertIn("EVIDENCE source-audited · partial", text)
        self.assertIn("base-head-binding", text)

    def test_default_class_evidence_is_not_silently_dropped(self) -> None:
        # `project-verified` is the fallback class of `evidence_class()`, so it
        # covers Intake's own proofs. A category loop that omits it prints a
        # PROOF class that EVIDENCE can never confirm, on the very first card a
        # reader sees. Reds if `project-verified` leaves EVIDENCE_CLASS_ORDER.
        revision = "e" * 40
        card = minimal_card(
            phase_name="Intake",
            required_proof=["owner-and-boundary"],
            revision=revision,
        )
        accepted = {
            "accepted": True,
            "environment": "test",
            "kind": "outcome-statement",
            "revision": revision,
        }

        self.assertEqual("project-verified", evidence_class("outcome-statement"))
        self.assertEqual("project-verified", evidence_class("owner-and-boundary"))

        text = render_human(card, RAIL_DEFINITION, evidence=[accepted])

        self.assertIn("PROOF    project-verified · owner-and-boundary", text)
        self.assertIn(
            "EVIDENCE project-verified · partial (verified: outcome-statement; "
            "required: owner-and-boundary)",
            text,
        )

    def test_every_evidence_class_can_reach_an_evidence_line(self) -> None:
        # The reachability invariant behind the test above, stated directly:
        # no kind may classify into a category the renderer never prints.
        reachable = set(EVIDENCE_CLASS_ORDER)
        classified = {
            evidence_class(kind)
            for kind in (*EVIDENCE_CLASS_BY_KIND, "focused-test-report:unit", "unmapped")
        }

        self.assertEqual(set(), classified - reachable)


    def test_validated_blocked_gate_still_renders_its_rationale(self) -> None:
        card = minimal_card()
        card["gate"] = "Blocked"
        card["rationale"] = {"summary": "An example validated blocker summary."}

        text = render_human(card, RAIL_DEFINITION)

        self.assertIn("BLOCKERS An example validated blocker summary.", text)
        self.assertIn("blocker gate", text)


class PhaseCueTests(unittest.TestCase):
    """A dense card must still say, unambiguously, which phase you are in."""

    def test_resolved_card_names_its_own_phase_in_words(self) -> None:
        # Ready + no required proof is the case where NEXT names the *next*
        # phase. Without a worded cue the current phase survives only as an
        # unlabeled `◉` - the legend is suppressed - so a reader can read
        # themselves into the following phase.
        card = minimal_card(phase_name="Framing")
        card["gate"] = "Ready"

        text = render_human(card, RAIL_DEFINITION)
        rail_summary = next(
            line for line in text.splitlines() if line.startswith("RAIL ·")
        )

        self.assertIn("RAIL · Framing · step 2/9", rail_summary)
        self.assertIn("Check whether", text)
        self.assertLessEqual(phase_mentions(text, "Framing"), 2, text)

    def test_rail_summary_names_the_marked_phase_in_both_modes(self) -> None:
        card = minimal_card(phase_name="Framing")
        for orientation in (True, False):
            with self.subTest(orientation=orientation):
                text = render_rail(card, RAIL_DEFINITION, orientation=orientation)
                self.assertIn("RAIL · Framing · step 2/9 · Understand 2/2", text)


if __name__ == "__main__":
    unittest.main()
