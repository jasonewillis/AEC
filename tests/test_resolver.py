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
            "sha256:1fccbcc297b7f3a267001d6dcd1cac38f9f69c44bd3f506a8b0124758964c78e",
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

    def test_unavailable_skill_returns_one_stable_blocked_decision(self) -> None:
        request = load_json(
            ROOT / "tests/fixtures/resolver/red/unavailable-skill.json"
        )
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")

        first = resolve(request, procedures)
        second = resolve(request, procedures)
        payload = first.to_dict()

        self.assertEqual(first.canonical_bytes, second.canonical_bytes)
        self.assertEqual(first.resolution_hash, second.resolution_hash)
        self.assertEqual(
            "sha256:f844ffcdacd144bf0f7ef7c77a2b335c1e4af3c2ff795150f0904cdd50392284",
            first.resolution_hash,
        )
        self.assertEqual([], validate_resolution(payload))
        self.assertEqual("Blocked", payload["gate"])
        self.assertFalse(payload["allowed"])
        self.assertEqual("SKILL_UNAVAILABLE", payload["reason_code"])
        self.assertIsNone(payload["primary_procedure"])
        self.assertEqual(["procedure-availability"], payload["required_evidence"])
        self.assertEqual(
            {
                "identity": "verify-evidence",
                "revision": "verify-evidence:1.0.0",
            },
            payload["required_procedure"],
        )
        self.assertEqual(
            "verify-evidence",
            payload["source_identities"]["procedure"],
        )

    def test_unavailable_required_skill_does_not_select_same_phase_substitute(
        self,
    ) -> None:
        request = load_json(
            ROOT / "tests/fixtures/resolver/red/unavailable-skill.json"
        )
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        substitute = copy.deepcopy(procedures["procedures"][0])
        substitute["identity"] = "silent-substitute"
        substitute["revision"] = "silent-substitute:1.0.0"
        procedures["procedures"].append(substitute)
        request["available_procedures"] = [
            {
                "identity": "silent-substitute",
                "revision": "silent-substitute:1.0.0",
            }
        ]

        payload = resolve(request, procedures).to_dict()

        self.assertEqual([], validate_resolution(payload))
        self.assertEqual("Blocked", payload["gate"])
        self.assertFalse(payload["allowed"])
        self.assertEqual("SKILL_UNAVAILABLE", payload["reason_code"])
        self.assertIsNone(payload["primary_procedure"])
        self.assertEqual(
            {
                "identity": "verify-evidence",
                "revision": "verify-evidence:1.0.0",
            },
            payload["required_procedure"],
        )
        self.assertEqual(["procedure-availability"], payload["required_evidence"])

    def test_availability_facts_are_bound_into_blocked_decision_hash(self) -> None:
        request = load_json(
            ROOT / "tests/fixtures/resolver/red/unavailable-skill.json"
        )
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        changed = copy.deepcopy(request)
        changed["available_procedures"] = [
            {
                "identity": "unrelated-procedure",
                "revision": "unrelated-procedure:1.0.0",
            }
        ]

        empty_availability = resolve(request, procedures).to_dict()
        unrelated_availability = resolve(changed, procedures).to_dict()

        self.assertEqual([], validate_resolution(empty_availability))
        self.assertEqual([], validate_resolution(unrelated_availability))
        self.assertNotEqual(
            empty_availability["resolution_hash"],
            unrelated_availability["resolution_hash"],
        )
        self.assertEqual([], empty_availability["available_procedures"])
        self.assertEqual(
            changed["available_procedures"],
            unrelated_availability["available_procedures"],
        )


if __name__ == "__main__":
    unittest.main()
