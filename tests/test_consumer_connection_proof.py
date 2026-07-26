"""Consumer-visible compatibility signal for a pinned AEC checkout.

Covers the incident behind AEC #55: `d35f535` tightened `decision_context`
and a consumer pinned to the previous shape only found out when its own
suite went red, because its routine connection check never exercised a
material-decision card. These tests prove the connection proof in
`tools/validate_consumer_connection.py` catches that class of break before
any card is rendered, and names the exact fields a consumer must change.
"""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from aec.consumer import ConsumerCard, ConsumerStateRejection
from tools.validate_consumer_connection import (
    DEFAULT_CATALOG,
    DEFAULT_MATERIAL_PROBE,
    DEFAULT_ROUTINE_PROBE,
    PREVIOUS_CONTRACT_EXPECTED_MISSING_FIELDS,
    PREVIOUS_CONTRACT_FIXTURE,
    ConnectionFailure,
    DecisionContextDiagnosis,
    diagnose_decision_context,
    resolve_probe,
    run_probe,
    self_check,
    validate_connection,
)
from tools.validate_consumer_connection import _verify_previous_contract_diagnosis


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


class RoutineProbeTests(unittest.TestCase):
    """G1: a routine probe (no decision_context) passes against current AEC."""

    def test_routine_probe_has_no_decision_context(self) -> None:
        state = load_json(DEFAULT_ROUTINE_PROBE)
        assert isinstance(state, dict)
        self.assertNotIn("decision_context", state)

    def test_routine_probe_resolves_to_a_non_authoritative_card(self) -> None:
        catalog = load_json(DEFAULT_CATALOG)
        state = load_json(DEFAULT_ROUTINE_PROBE)
        result = resolve_probe(state, catalog)

        self.assertIsInstance(result, ConsumerCard)
        card = result.to_dict()
        self.assertIsNone(card["decision_support"])
        self.assertFalse(card["authoritative"])
        self.assertFalse(card["transition_request"]["executes"])
        self.assertFalse(card["transition_request"]["mutates"])

    def test_full_connection_proof_reports_pass(self) -> None:
        receipt = validate_connection(
            DEFAULT_ROUTINE_PROBE, DEFAULT_MATERIAL_PROBE, DEFAULT_CATALOG
        )

        self.assertEqual("PASS", receipt["status"])
        routine = next(p for p in receipt["probes"] if p["probe"] == "routine")
        self.assertEqual("PASS", routine["status"])
        self.assertFalse(routine["has_decision_support"])

    def test_routine_probe_rejects_a_material_expectation(self) -> None:
        """F1 red canary: a routine probe run with expect_decision_support=True
        must fail, because it never renders decision_support."""
        catalog = load_json(DEFAULT_CATALOG)

        with self.assertRaises(ConnectionFailure):
            run_probe(
                "routine",
                DEFAULT_ROUTINE_PROBE,
                catalog,
                expect_decision_support=True,
            )


class MaterialProbeTests(unittest.TestCase):
    """G2: a material-decision probe (with decision_context) passes."""

    def test_material_probe_declares_a_closed_decision_context(self) -> None:
        state = load_json(DEFAULT_MATERIAL_PROBE)
        assert isinstance(state, dict)
        self.assertIn("decision_context", state)
        self.assertIn(len(state["decision_context"]["choices"]), (2, 3))

    def test_material_probe_resolves_to_a_non_authoritative_decision_brief(self) -> None:
        catalog = load_json(DEFAULT_CATALOG)
        state = load_json(DEFAULT_MATERIAL_PROBE)
        result = resolve_probe(state, catalog)

        self.assertIsInstance(result, ConsumerCard)
        card = result.to_dict()
        self.assertIsNotNone(card["decision_support"])
        self.assertFalse(card["authoritative"])
        self.assertFalse(card["transition_request"]["executes"])
        self.assertFalse(card["transition_request"]["mutates"])

    def test_full_connection_proof_covers_the_material_probe(self) -> None:
        receipt = validate_connection(
            DEFAULT_ROUTINE_PROBE, DEFAULT_MATERIAL_PROBE, DEFAULT_CATALOG
        )

        material = next(p for p in receipt["probes"] if p["probe"] == "material")
        self.assertEqual("PASS", material["status"])
        self.assertTrue(material["has_decision_support"])

    def test_material_probe_rejects_a_routine_expectation(self) -> None:
        """F1 red canary: a material probe run with expect_decision_support=False
        must fail, because it always renders decision_support."""
        catalog = load_json(DEFAULT_CATALOG)

        with self.assertRaises(ConnectionFailure):
            run_probe(
                "material",
                DEFAULT_MATERIAL_PROBE,
                catalog,
                expect_decision_support=False,
            )


class ProbeSlotMismatchTests(unittest.TestCase):
    """F1 (HIGH): the wrong fixture in either slot must fail, not report PASS.

    Before the fix, `run_probe` reported `has_decision_support` without ever
    asserting it, so `validate_connection` returned `status: PASS` regardless
    of which fixture occupied which slot. These reproduce the exact swap
    Codex flagged: the routine fixture handed to `--material`, and the
    material fixture handed to `--routine`.
    """

    def test_routine_fixture_passed_as_material_fails(self) -> None:
        """G1: the routine fixture (no decision_context) cannot pass as MATERIAL."""
        with self.assertRaises(ConnectionFailure) as context:
            validate_connection(
                DEFAULT_ROUTINE_PROBE, DEFAULT_ROUTINE_PROBE, DEFAULT_CATALOG
            )
        self.assertIn("decision_support mismatch", str(context.exception))

    def test_material_fixture_passed_as_routine_fails(self) -> None:
        """G2: the material fixture (a closed decision_context) cannot pass as ROUTINE."""
        with self.assertRaises(ConnectionFailure) as context:
            validate_connection(
                DEFAULT_MATERIAL_PROBE, DEFAULT_MATERIAL_PROBE, DEFAULT_CATALOG
            )
        self.assertIn("decision_support mismatch", str(context.exception))


class PreviousContractFixtureTests(unittest.TestCase):
    """G3/G5: a fixture pinned to the previous contract fails before a card renders."""

    def setUp(self) -> None:
        self.catalog = load_json(DEFAULT_CATALOG)
        self.state = load_json(PREVIOUS_CONTRACT_FIXTURE)
        assert isinstance(self.state, dict)

    def test_previous_contract_fixture_reproduces_the_pre_48_shape(self) -> None:
        context = self.state["decision_context"]
        self.assertNotIn("schema_version", context)
        self.assertNotIn("context", context)
        self.assertNotIn("confidence", context["recommendation"])
        self.assertNotIn("expected_result", context["recommendation"])
        self.assertNotIn("principal_uncertainty", context["recommendation"])

    def test_previous_contract_fixture_is_rejected_not_resolved(self) -> None:
        with patch("aec.consumer.resolve") as resolver:
            result = resolve_probe(self.state, self.catalog)

        self.assertIsInstance(result, ConsumerStateRejection)
        rejection = result.to_dict()
        self.assertFalse(rejection["accepted"])
        self.assertIsNone(rejection["card"])
        self.assertEqual("CONSUMER_STATE_INVALID", rejection["code"])
        resolver.assert_not_called()

    def test_run_probe_raises_a_connection_failure_for_the_previous_contract(self) -> None:
        with self.assertRaises(ConnectionFailure):
            run_probe(
                "previous-contract",
                PREVIOUS_CONTRACT_FIXTURE,
                self.catalog,
                expect_decision_support=True,
            )


class ActionableFailureMessageTests(unittest.TestCase):
    """G4: the failure message names specific fields, not a generic verdict."""

    def setUp(self) -> None:
        self.state = load_json(PREVIOUS_CONTRACT_FIXTURE)
        assert isinstance(self.state, dict)

    def test_diagnosis_names_the_missing_top_level_fields(self) -> None:
        diagnosis = diagnose_decision_context(self.state["decision_context"])

        joined = " ".join(diagnosis.messages)
        self.assertIn("context", joined)
        self.assertIn("schema_version", joined)
        self.assertIn("missing required fields", joined)

    def test_diagnosis_names_the_missing_recommendation_fields(self) -> None:
        diagnosis = diagnose_decision_context(self.state["decision_context"])

        joined = " ".join(diagnosis.messages)
        self.assertIn("recommendation", joined)
        self.assertIn("confidence", joined)
        self.assertIn("expected_result", joined)
        self.assertIn("principal_uncertainty", joined)

    def test_diagnosis_missing_fields_is_exactly_the_five_pre_48_gaps(self) -> None:
        """G4/structural: missing_fields is exact field names, not prose."""
        diagnosis = diagnose_decision_context(self.state["decision_context"])

        self.assertEqual(
            PREVIOUS_CONTRACT_EXPECTED_MISSING_FIELDS, diagnosis.missing_fields
        )

    def test_diagnosis_is_empty_for_an_absent_decision_context(self) -> None:
        diagnosis = diagnose_decision_context(None)
        self.assertEqual((), diagnosis.messages)
        self.assertEqual(frozenset(), diagnosis.missing_fields)

    def test_diagnosis_is_empty_for_a_compliant_material_probe(self) -> None:
        material = load_json(DEFAULT_MATERIAL_PROBE)
        assert isinstance(material, dict)

        diagnosis = diagnose_decision_context(material["decision_context"])
        self.assertEqual((), diagnosis.messages)
        self.assertEqual(frozenset(), diagnosis.missing_fields)

    def test_diagnosis_covers_authority_choices_tradeoffs_and_expected_result(self) -> None:
        """F2: the diagnosis must not stop at decision_context/context/recommendation.

        Strips one field from each of authority, a choice, its tradeoffs, and
        recommendation.expected_result (leaving the top-level and recommendation
        field sets otherwise closed) and asserts each break is still named.
        """
        material = load_json(DEFAULT_MATERIAL_PROBE)
        assert isinstance(material, dict)
        context = material["decision_context"]

        del context["authority"]["reason"]
        del context["choices"][0]["summary"]
        del context["choices"][0]["tradeoffs"]["risk"]
        del context["recommendation"]["expected_result"]["unit"]

        diagnosis = diagnose_decision_context(context)

        self.assertIn("reason", diagnosis.missing_fields)
        self.assertIn("summary", diagnosis.missing_fields)
        self.assertIn("risk", diagnosis.missing_fields)
        self.assertIn("unit", diagnosis.missing_fields)
        joined = " ".join(diagnosis.messages)
        self.assertIn("decision_context.authority", joined)
        self.assertIn("decision_context.choices[0]", joined)
        self.assertIn("decision_context.choices[0].tradeoffs", joined)
        self.assertIn("decision_context.recommendation.expected_result", joined)

    def test_run_probe_failure_message_carries_the_field_level_diagnosis(self) -> None:
        catalog = load_json(DEFAULT_CATALOG)

        with self.assertRaises(ConnectionFailure) as context:
            run_probe(
                "previous-contract",
                PREVIOUS_CONTRACT_FIXTURE,
                catalog,
                expect_decision_support=True,
            )

        message = str(context.exception)
        self.assertNotEqual("validation failed", message.strip().lower())
        self.assertIn("schema_version", message)
        self.assertIn("context", message)
        self.assertIn("confidence", message)
        self.assertIn("expected_result", message)
        self.assertIn("principal_uncertainty", message)

    def test_self_check_proves_the_negative_path_and_field_level_guidance(self) -> None:
        self_check(DEFAULT_CATALOG)  # must not raise


class SelfCheckStructuralAssertionTests(unittest.TestCase):
    """G3: self-check's assertion must be structural, and must be able to fail.

    A substring test against `diagnosis.messages` cannot fail here: every
    message begins with the literal `"decision_context"`, which contains the
    substring `"context"`. `_verify_previous_contract_diagnosis` instead
    matches on `diagnosis.missing_fields`, an exact set of field names. These
    tests construct diagnoses with one expected field missing from that set
    -- as `diagnose_decision_context` would produce if it silently stopped
    reporting that field -- and prove the assertion actually rejects them.
    """

    def test_full_expected_diagnosis_passes(self) -> None:
        diagnosis = DecisionContextDiagnosis(
            messages=("decision_context is missing required fields: context, schema_version",),
            missing_fields=PREVIOUS_CONTRACT_EXPECTED_MISSING_FIELDS,
        )
        _verify_previous_contract_diagnosis(diagnosis)  # must not raise

    def test_diagnosis_missing_one_expected_field_fails(self) -> None:
        """Red canary: drop one of the five fields diagnose_decision_context
        should have reported, and confirm the structural check rejects it."""
        for dropped in sorted(PREVIOUS_CONTRACT_EXPECTED_MISSING_FIELDS):
            with self.subTest(dropped=dropped):
                incomplete = DecisionContextDiagnosis(
                    messages=("decision_context is missing required fields: something",),
                    missing_fields=PREVIOUS_CONTRACT_EXPECTED_MISSING_FIELDS - {dropped},
                )
                with self.assertRaises(ConnectionFailure):
                    _verify_previous_contract_diagnosis(incomplete)

    def test_a_message_that_only_mentions_context_by_substring_still_fails(self) -> None:
        """The exact bug F3 named: a message containing the substring "context"
        must not be enough to satisfy the check when missing_fields disagrees."""
        diagnosis = DecisionContextDiagnosis(
            messages=("decision_context fields do not match the contract",),
            missing_fields=frozenset(),
        )
        with self.assertRaises(ConnectionFailure):
            _verify_previous_contract_diagnosis(diagnosis)

    def test_empty_diagnosis_fails(self) -> None:
        with self.assertRaises(ConnectionFailure):
            _verify_previous_contract_diagnosis(DecisionContextDiagnosis((), frozenset()))


if __name__ == "__main__":
    unittest.main()
