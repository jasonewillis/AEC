import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

from aec.consumer import ConsumerCard, resolve_consumer_state
from aec.outcomes import (
    OutcomeReceiptRejection,
    OutcomeReceiptVerification,
    evaluate_outcomes,
    verify_outcome_receipt,
)


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

    def test_routine_work_cannot_carry_an_outcome_receipt(self) -> None:
        routine = copy.deepcopy(self.card)
        routine["decision_support"] = None

        result = verify_outcome_receipt(self.receipt, routine)

        self.assertIsInstance(result, OutcomeReceiptRejection)
        assert isinstance(result, OutcomeReceiptRejection)
        self.assertEqual("OUTCOME_RECEIPT_NO_DECISION", result.code)

    def test_stale_or_mismatched_decision_binding_fails_closed(self) -> None:
        wrong_hash = copy.deepcopy(self.receipt)
        wrong_hash["decision"]["resolution_hash"] = f"sha256:{'0' * 64}"
        self.reject(wrong_hash, "OUTCOME_RECEIPT_DECISION_MISMATCH")

        wrong_revision = copy.deepcopy(self.receipt)
        wrong_revision["decision"]["revision"] = "f" * 40
        self.reject(wrong_revision, "OUTCOME_RECEIPT_DECISION_MISMATCH")

    def test_undeclared_choice_fails_closed(self) -> None:
        undeclared = copy.deepcopy(self.receipt)
        undeclared["decision"]["selected_choice"] = "rewrite-everything"
        self.reject(undeclared, "OUTCOME_RECEIPT_CHOICE_UNDECLARED")

    def test_result_that_does_not_match_the_expected_result_fails_closed(self) -> None:
        other_measure = copy.deepcopy(self.receipt)
        other_measure["observed_result"]["measure"] = "some-other-measure"
        self.reject(other_measure, "OUTCOME_RECEIPT_RESULT_MISMATCH")

        wrong_direction = copy.deepcopy(self.receipt)
        wrong_direction["observed_result"]["direction"] = "increase"
        self.reject(wrong_direction, "OUTCOME_RECEIPT_RESULT_MISMATCH")

    def test_lying_outcome_summary_fails_closed(self) -> None:
        for expectation, verdict in (
            ("missed", "unsupported"),
            ("partially-met", "partially-supported"),
            ("reversed", "harmful"),
            ("unobserved", "inconclusive"),
        ):
            with self.subTest(expectation=expectation):
                lying = copy.deepcopy(self.receipt)
                lying["observed_result"]["expectation"] = expectation
                if expectation == "reversed":
                    lying["observed_result"]["direction"] = "increase"
                self.reject(lying, "OUTCOME_RECEIPT_VERDICT_CONTRADICTED")

                honest = copy.deepcopy(lying)
                honest["verdict"] = verdict
                result = verify_outcome_receipt(honest, self.card)
                self.assertIsInstance(result, OutcomeReceiptVerification)
                assert isinstance(result, OutcomeReceiptVerification)
                self.assertEqual(verdict, result.verdict)

    def test_unverified_or_stale_verification_forces_inconclusive(self) -> None:
        unverified = copy.deepcopy(self.receipt)
        for fact in unverified["verification"]:
            fact["accepted"] = False
        self.reject(unverified, "OUTCOME_RECEIPT_VERDICT_CONTRADICTED")

        stale = copy.deepcopy(self.receipt)
        for fact in stale["verification"]:
            fact["revision"] = "f" * 40
        self.reject(stale, "OUTCOME_RECEIPT_VERDICT_CONTRADICTED")

        honest = copy.deepcopy(stale)
        honest["verdict"] = "inconclusive"
        result = verify_outcome_receipt(honest, self.card)
        self.assertIsInstance(result, OutcomeReceiptVerification)

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
        records[0]["receipt"]["observed_result"]["expectation"] = "missed"

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
