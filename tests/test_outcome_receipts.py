import copy
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

from aec.cards import compute_card_hash, project_card, validate_public_card
from aec.consumer import ConsumerCard, resolve_consumer_state
from aec.contracts import CANONICAL_INTEGER
from aec.outcomes import (
    VERDICTS,
    OutcomeReceiptRejection,
    OutcomeReceiptVerification,
    evaluate_outcomes,
    verify_outcome_receipt,
    verify_outcome_record,
)
from aec.resolver import compute_resolution_hash


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "outcomes"


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def rendered_card() -> dict[str, object]:
    """Render the golden proposal card through the public consumer adapter."""
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


class OutcomeReceiptContractTests(unittest.TestCase):
    def setUp(self) -> None:
        records = load_json(FIXTURES / "golden.json")
        assert isinstance(records, dict)
        self.records = records
        record = records["records"][0]
        self.card = record["card"]
        self.receipt = record["receipt"]

    def reject(self, receipt: object, code: str) -> None:
        result = verify_outcome_receipt(receipt, self.card)
        self.assertIsInstance(result, OutcomeReceiptRejection)
        assert isinstance(result, OutcomeReceiptRejection)
        self.assertEqual(code, result.code)
        self.assertTrue(result.errors)

    def reject_card(self, card: object) -> None:
        result = verify_outcome_receipt(self.receipt, card)
        self.assertIsInstance(result, OutcomeReceiptRejection)
        assert isinstance(result, OutcomeReceiptRejection)
        self.assertEqual("OUTCOME_RECEIPT_CARD_INVALID", result.code)

    def observed(self, value: object) -> dict[str, Any]:
        receipt = copy.deepcopy(self.receipt)
        receipt["observed_result"]["value"] = value
        return receipt

    def expectation(self, name: str, value: object) -> dict[str, Any]:
        card = copy.deepcopy(self.card)
        card["decision_support"]["recommendation"]["expected_result"][name] = value
        card["card_hash"] = compute_card_hash(card)
        return card

    def test_golden_example_binds_proposal_card_and_observed_result(self) -> None:
        self.assertEqual(rendered_card(), self.card)

        result = verify_outcome_receipt(self.receipt, self.card)

        self.assertIsInstance(result, OutcomeReceiptVerification)
        assert isinstance(result, OutcomeReceiptVerification)
        self.assertEqual("supported", result.verdict)
        self.assertEqual(self.card["resolution_hash"], result.resolution_hash)
        self.assertEqual("isolate-import-boundary", result.selected_choice)
        self.assertEqual(
            result.canonical_bytes,
            verify_outcome_receipt(
                copy.deepcopy(self.receipt), copy.deepcopy(self.card)
            ).canonical_bytes,
        )

    def test_schema_validator_and_golden_receipt_agree(self) -> None:
        schema = load_json(ROOT / "schemas/outcome-receipt.schema.json")
        assert isinstance(schema, dict)

        self.assertFalse(schema["additionalProperties"])
        self.assertEqual("1.0.0", schema["properties"]["schema_version"]["const"])
        self.assertEqual(set(schema["required"]), set(self.receipt))
        self.assertEqual(
            [
                "supported",
                "partially-supported",
                "unsupported",
                "harmful",
                "inconclusive",
            ],
            schema["properties"]["verdict"]["enum"],
        )
        observed = schema["properties"]["observed_result"]
        self.assertEqual({"measure", "unit", "value"}, set(observed["required"]))
        self.assertEqual(
            {"$ref": "#/$defs/canonical_integer"}, observed["properties"]["value"]
        )

    def test_routine_work_cannot_carry_an_outcome_receipt(self) -> None:
        routine = copy.deepcopy(self.card)
        routine["decision_support"] = None
        routine["card_hash"] = compute_card_hash(routine)

        result = verify_outcome_receipt(self.receipt, routine)

        self.assertIsInstance(result, OutcomeReceiptRejection)
        assert isinstance(result, OutcomeReceiptRejection)
        self.assertEqual("OUTCOME_RECEIPT_NO_DECISION", result.code)

    def test_broken_cards_fail_before_any_outcome_fact_is_read(self) -> None:
        for value in (None, [], "card"):
            with self.subTest(card=value):
                self.reject_card(value)

        missing = copy.deepcopy(self.card)
        del missing["gate"]
        self.reject_card(missing)

        malformed = copy.deepcopy(self.card)
        malformed["gate"] = "green"
        malformed["card_hash"] = compute_card_hash(malformed)
        self.reject_card(malformed)

        inconsistent = copy.deepcopy(self.card)
        inconsistent["transition_request"]["requested_gate"] = "Ready"
        inconsistent["card_hash"] = compute_card_hash(inconsistent)
        self.reject_card(inconsistent)

        tampered = copy.deepcopy(self.card)
        tampered["decision_support"]["recommendation"]["choice"] = "install-everywhere"
        self.reject_card(tampered)

    def test_inconsistent_expected_result_on_the_card_fails_closed(self) -> None:
        for name, value in (
            ("target", "4"),
            ("target", "9"),
            ("direction", "increase"),
            ("direction", "hold"),
            ("baseline", 4),
            ("baseline", 4.0),
            ("baseline", True),
            ("target", "0.0"),
            ("unit", "Failures Per Run"),
        ):
            with self.subTest(field=name, value=value):
                self.reject_card(self.expectation(name, value))

    def test_stale_or_mismatched_decision_binding_fails_closed(self) -> None:
        wrong_hash = copy.deepcopy(self.receipt)
        wrong_hash["decision"]["resolution_hash"] = f"sha256:{'0' * 64}"
        self.reject(wrong_hash, "OUTCOME_RECEIPT_DECISION_MISMATCH")

        wrong_revision = copy.deepcopy(self.receipt)
        wrong_revision["decision"]["revision"] = "f" * 40
        self.reject(wrong_revision, "OUTCOME_RECEIPT_DECISION_MISMATCH")

    def test_only_the_recommended_choice_can_be_reported(self) -> None:
        undeclared = copy.deepcopy(self.receipt)
        undeclared["decision"]["selected_choice"] = "rewrite-everything"
        self.reject(undeclared, "OUTCOME_RECEIPT_CHOICE_UNDECLARED")

        declared = copy.deepcopy(self.receipt)
        declared["decision"]["selected_choice"] = "install-everywhere"
        self.reject(declared, "OUTCOME_RECEIPT_CHOICE_NOT_RECOMMENDED")

    def test_result_that_does_not_answer_the_expected_result_fails_closed(self) -> None:
        other_measure = copy.deepcopy(self.receipt)
        other_measure["observed_result"]["measure"] = "some-other-measure"
        self.reject(other_measure, "OUTCOME_RECEIPT_RESULT_MISMATCH")

        other_unit = copy.deepcopy(self.receipt)
        other_unit["observed_result"]["unit"] = "seconds"
        self.reject(other_unit, "OUTCOME_RECEIPT_RESULT_MISMATCH")

    def test_the_observed_revision_may_differ_from_the_decision_revision(self) -> None:
        self.assertNotEqual(
            self.receipt["decision"]["revision"],
            self.receipt["observed_revision"],
        )

        result = verify_outcome_receipt(self.receipt, self.card)

        self.assertIsInstance(result, OutcomeReceiptVerification)
        assert isinstance(result, OutcomeReceiptVerification)
        self.assertEqual(self.receipt["observed_revision"], result.observed_revision)
        self.assertEqual(self.card["transition_request"]["revision"], result.revision)

    def test_mixed_or_stale_accepted_verification_fails_closed(self) -> None:
        decision_revision = self.receipt["decision"]["revision"]

        mixed = copy.deepcopy(self.receipt)
        mixed["verification"][0]["revision"] = "f" * 40
        self.reject(mixed, "OUTCOME_RECEIPT_VERIFICATION_STALE")

        stale = copy.deepcopy(self.receipt)
        for fact in stale["verification"]:
            fact["revision"] = decision_revision
        self.reject(stale, "OUTCOME_RECEIPT_VERIFICATION_STALE")

        ignored = copy.deepcopy(self.receipt)
        ignored["verification"].append(
            {"accepted": False, "kind": "smoke-report", "revision": decision_revision}
        )
        self.assertIsInstance(
            verify_outcome_receipt(ignored, self.card), OutcomeReceiptVerification
        )

    def test_the_declared_verdict_must_equal_the_derived_verdict(self) -> None:
        for value, verdict in (("0", "supported"), ("-2", "supported"),
                               ("1", "partially-supported"), ("3", "partially-supported"),
                               ("4", "unsupported"), ("5", "harmful")):
            with self.subTest(value=value):
                honest = self.observed(value)
                honest["verdict"] = verdict
                result = verify_outcome_receipt(honest, self.card)
                self.assertIsInstance(result, OutcomeReceiptVerification)
                assert isinstance(result, OutcomeReceiptVerification)
                self.assertEqual(verdict, result.verdict)

                for lie in sorted(set(VERDICTS) - {verdict}):
                    lying = copy.deepcopy(honest)
                    lying["verdict"] = lie
                    self.reject(lying, "OUTCOME_RECEIPT_VERDICT_CONTRADICTED")

    def test_increase_is_the_exact_inverse_and_hold_admits_one_value(self) -> None:
        cases = (
            ("increase", "4", "9", (("9", "supported"), ("11", "supported"),
                                    ("5", "partially-supported"), ("4", "unsupported"),
                                    ("3", "harmful"))),
            ("hold", "4", "4", (("4", "supported"), ("3", "harmful"), ("5", "harmful"))),
        )
        for direction, baseline, target, outcomes in cases:
            card = copy.deepcopy(self.card)
            card["decision_support"]["recommendation"]["expected_result"].update(
                {"baseline": baseline, "direction": direction, "target": target}
            )
            card["card_hash"] = compute_card_hash(card)
            self.assertEqual([], validate_public_card(card))

            for value, verdict in outcomes:
                with self.subTest(direction=direction, value=value):
                    receipt = self.observed(value)
                    receipt["verdict"] = verdict
                    result = verify_outcome_receipt(receipt, card)
                    self.assertIsInstance(result, OutcomeReceiptVerification)
                    assert isinstance(result, OutcomeReceiptVerification)
                    self.assertEqual(verdict, result.verdict)

    def test_no_accepted_proof_derives_an_inconclusive_verdict(self) -> None:
        unverified = copy.deepcopy(self.receipt)
        for fact in unverified["verification"]:
            fact["accepted"] = False
        self.reject(unverified, "OUTCOME_RECEIPT_VERDICT_CONTRADICTED")

        honest = copy.deepcopy(unverified)
        honest["verdict"] = "inconclusive"
        result = verify_outcome_receipt(honest, self.card)
        self.assertIsInstance(result, OutcomeReceiptVerification)
        assert isinstance(result, OutcomeReceiptVerification)
        self.assertEqual("inconclusive", result.verdict)

    def test_unknown_and_prohibited_fields_fail_closed(self) -> None:
        cases = load_json(FIXTURES / "red-cases.json")
        assert isinstance(cases, dict)

        for case in cases["cases"]:
            with self.subTest(case=case["name"]):
                receipt = copy.deepcopy(self.receipt)
                target = receipt
                for part in case["path"][:-1]:
                    target = target[part]
                if case["operation"] == "remove":
                    del target[case["path"][-1]]
                else:
                    target[case["path"][-1]] = case["value"]
                self.reject(receipt, case["code"])

    def test_private_paths_and_non_json_values_fail_closed(self) -> None:
        for value in ("/Users/example/notes.md", "~/secrets", "C:\\keys", "./diff"):
            with self.subTest(value=value):
                leaking = copy.deepcopy(self.receipt)
                leaking["decision"]["selected_choice"] = value
                self.reject(leaking, "OUTCOME_RECEIPT_PRIVATE_PATH")

        self.reject({"receipt": object()}, "OUTCOME_RECEIPT_INVALID")
        self.reject([], "OUTCOME_RECEIPT_INVALID")

    def test_receipt_carries_no_free_text(self) -> None:
        result = verify_outcome_receipt(self.receipt, self.card)
        assert isinstance(result, OutcomeReceiptVerification)

        for value in json.loads(json.dumps(self.receipt)).values():
            for text in _strings(value):
                self.assertNotIn(" ", text)


class CanonicalIntegerEncodingTests(unittest.TestCase):
    """Prove the schema pattern and the Python validator accept the same values."""

    REJECTED = (
        "1.0",
        1.0,
        1,
        0,
        True,
        False,
        "+1",
        "01",
        "-0",
        "-01",
        " 1",
        "1 ",
        "\n1",
        "1\n",
        "1e3",
        "1E3",
        "",
        "-",
        "0x1",
        "one",
        None,
    )
    ACCEPTED = ("0", "1", "7", "-7", "12345", "-12345")

    def setUp(self) -> None:
        records = load_json(FIXTURES / "golden.json")
        assert isinstance(records, dict)
        record = records["records"][0]
        self.card = record["card"]
        self.receipt = record["receipt"]

    def schema_pattern(self, path: Path, *names: str) -> str:
        """Return the canonical-integer pattern one schema binds to a field."""
        schema = load_json(path)
        assert isinstance(schema, dict)
        node: Any = schema
        for name in names:
            node = node[name]
        if "$ref" in node:
            node = schema["$defs"][node["$ref"].rsplit("/", 1)[-1]]
        self.assertEqual("string", node["type"])
        return str(node["pattern"])

    def test_every_schema_binds_the_same_canonical_integer_pattern(self) -> None:
        patterns = {
            self.schema_pattern(
                ROOT / "schemas/outcome-receipt.schema.json",
                "properties",
                "observed_result",
                "properties",
                "value",
            ),
            self.schema_pattern(
                ROOT / "schemas/consumer-state.schema.json",
                "$defs",
                "decision_context",
                "properties",
                "recommendation",
                "properties",
                "expected_result",
                "properties",
                "baseline",
            ),
            self.schema_pattern(
                ROOT / "schemas/resolution-request.schema.json",
                "$defs",
                "decision_context",
                "properties",
                "recommendation",
                "properties",
                "expected_result",
                "properties",
                "target",
            ),
        }

        self.assertEqual(1, len(patterns))

    def test_the_schema_pattern_and_the_python_regex_agree_exactly(self) -> None:
        pattern = re.compile(
            self.schema_pattern(
                ROOT / "schemas/outcome-receipt.schema.json",
                "properties",
                "observed_result",
                "properties",
                "value",
            )
        )

        for value in self.REJECTED:
            with self.subTest(rejected=value):
                self.assertIsNone(
                    CANONICAL_INTEGER.fullmatch(value)
                    if type(value) is str
                    else None
                )
                if type(value) is str:
                    self.assertIsNone(pattern.search(value))
        for value in self.ACCEPTED:
            with self.subTest(accepted=value):
                self.assertIsNotNone(CANONICAL_INTEGER.fullmatch(value))
                self.assertIsNotNone(pattern.search(value))

    def test_only_canonical_metric_values_are_accepted(self) -> None:
        for value in self.REJECTED:
            with self.subTest(rejected=value):
                receipt = copy.deepcopy(self.receipt)
                receipt["observed_result"]["value"] = value
                result = verify_outcome_receipt(receipt, self.card)
                self.assertIsInstance(result, OutcomeReceiptRejection)
                assert isinstance(result, OutcomeReceiptRejection)
                self.assertEqual("OUTCOME_RECEIPT_INVALID", result.code)

        # baseline "4" and target "0" decreasing: 0 and every negative value support it.
        for value, verdict in (("0", "supported"), ("-7", "supported"),
                               ("2", "partially-supported"), ("4", "unsupported"),
                               ("12345", "harmful")):
            with self.subTest(accepted=value):
                receipt = copy.deepcopy(self.receipt)
                receipt["observed_result"]["value"] = value
                receipt["verdict"] = verdict
                result = verify_outcome_receipt(receipt, self.card)
                self.assertIsInstance(result, OutcomeReceiptVerification)
                assert isinstance(result, OutcomeReceiptVerification)
                self.assertEqual(verdict, result.verdict)

    def test_only_canonical_expected_result_numbers_are_accepted(self) -> None:
        expected = self.card["decision_support"]["recommendation"]["expected_result"]
        self.assertEqual("4", expected["baseline"])
        self.assertEqual("0", expected["target"])

        for name in ("baseline", "target"):
            for value in self.REJECTED:
                with self.subTest(field=name, rejected=value):
                    card = copy.deepcopy(self.card)
                    card["decision_support"]["recommendation"]["expected_result"][
                        name
                    ] = value
                    card["card_hash"] = compute_card_hash(card)
                    self.assertTrue(validate_public_card(card))


class OutcomeRecordAuthenticationTests(unittest.TestCase):
    """Prove one record authenticates its card as a projection of its decision."""

    def setUp(self) -> None:
        records = load_json(FIXTURES / "golden.json")
        assert isinstance(records, dict)
        self.record = records["records"][0]
        self.decision = self.record["decision"]

    def reject(self, record: object, code: str) -> None:
        result = verify_outcome_record(record)
        self.assertIsInstance(result, OutcomeReceiptRejection)
        assert isinstance(result, OutcomeReceiptRejection)
        self.assertEqual(code, result.code)

    def forge(self, **changes: Any) -> dict[str, Any]:
        """Rebuild one internally consistent record around a changed decision."""
        decision = copy.deepcopy(self.decision)
        decision.update(changes)
        decision["resolution_hash"] = compute_resolution_hash(decision)
        receipt = copy.deepcopy(self.record["receipt"])
        receipt["decision"]["resolution_hash"] = decision["resolution_hash"]
        receipt["decision"]["revision"] = decision["revision"]
        return {
            "card": project_card(decision),
            "decision": decision,
            "receipt": receipt,
        }

    def test_the_record_carries_the_decision_that_produced_the_card(self) -> None:
        self.assertEqual({"card", "decision", "receipt"}, set(self.record))
        self.assertEqual(
            self.decision["resolution_hash"],
            compute_resolution_hash(self.decision),
        )
        self.assertEqual(self.record["card"], project_card(self.decision))

        result = verify_outcome_record(self.record)

        self.assertIsInstance(result, OutcomeReceiptVerification)
        assert isinstance(result, OutcomeReceiptVerification)
        self.assertEqual("supported", result.verdict)

    def test_a_recomputed_self_consistent_forgery_still_fails_closed(self) -> None:
        forged = self.forge(gate="Ready")

        # The forgery is internally consistent: its own hash and card both agree.
        self.assertEqual(
            forged["decision"]["resolution_hash"],
            compute_resolution_hash(forged["decision"]),
        )
        self.assertEqual(forged["card"], project_card(forged["decision"]))
        self.assertEqual(
            forged["card"]["card_hash"], compute_card_hash(forged["card"])
        )
        self.assertNotEqual(
            self.record["card"]["card_hash"], forged["card"]["card_hash"]
        )

        self.reject(forged, "OUTCOME_RECORD_DECISION_INVALID")

    def test_a_decision_that_does_not_produce_the_card_fails_closed(self) -> None:
        edited = copy.deepcopy(self.record)
        edited["card"]["good"] = ["A Good the decision never stated."]
        edited["card"]["card_hash"] = compute_card_hash(edited["card"])
        self.assertEqual([], validate_public_card(edited["card"]))
        self.reject(edited, "OUTCOME_RECORD_CARD_NOT_PROJECTED")

        prose = copy.deepcopy(self.record)
        prose["decision"]["rationale"]["summary"] = "A summary nobody resolved."
        prose["decision"]["resolution_hash"] = compute_resolution_hash(
            prose["decision"]
        )
        prose["receipt"]["decision"]["resolution_hash"] = prose["decision"][
            "resolution_hash"
        ]
        self.reject(prose, "OUTCOME_RECORD_CARD_NOT_PROJECTED")

    def test_a_decision_hash_that_is_not_recomputed_fails_closed(self) -> None:
        stale = copy.deepcopy(self.record)
        stale["decision"]["resolution_hash"] = f"sha256:{'0' * 64}"
        self.reject(stale, "OUTCOME_RECORD_DECISION_INVALID")

    def test_malformed_records_and_decisions_fail_closed(self) -> None:
        for record in ({}, [], None, {"card": {}, "receipt": {}}):
            with self.subTest(record=record):
                self.reject(record, "OUTCOME_RECORD_INVALID")

        for decision in (None, [], "decision", {}, {"schema_version": "4.0.0"}):
            with self.subTest(decision=decision):
                broken = copy.deepcopy(self.record)
                broken["decision"] = decision
                self.reject(broken, "OUTCOME_RECORD_DECISION_INVALID")

    def test_the_evaluator_never_echoes_decision_content(self) -> None:
        report = evaluate_outcomes([self.record, self.forge(gate="Ready")])

        self.assertEqual(1, report["verified"])
        self.assertEqual(
            [{"code": "OUTCOME_RECORD_DECISION_INVALID", "index": 1}],
            report["rejected"],
        )
        rendered = json.dumps(report, sort_keys=True)
        content = [text for text in _strings(self.decision) if " " in text]
        content += [
            self.decision["resolution_hash"],
            self.decision["revision"],
            self.decision["task_id"],
        ]
        self.assertTrue(content)
        for text in content:
            self.assertNotIn(text, rendered)


class OutcomeEvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        records = load_json(FIXTURES / "golden.json")
        assert isinstance(records, dict)
        self.records = records["records"]

    def test_evaluator_reports_coaching_value_and_project_impact(self) -> None:
        report = evaluate_outcomes(self.records)

        self.assertEqual(evaluate_outcomes(copy.deepcopy(self.records)), report)
        self.assertEqual("1.0.0", report["schema_version"])
        self.assertFalse(report["authoritative"])
        self.assertFalse(report["causal_claim"])
        self.assertEqual(len(self.records), report["verified"])
        self.assertEqual([], report["rejected"])
        self.assertEqual(
            {"high": 0, "low": 0, "moderate": 0},
            {key: 0 for key in report["coaching_value"]["burden"]},
        )
        self.assertEqual(
            {"full": 0, "none": 0, "partial": 0},
            {key: 0 for key in report["coaching_value"]["transfer"]},
        )
        self.assertEqual(
            {
                "harmful",
                "inconclusive",
                "partially-supported",
                "supported",
                "unsupported",
            },
            set(report["project_impact"]["verdict"]),
        )
        self.assertEqual(
            len(self.records),
            sum(report["project_impact"]["verdict"].values()),
        )

    def test_evaluator_reports_rejected_records_without_counting_them(self) -> None:
        records = copy.deepcopy(self.records)
        records[0]["receipt"]["verdict"] = "supported"
        records[0]["receipt"]["observed_result"]["value"] = "9"

        report = evaluate_outcomes(records)

        self.assertEqual(0, report["verified"])
        self.assertEqual(
            [{"code": "OUTCOME_RECEIPT_VERDICT_CONTRADICTED", "index": 0}],
            report["rejected"],
        )
        self.assertEqual(0, sum(report["project_impact"]["verdict"].values()))

    def test_evaluator_rejects_malformed_record_collections(self) -> None:
        for records in ({}, [{"card": {}}], [{"card": {}, "receipt": {}, "x": 1}]):
            with self.subTest(records=records):
                self.assertRaises(ValueError, evaluate_outcomes, records)

    def test_cli_prints_a_canonical_report_and_fails_closed(self) -> None:
        completed = subprocess.run(
            [sys.executable, "tools/evaluate_outcomes.py", str(FIXTURES / "golden.json")],
            capture_output=True,
            check=False,
            cwd=ROOT,
            text=True,
        )

        self.assertEqual(0, completed.returncode, completed.stderr)
        report = json.loads(completed.stdout)
        self.assertEqual(1, report["verified"])
        self.assertNotIn(str(FIXTURES), completed.stdout)

        missing = subprocess.run(
            [sys.executable, "tools/evaluate_outcomes.py", "tests/fixtures/nope.json"],
            capture_output=True,
            check=False,
            cwd=ROOT,
            text=True,
        )
        self.assertEqual(1, missing.returncode)
        self.assertEqual("", missing.stdout)


def _strings(value: object) -> list[str]:
    """Return every nested string in one JSON value."""
    if isinstance(value, dict):
        return [item for nested in value.values() for item in _strings(nested)]
    if isinstance(value, list):
        return [item for nested in value for item in _strings(nested)]
    return [value] if isinstance(value, str) else []


if __name__ == "__main__":
    unittest.main()
