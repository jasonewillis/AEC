import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from aec.mentor import (
    PrivateMentorLensError,
    apply_private_mentor_lens,
    load_private_mentor_lens,
)
from aec.resolver import ResolutionDecision, ResolutionRejection, resolve


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def intake_decision():
    request = load_json(ROOT / "tests/fixtures/resolver/golden/intake.json")
    catalog = load_json(ROOT / "config/procedures/ticket-to-pr.json")
    decision = resolve(request, catalog)
    if isinstance(decision, ResolutionRejection):
        raise AssertionError(decision.to_dict())
    return decision


class PrivateMentorLensTests(unittest.TestCase):
    def test_private_local_directory_is_ignored(self) -> None:
        patterns = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

        self.assertIn(".local/", patterns)

    def test_private_course_source_directory_is_ignored(self) -> None:
        patterns = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()

        self.assertIn("docs/AI Engineer Course/", patterns)

    def test_schema_and_validator_share_one_closed_card_contract(self) -> None:
        schema = load_json(ROOT / "schemas/private-mentor-lens.schema.json")

        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            {"cards", "identity", "revision", "schema_version"},
            set(schema["required"]),
        )
        card = schema["properties"]["cards"]["items"]
        self.assertFalse(card["additionalProperties"])
        self.assertEqual(
            {
                "guidance",
                "id",
                "phase",
                "principle_ids",
                "questions",
                "source_ids",
            },
            set(card["required"]),
        )

    def test_valid_lens_adds_context_without_changing_authoritative_decision(self) -> None:
        decision = intake_decision()
        lens = load_private_mentor_lens(
            ROOT / "tests/fixtures/private-mentor-lens/valid.json"
        )

        first = apply_private_mentor_lens(decision, lens).to_dict()
        second = apply_private_mentor_lens(decision, lens).to_dict()

        self.assertEqual(first, second)
        self.assertEqual(decision.to_dict(), first["authoritative_decision"])
        self.assertEqual(
            decision.resolution_hash,
            first["authoritative_resolution_hash"],
        )
        self.assertFalse(first["executes"])
        self.assertFalse(first["mutates"])
        self.assertEqual(
            ["synthetic-intake-card"],
            [item["id"] for item in first["supplemental_context"]["cards"]],
        )

    def test_conflicting_embedded_decision_hash_is_rejected(self) -> None:
        decision = intake_decision()
        payload = decision.to_dict()
        payload["resolution_hash"] = f"sha256:{'0' * 64}"
        forged = ResolutionDecision(
            canonical_bytes=json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8"),
            hashed_bytes=decision.hashed_bytes,
            resolution_hash=decision.resolution_hash,
        )

        with self.assertRaisesRegex(
            PrivateMentorLensError,
            "embedded authoritative decision hash does not match",
        ):
            apply_private_mentor_lens(forged, None)

    def test_missing_lens_degrades_to_the_normal_decision(self) -> None:
        decision = intake_decision()

        absent = load_private_mentor_lens(ROOT / "missing-private-lens.json")
        envelope = apply_private_mentor_lens(decision, absent).to_dict()

        self.assertEqual(decision.to_dict(), envelope["authoritative_decision"])
        self.assertEqual(decision.resolution_hash, envelope["authoritative_resolution_hash"])
        self.assertIsNone(envelope["supplemental_context"])

    def test_malformed_duplicate_and_mismatched_lenses_are_rejected(self) -> None:
        valid = load_json(ROOT / "tests/fixtures/private-mentor-lens/valid.json")
        cases = []

        malformed = copy.deepcopy(valid)
        malformed["cards"][0]["guidance"] = "not-a-list"
        cases.append(malformed)

        duplicate = copy.deepcopy(valid)
        duplicate["cards"].append(copy.deepcopy(duplicate["cards"][0]))
        cases.append(duplicate)

        mismatched = copy.deepcopy(valid)
        mismatched["cards"][0]["principle_ids"] = ["aec-ticket-to-pr-build"]
        cases.append(mismatched)

        for payload in cases:
            with self.subTest(payload=payload):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    path = Path(temporary_directory) / "lens.json"
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    with self.assertRaises(PrivateMentorLensError):
                        lens = load_private_mentor_lens(path)
                        apply_private_mentor_lens(intake_decision(), lens)

    def test_duplicate_json_keys_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "lens.json"
            path.write_text(
                '{"schema_version":"1.0.0","identity":"one",'
                '"identity":"two","revision":"one:1.0.0","cards":[]}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(PrivateMentorLensError, "duplicate JSON key"):
                load_private_mentor_lens(path)

    def test_existing_non_file_lens_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaisesRegex(PrivateMentorLensError, "must be a file"):
                load_private_mentor_lens(Path(temporary_directory))

    def test_proof_tool_emits_metadata_without_private_guidance(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/prove_private_mentor_lens.py"),
                "--request",
                str(ROOT / "tests/fixtures/resolver/golden/intake.json"),
                "--lens",
                str(ROOT / "tests/fixtures/private-mentor-lens/valid.json"),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        proof = json.loads(result.stdout)
        self.assertTrue(proof["decision_unchanged"])
        self.assertEqual(["synthetic-intake-card"], proof["selected_card_ids"])
        self.assertNotIn("Use one synthetic observable outcome", result.stdout)

    def test_proof_tool_rejects_an_explicit_missing_lens(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools/prove_private_mentor_lens.py"),
                "--request",
                str(ROOT / "tests/fixtures/resolver/golden/intake.json"),
                "--lens",
                str(ROOT / "missing-private-lens.json"),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(0, result.returncode)
        self.assertEqual("FAIL", json.loads(result.stdout)["status"])


if __name__ == "__main__":
    unittest.main()
