"""Consumer-visible compatibility signal for a pinned AEC checkout.

Covers the incident behind AEC #55: `d35f535` tightened `decision_context`
and a consumer pinned to the previous shape only found out when its own
suite went red, because its routine connection check never exercised a
material-decision card. These tests prove the connection proof in
`tools/validate_consumer_connection.py` catches that class of break before
any card is rendered, and names the exact fields a consumer must change.
"""

import copy
import json
import re
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
MISSING_FIELDS_PATTERN = re.compile(r"is missing required fields: (?P<names>.+)$")


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def field_names_from_messages(messages: tuple) -> set:
    """Parse the field names out of every "is missing required fields" message.

    Used only to prove the missing_fields/messages binding empirically
    (MissingFieldsMessagesInvariantTests); never used as a substring test on
    its own, since a regex match on the literal marker phrase followed by an
    exact comma-split is unambiguous, not a short-token substring check.
    """
    names: set = set()
    for message in messages:
        match = MISSING_FIELDS_PATTERN.search(message)
        if match:
            names.update(name.strip() for name in match.group("names").split(", "))
    return names


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
        self.assertTrue("decision_context" in state)
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
        self.assertTrue("decision_support mismatch" in str(context.exception))

    def test_material_fixture_passed_as_routine_fails(self) -> None:
        """G2: the material fixture (a closed decision_context) cannot pass as ROUTINE."""
        with self.assertRaises(ConnectionFailure) as context:
            validate_connection(
                DEFAULT_MATERIAL_PROBE, DEFAULT_MATERIAL_PROBE, DEFAULT_CATALOG
            )
        self.assertTrue("decision_support mismatch" in str(context.exception))


class FakeCard:
    """A stand-in for `aec.consumer.ConsumerCard` carrying a fixed dict.

    Used only to construct cards `resolve_consumer_state` would never
    actually render (an authoritative one), so `run_probe`'s own guard is
    what has to reject it, not the real adapter's validation.
    """

    def __init__(self, card: dict) -> None:
        self._card = card

    def to_dict(self) -> dict:
        return self._card


def _non_authoritative_card(**overrides: object) -> dict:
    card = {
        "gate": "Evidence needed",
        "authoritative": False,
        "decision_support": None,
        "transition_request": {
            "authoritative": False,
            "environment": "test",
            "executes": False,
            "mutates": False,
            "requested_gate": "Evidence needed",
            "revision": "0" * 40,
        },
    }
    card.update(overrides)
    return card


class AuthoritativeCardRejectionTests(unittest.TestCase):
    """F6 (HIGH): a card claiming authority must be rejected, not passed.

    Before this fix, `run_probe` checked `transition_request.executes` and
    `.mutates` but never `authoritative`, at either of its two locations on
    the card (the top-level field and `transition_request.authoritative`).
    AEC is never an authority owner (see docs/architecture/consumer-contract.md), so a
    card claiming authority is a contract violation the connection proof
    exists to catch. `resolve_consumer_state` never actually renders such a
    card today, so these tests construct one directly with a FakeCard and
    patch `resolve_probe` to return it, proving run_probe's own guard is
    what rejects it.
    """

    def test_top_level_authoritative_true_is_rejected(self) -> None:
        """G1/G3: checking transition_request alone would miss this card,
        because its transition_request.authoritative is correctly False."""
        catalog = load_json(DEFAULT_CATALOG)
        card = _non_authoritative_card(authoritative=True)

        with patch(
            "tools.validate_consumer_connection.resolve_probe",
            return_value=FakeCard(card),
        ):
            with self.assertRaises(ConnectionFailure) as context:
                run_probe(
                    "routine",
                    DEFAULT_ROUTINE_PROBE,
                    catalog,
                    expect_decision_support=False,
                )
        self.assertTrue("authoritative decision" in str(context.exception))

    def test_transition_request_authoritative_true_is_rejected(self) -> None:
        """G3: checking the top-level field alone would miss this card,
        because its top-level authoritative is correctly False."""
        catalog = load_json(DEFAULT_CATALOG)
        card = _non_authoritative_card(
            transition_request={
                "authoritative": True,
                "environment": "test",
                "executes": False,
                "mutates": False,
                "requested_gate": "Evidence needed",
                "revision": "0" * 40,
            }
        )

        with patch(
            "tools.validate_consumer_connection.resolve_probe",
            return_value=FakeCard(card),
        ):
            with self.assertRaises(ConnectionFailure) as context:
                run_probe(
                    "routine",
                    DEFAULT_ROUTINE_PROBE,
                    catalog,
                    expect_decision_support=False,
                )
        self.assertTrue("authoritative decision" in str(context.exception))

    def test_a_genuinely_non_authoritative_card_passes(self) -> None:
        """G2 green half: the same shape with both fields False must pass,
        so the guard rejects on the claim, not on any other property."""
        catalog = load_json(DEFAULT_CATALOG)
        card = _non_authoritative_card()

        with patch(
            "tools.validate_consumer_connection.resolve_probe",
            return_value=FakeCard(card),
        ):
            result = run_probe(
                "routine",
                DEFAULT_ROUTINE_PROBE,
                catalog,
                expect_decision_support=False,
            )
        self.assertEqual("PASS", result["status"])


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
        """Structural, not a substring test: every message here begins with the
        literal "decision_context", which itself contains the substring
        "context", so a substring test against joined messages cannot fail on
        that field. Assert on missing_fields (structured) and, separately, one
        exact full message string for the human-readable wording."""
        diagnosis = diagnose_decision_context(self.state["decision_context"])

        self.assertTrue({"context", "schema_version"} <= diagnosis.missing_fields)
        self.assertTrue(
            "decision_context is missing required fields: context, schema_version"
            in diagnosis.messages
        )

    def test_diagnosis_names_the_missing_recommendation_fields(self) -> None:
        diagnosis = diagnose_decision_context(self.state["decision_context"])

        self.assertTrue(
            {"confidence", "expected_result", "falsifier", "principal_uncertainty"}
            <= diagnosis.missing_fields
        )
        self.assertTrue(
            "decision_context.recommendation is missing required fields: "
            "confidence, expected_result, falsifier, principal_uncertainty"
            in diagnosis.messages
        )

    def test_diagnosis_missing_fields_is_exactly_the_pre_48_gaps(self) -> None:
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

        self.assertTrue({"reason", "summary", "risk", "unit"} <= diagnosis.missing_fields)
        self.assertTrue(
            "decision_context.authority is missing required fields: reason"
            in diagnosis.messages
        )
        self.assertTrue(
            "decision_context.choices[0] is missing required fields: summary"
            in diagnosis.messages
        )
        self.assertTrue(
            "decision_context.choices[0].tradeoffs is missing required fields: risk"
            in diagnosis.messages
        )
        self.assertTrue(
            "decision_context.recommendation.expected_result is missing required "
            "fields: unit" in diagnosis.messages
        )

    def test_run_probe_failure_message_carries_the_field_level_diagnosis(self) -> None:
        """Checks that run_probe's exception carries every full diagnosis
        message verbatim, not a short ambiguous token. A short token like
        "context" would be a tautology (see the class docstring above); a
        complete message sentence is unambiguous provenance, not a guess."""
        catalog = load_json(DEFAULT_CATALOG)
        diagnosis = diagnose_decision_context(self.state["decision_context"])
        self.assertTrue(diagnosis.messages)

        with self.assertRaises(ConnectionFailure) as context:
            run_probe(
                "previous-contract",
                PREVIOUS_CONTRACT_FIXTURE,
                catalog,
                expect_decision_support=True,
            )

        message = str(context.exception)
        self.assertNotEqual("validation failed", message.strip().lower())
        for full_message in diagnosis.messages:
            self.assertTrue(full_message in message)

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


class NullNestedFieldDiagnosisTests(unittest.TestCase):
    """F4: a present-but-null nested field must still produce a diagnostic.

    Before this fix, `recommendation: None` fell through both branches of the
    old `if type(recommendation) is dict: ... elif recommendation is not
    None: ...` check (the `elif` explicitly excluded None) and produced total
    silence: no message, no missing_fields entry, nothing a consumer could
    act on, immediately before a rejection with no guidance -- precisely the
    failure AEC #55 exists to eliminate. `context`, `authority`, `choices`,
    and one `choices[i]` element are checked here for the same hole; all four
    already handled null correctly (their code checks `type(...) is not
    dict/list`, which is true for None too), but nothing had proven that
    before, so it is pinned here alongside the actual fix.
    """

    def setUp(self) -> None:
        material = load_json(DEFAULT_MATERIAL_PROBE)
        assert isinstance(material, dict)
        self.context = material["decision_context"]

    def test_null_recommendation_is_named(self) -> None:
        mutated = copy.deepcopy(self.context)
        mutated["recommendation"] = None

        diagnosis = diagnose_decision_context(mutated)

        self.assertTrue(diagnosis.messages)
        self.assertTrue(
            "decision_context.recommendation must be an object" in diagnosis.messages
        )

    def test_null_context_is_named(self) -> None:
        mutated = copy.deepcopy(self.context)
        mutated["context"] = None

        diagnosis = diagnose_decision_context(mutated)

        self.assertTrue(diagnosis.messages)
        self.assertTrue("decision_context.context must be an object" in diagnosis.messages)

    def test_null_authority_is_named(self) -> None:
        mutated = copy.deepcopy(self.context)
        mutated["authority"] = None

        diagnosis = diagnose_decision_context(mutated)

        self.assertTrue(diagnosis.messages)
        self.assertTrue("decision_context.authority must be an object" in diagnosis.messages)

    def test_null_choices_is_named(self) -> None:
        mutated = copy.deepcopy(self.context)
        mutated["choices"] = None

        diagnosis = diagnose_decision_context(mutated)

        self.assertTrue(diagnosis.messages)
        self.assertTrue("decision_context.choices must be a list" in diagnosis.messages)

    def test_null_choice_element_is_named(self) -> None:
        mutated = copy.deepcopy(self.context)
        mutated["choices"][0] = None

        diagnosis = diagnose_decision_context(mutated)

        self.assertTrue(diagnosis.messages)
        self.assertTrue(
            "decision_context.choices[0] must be an object" in diagnosis.messages
        )


class MissingFieldsMessagesInvariantTests(unittest.TestCase):
    """G4: missing_fields and the "missing required fields" messages must agree.

    Design choice: derive, not just test. `diagnose_decision_context` writes
    both surfaces from one call to the shared `_report_missing` helper (see
    `tools/validate_consumer_connection.py`), so a "missing required fields"
    message and its matching `missing_fields` entries are always written
    together from the same source list -- they cannot diverge by
    construction. This class proves that binding holds empirically across a
    range of decision_context shapes, as a regression backstop in case a
    future edit reintroduces a direct `findings.append(...)` /
    `missing_fields.update(...)` pair instead of going through the helper.
    """

    def _assert_consistent(self, diagnosis: DecisionContextDiagnosis) -> None:
        self.assertEqual(
            field_names_from_messages(diagnosis.messages), diagnosis.missing_fields
        )

    def test_previous_contract_fixture_is_consistent(self) -> None:
        state = load_json(PREVIOUS_CONTRACT_FIXTURE)
        assert isinstance(state, dict)
        self._assert_consistent(diagnose_decision_context(state["decision_context"]))

    def test_compliant_material_probe_is_consistent(self) -> None:
        material = load_json(DEFAULT_MATERIAL_PROBE)
        assert isinstance(material, dict)
        self._assert_consistent(diagnose_decision_context(material["decision_context"]))

    def test_multi_field_strip_is_consistent(self) -> None:
        material = load_json(DEFAULT_MATERIAL_PROBE)
        assert isinstance(material, dict)
        context = material["decision_context"]
        del context["authority"]["reason"]
        del context["choices"][0]["summary"]
        del context["choices"][0]["tradeoffs"]["risk"]
        del context["recommendation"]["expected_result"]["unit"]
        self._assert_consistent(diagnose_decision_context(context))

    def test_null_nested_fields_are_consistent(self) -> None:
        material = load_json(DEFAULT_MATERIAL_PROBE)
        assert isinstance(material, dict)
        for field in ("recommendation", "context", "authority", "choices"):
            with self.subTest(field=field):
                mutated = copy.deepcopy(material["decision_context"])
                mutated[field] = None
                self._assert_consistent(diagnose_decision_context(mutated))


if __name__ == "__main__":
    unittest.main()
