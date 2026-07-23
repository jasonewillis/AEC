import copy
import json
import unittest
from pathlib import Path

from aec.resolver import (
    BLOCKER_REASON_PRECEDENCE as RUNTIME_BLOCKER_PRECEDENCE,
    BLOCKER_REASON_REGISTRY,
    ResolutionRejection,
    compute_resolution_hash,
    resolve,
)
from tools.validate_foundation import validate_resolution


ROOT = Path(__file__).resolve().parents[1]
BLOCKER_PRECEDENCE = (
    "AUTHORITY_CONFLICT",
    "PRIVATE_INPUT_INCLUDED",
    "POLICY_CONFLICT",
    "LIFECYCLE_STATE_STALE",
    "EVIDENCE_CONTRADICTED",
)


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


class ResolverBlockerPrecedenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = load_json(
            ROOT / "tests/fixtures/resolver/golden/verify.json"
        )
        self.procedures = load_json(
            ROOT / "config/procedures/ticket-to-pr.json"
        )

    def resolve_payload(self, request: object) -> dict[str, object]:
        result = resolve(request, self.procedures)
        self.assertNotIsInstance(result, ResolutionRejection)
        return result.to_dict()

    def test_closed_blocker_registry_rejects_unknown_reasons(self) -> None:
        self.assertEqual(BLOCKER_PRECEDENCE, RUNTIME_BLOCKER_PRECEDENCE)
        self.assertEqual(set(BLOCKER_PRECEDENCE), set(BLOCKER_REASON_REGISTRY))
        schema = load_json(ROOT / "schemas/resolution-request.schema.json")
        schema_reasons = schema["properties"]["blockers"]["items"]["properties"][
            "reason_code"
        ]["enum"]
        self.assertEqual(set(BLOCKER_PRECEDENCE), set(schema_reasons))
        self.request["blockers"] = [
            {
                "active": True,
                "identity": "unknown",
                "reason_code": "UNKNOWN_BLOCKER",
            }
        ]

        first = resolve(self.request, self.procedures)
        second = resolve(self.request, self.procedures)

        self.assertIsInstance(first, ResolutionRejection)
        self.assertEqual(first, second)
        self.assertEqual(
            ("blockers[0].reason_code is unsupported",),
            first.errors,
        )

    def test_decision_schema_binds_each_blocker_reason_and_evidence(self) -> None:
        schema = load_json(ROOT / "schemas/resolution-decision.schema.json")
        contracts = {}
        for rule in schema["allOf"]:
            condition = rule.get("if", {}).get("properties", {}).get(
                "reason_code", {}
            )
            reason_code = condition.get("const")
            if reason_code is None:
                continue
            properties = rule["then"]["properties"]
            contracts[reason_code] = {
                "allowed": properties["allowed"]["const"],
                "gate": properties["gate"]["const"],
                "primary_reason": properties["primary_blocker"]["properties"][
                    "reason_code"
                ]["const"],
                "required_evidence": properties["required_evidence"]["const"],
            }

        expected = {
            reason_code: {
                "allowed": False,
                "gate": "Blocked",
                "primary_reason": reason_code,
                "required_evidence": BLOCKER_REASON_REGISTRY[reason_code][
                    "required_evidence"
                ],
            }
            for reason_code in BLOCKER_PRECEDENCE
        }
        expected["SKILL_UNAVAILABLE"] = {
            "allowed": False,
            "gate": "Blocked",
            "primary_reason": "SKILL_UNAVAILABLE",
            "required_evidence": ["procedure-availability"],
        }
        self.assertEqual(expected, contracts)

    def test_inactive_blockers_do_not_override_evidence_gate(self) -> None:
        self.request["blockers"] = [
            {
                "active": False,
                "identity": "stale-phase",
                "reason_code": "LIFECYCLE_STATE_STALE",
            }
        ]

        payload = self.resolve_payload(self.request)

        self.assertEqual("Evidence needed", payload["gate"])
        self.assertEqual(
            "ACCEPTANCE_EVIDENCE_INCOMPLETE",
            payload["reason_code"],
        )
        self.assertIsNone(payload["primary_blocker"])
        self.assertEqual("verify-evidence", payload["primary_procedure"])

    def test_one_active_blocker_has_fail_closed_priority_over_ready(self) -> None:
        request = copy.deepcopy(self.request)
        required_kinds = next(
            procedure["required_evidence"]
            for procedure in self.procedures["procedures"]
            if procedure["identity"]
            == request["required_procedure"]["identity"]
        )
        request["evidence"] = [
            {
                "accepted": True,
                "environment": request["environment"],
                "kind": kind,
                "revision": request["revision"],
            }
            for kind in required_kinds
        ]
        request["blockers"] = [
            {
                "active": True,
                "identity": "stale-phase",
                "reason_code": "LIFECYCLE_STATE_STALE",
            }
        ]

        payload = self.resolve_payload(request)

        self.assertEqual([], validate_resolution(payload))
        self.assertEqual("Blocked", payload["gate"])
        self.assertFalse(payload["allowed"])
        self.assertEqual("LIFECYCLE_STATE_STALE", payload["reason_code"])
        self.assertEqual(
            {
                "identity": "stale-phase",
                "reason_code": "LIFECYCLE_STATE_STALE",
            },
            payload["primary_blocker"],
        )
        self.assertIsNone(payload["primary_procedure"])
        self.assertTrue(payload["required_evidence"])

    def test_multiple_active_blockers_have_one_order_independent_primary(self) -> None:
        blockers = [
            {
                "active": True,
                "identity": f"{index}-{reason.lower()}",
                "reason_code": reason,
            }
            for index, reason in enumerate(reversed(BLOCKER_PRECEDENCE), start=1)
        ]
        first_request = copy.deepcopy(self.request)
        first_request["blockers"] = blockers
        second_request = copy.deepcopy(first_request)
        second_request["blockers"].reverse()

        first = self.resolve_payload(first_request)
        second = self.resolve_payload(second_request)

        self.assertEqual(first, second)
        self.assertEqual(first["resolution_hash"], second["resolution_hash"])
        self.assertEqual("AUTHORITY_CONFLICT", first["reason_code"])
        self.assertEqual(
            {
                "identity": "5-authority_conflict",
                "reason_code": "AUTHORITY_CONFLICT",
            },
            first["primary_blocker"],
        )

    def test_identity_breaks_same_reason_ties_deterministically(self) -> None:
        self.request["blockers"] = [
            {
                "active": True,
                "identity": "zeta",
                "reason_code": "POLICY_CONFLICT",
            },
            {
                "active": True,
                "identity": "alpha",
                "reason_code": "POLICY_CONFLICT",
            },
        ]

        payload = self.resolve_payload(self.request)

        self.assertEqual("alpha", payload["primary_blocker"]["identity"])

    def test_active_caller_blocker_precedes_skill_unavailable(self) -> None:
        request = load_json(
            ROOT / "tests/fixtures/resolver/red/unavailable-skill.json"
        )
        request["blockers"] = [
            {
                "active": True,
                "identity": "policy-denial",
                "reason_code": "POLICY_CONFLICT",
            }
        ]

        payload = self.resolve_payload(request)

        self.assertEqual("Blocked", payload["gate"])
        self.assertEqual("POLICY_CONFLICT", payload["reason_code"])
        self.assertEqual(
            {
                "identity": "policy-denial",
                "reason_code": "POLICY_CONFLICT",
            },
            payload["primary_blocker"],
        )
        self.assertIsNone(payload["primary_procedure"])

    def test_blocker_tamper_changes_hash_and_reason_mismatch_is_rejected(self) -> None:
        self.request["blockers"] = [
            {
                "active": True,
                "identity": "policy-denial",
                "reason_code": "POLICY_CONFLICT",
            }
        ]
        payload = self.resolve_payload(self.request)
        tampered = copy.deepcopy(payload)
        tampered["primary_blocker"]["reason_code"] = "LIFECYCLE_STATE_STALE"
        tampered["resolution_hash"] = compute_resolution_hash(tampered)

        self.assertNotEqual(payload["resolution_hash"], tampered["resolution_hash"])
        self.assertIn(
            "primary_blocker.reason_code must equal reason_code",
            validate_resolution(tampered),
        )


if __name__ == "__main__":
    unittest.main()
