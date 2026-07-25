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
    PREVIOUS_CONTRACT_FIXTURE,
    ConnectionFailure,
    diagnose_decision_context,
    resolve_probe,
    run_probe,
    self_check,
    validate_connection,
)


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
            run_probe("previous-contract", PREVIOUS_CONTRACT_FIXTURE, self.catalog)


class ActionableFailureMessageTests(unittest.TestCase):
    """G4: the failure message names specific fields, not a generic verdict."""

    def setUp(self) -> None:
        self.state = load_json(PREVIOUS_CONTRACT_FIXTURE)
        assert isinstance(self.state, dict)

    def test_diagnosis_names_the_missing_top_level_fields(self) -> None:
        findings = diagnose_decision_context(self.state["decision_context"])

        joined = " ".join(findings)
        self.assertIn("context", joined)
        self.assertIn("schema_version", joined)
        self.assertIn("missing required fields", joined)

    def test_diagnosis_names_the_missing_recommendation_fields(self) -> None:
        findings = diagnose_decision_context(self.state["decision_context"])

        joined = " ".join(findings)
        self.assertIn("recommendation", joined)
        self.assertIn("confidence", joined)
        self.assertIn("expected_result", joined)
        self.assertIn("principal_uncertainty", joined)

    def test_diagnosis_is_empty_for_an_absent_decision_context(self) -> None:
        self.assertEqual([], diagnose_decision_context(None))

    def test_diagnosis_is_empty_for_a_compliant_material_probe(self) -> None:
        material = load_json(DEFAULT_MATERIAL_PROBE)
        assert isinstance(material, dict)

        self.assertEqual([], diagnose_decision_context(material["decision_context"]))

    def test_run_probe_failure_message_carries_the_field_level_diagnosis(self) -> None:
        catalog = load_json(DEFAULT_CATALOG)

        with self.assertRaises(ConnectionFailure) as context:
            run_probe("previous-contract", PREVIOUS_CONTRACT_FIXTURE, catalog)

        message = str(context.exception)
        self.assertNotEqual("validation failed", message.strip().lower())
        self.assertIn("schema_version", message)
        self.assertIn("context", message)
        self.assertIn("confidence", message)
        self.assertIn("expected_result", message)
        self.assertIn("principal_uncertainty", message)

    def test_self_check_proves_the_negative_path_and_field_level_guidance(self) -> None:
        self_check(DEFAULT_CATALOG)  # must not raise


if __name__ == "__main__":
    unittest.main()
