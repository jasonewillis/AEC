import copy
import json
import unittest
from pathlib import Path

from aec.cards import (
    PUBLIC_CARD_FIELDS,
    PUBLIC_CARD_SCHEMA_VERSION,
    compute_card_hash,
    validate_public_card,
)
from aec.consumer import ConsumerCard, resolve_consumer_state


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "outcomes"


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def rendered_card() -> dict[str, object]:
    """Render the worked material-decision card through the public adapter."""
    state = load_json(FIXTURES / "proposal.json")
    assert isinstance(state, dict)
    result = resolve_consumer_state(
        state,
        load_json(ROOT / "config/procedures/ticket-to-pr.json"),
        current_time="2026-01-01T00:30:00Z",
        expected_environment="test",
        expected_revision="0123456789abcdef0123456789abcdef01234567",
    )
    assert isinstance(result, ConsumerCard)
    return result.to_dict()


class PublicCardIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.card = rendered_card()

    def test_rendering_computes_the_card_hash_validation_recomputes_it(self) -> None:
        self.assertEqual(PUBLIC_CARD_SCHEMA_VERSION, self.card["schema_version"])
        self.assertEqual(set(PUBLIC_CARD_FIELDS), set(self.card))
        self.assertEqual(self.card["card_hash"], compute_card_hash(self.card))
        self.assertRegex(str(self.card["card_hash"]), r"^sha256:[0-9a-f]{64}$")
        self.assertEqual([], validate_public_card(self.card))

    def test_the_hash_covers_every_field_except_itself(self) -> None:
        without_hash = {
            name: value for name, value in self.card.items() if name != "card_hash"
        }
        self.assertEqual(self.card["card_hash"], compute_card_hash(without_hash))

        for name in sorted(set(self.card) - {"card_hash"}):
            with self.subTest(field=name):
                tampered = copy.deepcopy(self.card)
                tampered[name] = None
                self.assertNotEqual(self.card["card_hash"], compute_card_hash(tampered))

    def test_missing_or_unknown_card_fields_fail_closed(self) -> None:
        for name in sorted(PUBLIC_CARD_FIELDS):
            with self.subTest(missing=name):
                incomplete = copy.deepcopy(self.card)
                del incomplete[name]
                self.assertTrue(validate_public_card(incomplete))

        unknown = copy.deepcopy(self.card)
        unknown["telemetry_endpoint"] = "https://example.invalid"
        self.assertTrue(validate_public_card(unknown))

    def test_non_object_cards_fail_closed(self) -> None:
        for value in (None, [], "card", 1, True):
            with self.subTest(value=value):
                self.assertTrue(validate_public_card(value))

    def test_malformed_card_values_fail_closed(self) -> None:
        cases = (
            ("authoritative", True),
            ("gate", "green"),
            ("phase", "Refactor"),
            ("lane", ""),
            ("anti_example", ""),
            ("finished", []),
            ("good", ["  "]),
            ("required_proof", "vertical-slice-plan"),
            ("resolution_hash", "sha256:not-a-digest"),
            ("schema_version", "2.0.0"),
            ("mentoring", {"lesson": "x"}),
            ("rationale", {"summary": "x"}),
            ("rail_position", {"stage": "Design"}),
            ("transition_request", {"revision": "HEAD"}),
            ("decision_support", {"schema_version": "2.0.0"}),
            ("observation_support", {"schema_version": "1.0.0"}),
        )
        for name, value in cases:
            with self.subTest(field=name):
                malformed = copy.deepcopy(self.card)
                malformed[name] = value
                malformed["card_hash"] = compute_card_hash(malformed)
                self.assertTrue(validate_public_card(malformed))

    def test_internally_inconsistent_cards_fail_closed(self) -> None:
        wrong_gate = copy.deepcopy(self.card)
        wrong_gate["transition_request"]["requested_gate"] = "Ready"
        wrong_gate["card_hash"] = compute_card_hash(wrong_gate)
        self.assertTrue(validate_public_card(wrong_gate))

        wrong_rail = copy.deepcopy(self.card)
        wrong_rail["rail_position"]["rail"] = 1
        wrong_rail["card_hash"] = compute_card_hash(wrong_rail)
        self.assertTrue(validate_public_card(wrong_rail))

        wrong_stage = copy.deepcopy(self.card)
        wrong_stage["rail_position"]["stage"] = "Execute"
        wrong_stage["card_hash"] = compute_card_hash(wrong_stage)
        self.assertTrue(validate_public_card(wrong_stage))

        foreign_revision = copy.deepcopy(self.card)
        foreign_revision["decision_support"]["context"]["revision"] = "f" * 40
        foreign_revision["card_hash"] = compute_card_hash(foreign_revision)
        self.assertTrue(validate_public_card(foreign_revision))

        foreign_observation_revision = copy.deepcopy(self.card)
        foreign_observation_revision["observation_support"]["context"]["revision"] = (
            "f" * 40
        )
        foreign_observation_revision["card_hash"] = compute_card_hash(
            foreign_observation_revision
        )
        self.assertTrue(validate_public_card(foreign_observation_revision))

    def test_tampered_cards_fail_closed_on_the_recomputed_hash(self) -> None:
        tampered = copy.deepcopy(self.card)
        tampered["gate"] = "Ready"
        errors = validate_public_card(tampered)
        self.assertTrue(any("card_hash" in error for error in errors))

        missing_hash = copy.deepcopy(self.card)
        missing_hash["card_hash"] = "sha256:" + "0" * 64
        self.assertTrue(validate_public_card(missing_hash))

    def test_a_routine_card_without_a_material_decision_stays_valid(self) -> None:
        routine = copy.deepcopy(self.card)
        routine["decision_support"] = None
        routine["card_hash"] = compute_card_hash(routine)
        self.assertEqual([], validate_public_card(routine))

    def test_a_routine_card_without_an_observation_stays_valid(self) -> None:
        routine = copy.deepcopy(self.card)
        routine["observation_support"] = None
        routine["card_hash"] = compute_card_hash(routine)
        self.assertEqual([], validate_public_card(routine))


if __name__ == "__main__":
    unittest.main()
