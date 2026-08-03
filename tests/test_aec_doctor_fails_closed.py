"""Fail-closed proof for `python3 -m tools.aec_coach doctor` (AEC issue #109).

`doctor` exists so a consumer can prove one pinned checkout in a single pass
instead of running three disconnected steps. That value depends entirely on
its report being unearned-claim-free: a `PASS` line must mean the named probe
actually resolved. These tests pin both halves of that.

The positive path (`DoctorReportsTheProvenPinTests`) is the ordinary green
check. The red canary is `DoctorRefusesUnearnedPassTests`, which drives
`require_probe_receipts` directly with receipts a rejected or absent probe
would produce. Deleting the guard's missing-probe or non-PASS check reds those
tests while the end-to-end fixture test stays green, because
`validate_connection` raises first on the real path -- which is exactly why
the guard needs its own tests rather than relying on the CLI test to cover it.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

import tools.aec_coach as aec_coach


ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_CONTRACT_FIXTURE = (
    ROOT / "tests" / "fixtures" / "consumer-connection" / "previous-contract.json"
)


def run_doctor(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "tools.aec_coach", "doctor", *args],
        check=False,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )


def passing_receipt() -> dict[str, object]:
    """One receipt shaped exactly like validate_connection's success value."""
    return {
        "probes": [
            {
                "probe": "routine",
                "gate": "Evidence needed",
                "has_decision_support": False,
                "status": "PASS",
            },
            {
                "probe": "material",
                "gate": "Evidence needed",
                "has_decision_support": True,
                "status": "PASS",
            },
        ],
        "status": "PASS",
    }


def descriptor() -> dict[str, object]:
    return aec_coach.load_object(aec_coach.RELEASE_DESCRIPTOR_PATH, "release descriptor")


class DoctorReportsTheProvenPinTests(unittest.TestCase):
    """The single preflight command reports pin, contract, and both probes."""

    def test_doctor_exits_zero_and_reports_four_facts(self) -> None:
        result = run_doctor()
        self.assertEqual(result.returncode, 0, result.stderr)
        for marker in ("PIN", "CONTRACT", "ROUTINE", "MATERIAL"):
            self.assertIn(marker, result.stdout)

    def test_doctor_binds_the_pin_line_to_this_checkout_head(self) -> None:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            cwd=ROOT,
            capture_output=True,
            text=True,
        ).stdout.strip()
        result = run_doctor()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"PIN revision={head}", result.stdout)

    def test_doctor_reports_both_probe_shapes_distinctly(self) -> None:
        result = run_doctor()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ROUTINE PASS", result.stdout)
        self.assertIn("decision_support=absent", result.stdout)
        self.assertIn("MATERIAL PASS", result.stdout)
        self.assertIn("decision_support=present", result.stdout)


class DoctorFailsClosedOnAnIncompatiblePinTests(unittest.TestCase):
    """A pre-`d35f535` decision_context in the MATERIAL slot must stop the report."""

    def test_previous_contract_fixture_exits_nonzero_with_no_pass_on_stdout(self) -> None:
        result = run_doctor("--material", str(PREVIOUS_CONTRACT_FIXTURE))
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("PASS", result.stdout)
        self.assertNotIn("PIN", result.stdout)
        self.assertIn("FAIL", result.stderr)

    def test_the_failure_names_the_fields_a_consumer_must_add(self) -> None:
        result = run_doctor("--material", str(PREVIOUS_CONTRACT_FIXTURE))
        self.assertNotEqual(result.returncode, 0)
        for field in ("context", "schema_version", "confidence", "expected_result"):
            self.assertIn(field, result.stderr)

    def test_an_unreadable_probe_path_fails_closed(self) -> None:
        result = run_doctor("--material", str(ROOT / "tests" / "does-not-exist.json"))
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("PASS", result.stdout)


class DoctorRefusesUnearnedPassTests(unittest.TestCase):
    """Red canary: the guard, not the caller, is what refuses an unearned PASS."""

    def test_a_receipt_missing_the_material_probe_is_refused(self) -> None:
        receipt = passing_receipt()
        receipt["probes"] = [receipt["probes"][0]]
        with self.assertRaises(aec_coach.CoachFailure) as caught:
            aec_coach.require_probe_receipts(receipt)
        self.assertIn("material", str(caught.exception))

    def test_a_receipt_missing_the_routine_probe_is_refused(self) -> None:
        receipt = passing_receipt()
        receipt["probes"] = [receipt["probes"][1]]
        with self.assertRaises(aec_coach.CoachFailure) as caught:
            aec_coach.require_probe_receipts(receipt)
        self.assertIn("routine", str(caught.exception))

    def test_a_probe_reporting_any_status_other_than_pass_is_refused(self) -> None:
        for status in ("SKIPPED", "FAIL", None, "pass"):
            with self.subTest(status=status):
                receipt = passing_receipt()
                receipt["probes"][1]["status"] = status
                with self.assertRaises(aec_coach.CoachFailure) as caught:
                    aec_coach.require_probe_receipts(receipt)
                self.assertIn("did not report PASS", str(caught.exception))

    def test_a_malformed_receipt_is_refused(self) -> None:
        for receipt in ({}, {"probes": "routine"}, {"probes": ["routine"]}):
            with self.subTest(receipt=receipt):
                with self.assertRaises(aec_coach.CoachFailure):
                    aec_coach.require_probe_receipts(receipt)

    def test_doctor_report_raises_before_building_any_line(self) -> None:
        receipt = passing_receipt()
        receipt["probes"][0]["status"] = "SKIPPED"
        with self.assertRaises(aec_coach.CoachFailure):
            aec_coach.doctor_report("0" * 40, descriptor(), receipt)

    def test_doctor_report_renders_every_required_line_when_earned(self) -> None:
        report = aec_coach.doctor_report("0" * 40, descriptor(), passing_receipt())
        lines = report.splitlines()
        self.assertEqual(len(lines), 4)
        self.assertTrue(lines[0].startswith("PIN revision=" + "0" * 40))
        self.assertTrue(lines[1].startswith("CONTRACT release="))
        self.assertTrue(lines[2].startswith("ROUTINE PASS"))
        self.assertTrue(lines[3].startswith("MATERIAL PASS"))


class DoctorContractLineTests(unittest.TestCase):
    """The CONTRACT line comes from the validated release descriptor, not a literal."""

    def test_an_invalid_descriptor_is_refused(self) -> None:
        broken = descriptor()
        del broken["contracts"]
        with self.assertRaises(aec_coach.CoachFailure) as caught:
            aec_coach.contract_line(broken)
        self.assertIn("release descriptor is invalid", str(caught.exception))

    def test_the_contract_line_names_every_declared_contract(self) -> None:
        current = descriptor()
        line = aec_coach.contract_line(current)
        for name, version in current["contracts"].items():
            self.assertIn(f"{name}={version}", line)


if __name__ == "__main__":
    unittest.main()
