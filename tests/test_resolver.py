import copy
import json
import unittest
from pathlib import Path

from aec.resolver import canonical_resolution_bytes, resolve
from tools.validate_foundation import validate_resolution


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


class ResolverTracerTests(unittest.TestCase):
    def test_verify_request_resolves_one_complete_deterministic_card(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        request_before = copy.deepcopy(request)
        procedures_before = copy.deepcopy(procedures)

        first = resolve(request, procedures)
        second = resolve(request, procedures)
        first_payload = first.to_dict()

        self.assertEqual(first.canonical_bytes, second.canonical_bytes)
        self.assertEqual(first.resolution_hash, second.resolution_hash)
        self.assertEqual(
            "sha256:ec75bdb1f789a96c113f5166679cd7664177138ea7602cf63236d737794a53e2",
            first.resolution_hash,
        )
        self.assertEqual(request_before, request)
        self.assertEqual(procedures_before, procedures)
        self.assertEqual(canonical_resolution_bytes(first_payload), first.hashed_bytes)
        self.assertEqual([], validate_resolution(first_payload))
        self.assertEqual("Verify", first_payload["phase"])
        self.assertEqual("verify-evidence", first_payload["primary_procedure"])
        self.assertEqual("Evidence needed", first_payload["gate"])
        self.assertEqual(
            {
                "principle_ids": ["ai-engineer-09"],
                "summary": (
                    "Verification evidence is incomplete for the exact revision "
                    "and environment."
                ),
            },
            first_payload["rationale"],
        )
        self.assertEqual(
            ["focused-test-report", "integration-test-report"],
            first_payload["required_evidence"],
        )
        self.assertEqual(
            [
                "Focused and integration evidence bind the exact revision and environment."
            ],
            first_payload["good"],
        )
        self.assertEqual(
            [
                "Every required verification fact is accepted for the exact revision "
                "and environment."
            ],
            first_payload["finished"],
        )
        self.assertEqual(
            "A passing test from another revision is treated as proof.",
            first_payload["anti_example"],
        )
        self.assertEqual(
            {
                "capability_profile": "portable-python",
                "consumer_profile": "example-consumer",
                "policy": "default-delivery",
                "procedure": "verify-evidence",
                "workflow": "ticket-to-pr",
            },
            first_payload["source_identities"],
        )
        self.assertEqual(
            {
                "capability_profile": "portable-python:1.0.0",
                "consumer_profile": "example-consumer:1.0.0",
                "policy": "default-delivery:1.0.0",
                "procedure": "verify-evidence:1.0.0",
                "workflow": "ticket-to-pr:1.0.0",
            },
            first_payload["source_revisions"],
        )
        for source in ("capability_profile", "consumer_profile", "policy"):
            changed = copy.deepcopy(request)
            changed[source]["identity"] = f"other-{source}"
            changed_decision = resolve(changed, procedures)

            self.assertNotEqual(first.resolution_hash, changed_decision.resolution_hash)
        first_payload["gate"] = "Ready"
        self.assertEqual("Evidence needed", first.to_dict()["gate"])


if __name__ == "__main__":
    unittest.main()
