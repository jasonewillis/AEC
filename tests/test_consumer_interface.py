import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from aec.consumer import (
    ConsumerCard,
    ConsumerStateRejection,
    resolve_consumer_state,
    validate_consumer_state,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "consumer-state"


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def materialize_case(state: dict[str, object], case: dict[str, object]) -> object:
    value = copy.deepcopy(state)
    path = case["path"]
    assert isinstance(path, list)
    target = value
    for part in path[:-1]:
        assert isinstance(target, dict)
        target = target[part]
    operation = case["operation"]
    if operation == "remove":
        assert isinstance(target, dict)
        del target[path[-1]]
    elif operation == "replace":
        assert isinstance(target, dict)
        target[path[-1]] = case["value"]
    return value


class ConsumerStateContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = load_json(FIXTURES / "valid.json")
        assert isinstance(self.state, dict)
        self.catalog = load_json(ROOT / "config/procedures/ticket-to-pr.json")

    def test_schema_and_validator_define_one_closed_versioned_contract(self) -> None:
        schema = load_json(ROOT / "schemas/consumer-state.schema.json")
        assert isinstance(schema, dict)

        self.assertFalse(schema["additionalProperties"])
        self.assertEqual("1.0.0", schema["properties"]["schema_version"]["const"])
        self.assertEqual(set(schema["required"]), set(self.state))
        self.assertEqual(
            {"consumer_profile", "procedure_reference"}, set(schema["$defs"])
        )
        self.assertFalse(schema["$defs"]["consumer_profile"]["additionalProperties"])
        self.assertFalse(schema["properties"]["effects"]["additionalProperties"])
        self.assertFalse(
            schema["properties"]["effects"]["properties"]["executes"]["const"]
        )
        self.assertFalse(
            schema["properties"]["effects"]["properties"]["mutates"]["const"]
        )
        self.assertEqual([], validate_consumer_state(self.state))

    def test_valid_state_renders_one_deterministic_non_authoritative_card(self) -> None:
        kwargs = {
            "current_time": "2026-01-01T00:30:00Z",
            "expected_environment": "test",
            "expected_revision": "0123456789abcdef0123456789abcdef01234567",
        }

        first = resolve_consumer_state(self.state, self.catalog, **kwargs)
        second = resolve_consumer_state(self.state, self.catalog, **kwargs)

        self.assertIsInstance(first, ConsumerCard)
        self.assertEqual(first, second)
        card = first.to_dict()
        self.assertEqual("GENERAL", card["lane"])
        self.assertEqual("Verify", card["phase"])
        self.assertEqual(
            {
                "phase": 2,
                "phase_total": 2,
                "rail": 6,
                "rail_total": 9,
                "stage": "Execute",
            },
            card["rail_position"],
        )
        self.assertEqual("Evidence needed", card["gate"])
        self.assertTrue(card["rationale"]["summary"])
        self.assertEqual(
            ["focused-test-report", "integration-test-report"],
            card["required_proof"],
        )
        self.assertTrue(card["good"])
        self.assertTrue(card["finished"])
        self.assertTrue(card["anti_example"])
        self.assertFalse(card["authoritative"])
        self.assertEqual(
            {
                "authoritative": False,
                "environment": "test",
                "executes": False,
                "mutates": False,
                "requested_gate": "Evidence needed",
                "revision": "0123456789abcdef0123456789abcdef01234567",
            },
            card["transition_request"],
        )

    def test_red_fixtures_fail_before_resolver_and_return_no_card(self) -> None:
        suite = load_json(FIXTURES / "red-cases.json")
        assert isinstance(suite, dict)
        cases = suite["cases"]
        assert isinstance(cases, list)

        for case in cases:
            assert isinstance(case, dict)
            with self.subTest(case=case["name"]):
                state = materialize_case(self.state, case)
                with patch("aec.consumer.resolve") as resolver:
                    result = resolve_consumer_state(
                        state,
                        self.catalog,
                        current_time=case.get(
                            "current_time", "2026-01-01T00:30:00Z"
                        ),
                        expected_environment=case.get(
                            "expected_environment", "test"
                        ),
                        expected_revision=case.get(
                            "expected_revision",
                            "0123456789abcdef0123456789abcdef01234567",
                        ),
                    )

                self.assertIsInstance(result, ConsumerStateRejection)
                self.assertEqual(case["code"], result.code)
                self.assertFalse(result.to_dict()["accepted"])
                self.assertIsNone(result.to_dict()["card"])
                resolver.assert_not_called()

    def test_adapter_does_not_mutate_state_or_catalog(self) -> None:
        state_before = copy.deepcopy(self.state)
        catalog_before = copy.deepcopy(self.catalog)

        resolve_consumer_state(
            self.state,
            self.catalog,
            current_time="2026-01-01T00:30:00Z",
            expected_environment="test",
            expected_revision="0123456789abcdef0123456789abcdef01234567",
        )

        self.assertEqual(state_before, self.state)
        self.assertEqual(catalog_before, self.catalog)


if __name__ == "__main__":
    unittest.main()
