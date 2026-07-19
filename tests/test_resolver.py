import copy
import json
import unittest
from pathlib import Path

from aec.resolver import (
    ResolutionRejection,
    canonical_resolution_bytes,
    compute_resolution_hash,
    resolve,
)
from tools.validate_foundation import validate_resolution


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


class ResolverTracerTests(unittest.TestCase):
    def test_malformed_available_procedure_returns_structured_rejection(self) -> None:
        request = load_json(
            ROOT
            / "tests/fixtures/resolver/red/malformed-available-procedure.json"
        )
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")

        result = resolve(request, procedures)

        self.assertIsInstance(result, ResolutionRejection)
        self.assertEqual(
            {
                "accepted": False,
                "code": "RESOLUTION_REQUEST_INVALID",
                "errors": [
                    "available_procedures[0] must contain exactly identity and revision"
                ],
            },
            result.to_dict(),
        )

    def test_unknown_request_field_fails_closed(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        request["consumer_only_hint"] = "ignore me"

        result = resolve(request, procedures)

        self.assertIsInstance(result, ResolutionRejection)
        self.assertEqual(
            {
                "accepted": False,
                "code": "RESOLUTION_REQUEST_INVALID",
                "errors": ["unknown request fields: consumer_only_hint"],
            },
            result.to_dict(),
        )

    def test_missing_request_field_returns_deterministic_rejection(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        del request["phase"]

        first = resolve(request, procedures)
        second = resolve(request, procedures)

        self.assertIsInstance(first, ResolutionRejection)
        self.assertEqual(first, second)
        self.assertEqual(
            {
                "accepted": False,
                "code": "RESOLUTION_REQUEST_INVALID",
                "errors": ["missing request fields: phase"],
            },
            first.to_dict(),
        )

    def test_consumer_profile_uses_the_project_profile_contract_directly(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        request["consumer_profile"] = {
            "aec_mode": "read-only-mentor",
            "agent_adapters": ["example-adapter"],
            "lifecycle_authority": "consumer-owned",
            "profile_version": "example:1.0.0",
            "project": "example-owner/example-repo",
            "schema_version": "1.0.0",
            "workflow": "ticket-to-pr",
        }

        result = resolve(request, procedures)

        self.assertNotIsInstance(result, ResolutionRejection)
        payload = result.to_dict()
        self.assertEqual(
            "example-owner/example-repo",
            payload["source_identities"]["consumer_profile"],
        )
        self.assertEqual(
            "example:1.0.0",
            payload["project_profile_version"],
        )

    def test_invalid_untrusted_request_data_never_leaks_builtin_exceptions(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        missing_workflow_stage = copy.deepcopy(request)
        del missing_workflow_stage["workflow"]["stage"]
        old_consumer_shape = copy.deepcopy(request)
        old_consumer_shape["consumer_profile"] = {
            "identity": "example-consumer",
            "version": "example-consumer:1.0.0",
        }
        non_string_field = copy.deepcopy(request)
        non_string_field[3] = "invalid"
        invalid_requests = [
            None,
            {**request, "blockers": {}},
            {**request, "capability_profile": []},
            old_consumer_shape,
            {**request, "environment": ""},
            {**request, "evidence": [None]},
            {**request, "lane": 3},
            {**request, "phase": ["Verify"]},
            {**request, "policy": {"identity": "default-delivery"}},
            {
                **request,
                "required_procedure": {"identity": "verify-evidence"},
            },
            {**request, "revision": "not-a-git-revision"},
            {**request, "schema_version": "1.0.0"},
            {**request, "task_id": ""},
            missing_workflow_stage,
            non_string_field,
            {
                **request,
                "workflow": {
                    "identity": "ticket-to-pr",
                    "revision": "ticket-to-pr:1.0.0",
                    "stage": [],
                },
            },
        ]

        for invalid in invalid_requests:
            with self.subTest(request=invalid):
                first = resolve(invalid, procedures)
                second = resolve(invalid, procedures)
                self.assertIsInstance(first, ResolutionRejection)
                self.assertEqual(first, second)
                self.assertEqual("RESOLUTION_REQUEST_INVALID", first.to_dict()["code"])
                self.assertFalse(first.to_dict()["accepted"])

    def test_tampered_unavailable_decision_is_rejected_after_hash_recompute(self) -> None:
        request = load_json(
            ROOT / "tests/fixtures/resolver/red/unavailable-skill.json"
        )
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        result = resolve(request, procedures)
        self.assertNotIsInstance(result, ResolutionRejection)
        tampered = result.to_dict()
        tampered["allowed"] = True
        tampered["resolution_hash"] = compute_resolution_hash(tampered)

        self.assertEqual(
            ["SKILL_UNAVAILABLE decisions must set allowed=false"],
            validate_resolution(tampered),
        )

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
            "sha256:c9a4053e2fe0cad30d304b092ac4f9859e37f0a336ad243e60cf3dd62c6672a0",
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
                "consumer_profile": "example-owner/example-repo",
                "policy": "default-delivery",
                "procedure": "verify-evidence",
                "workflow": "ticket-to-pr",
            },
            first_payload["source_identities"],
        )
        self.assertEqual(
            {
                "capability_profile": "portable-python:1.0.0",
                "consumer_profile": "example:1.0.0",
                "policy": "default-delivery:1.0.0",
                "procedure": "verify-evidence:1.0.0",
                "workflow": "ticket-to-pr:1.0.0",
            },
            first_payload["source_revisions"],
        )
        identity_fields = {
            "capability_profile": "identity",
            "consumer_profile": "project",
            "policy": "identity",
        }
        for source, identity_field in identity_fields.items():
            changed = copy.deepcopy(request)
            changed[source][identity_field] = (
                "other-owner/other-repo"
                if source == "consumer_profile"
                else f"other-{source}"
            )
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
            "sha256:239971cfa54bf70ecd0693ca24297dd65857b340412fab348cb8ceab04ee8a4d",
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
