import copy
import json
import unittest
from pathlib import Path

from aec.resolver import (
    ResolutionRejection,
    canonical_resolution_bytes,
    compute_resolution_hash,
    resolve,
    validate_procedure_catalog,
    validate_resolution_request,
)
from tools.validate_foundation import validate_resolution


ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PHASES = {
    "Intake": ("Understand", "intake-outcome"),
    "Framing": ("Understand", "frame-delivery-context"),
    "Spec": ("Design", "specify-behavior-contract"),
    "Plan": ("Design", "plan-vertical-delivery"),
    "Build": ("Execute", "build-coherent-slice"),
    "Verify": ("Execute", "verify-evidence"),
    "Review": ("Assure & Release", "review-exact-change"),
    "PR": ("Assure & Release", "prepare-merge-candidate"),
    "Deploy": ("Assure & Release", "prove-live-revision"),
}
GOLDEN_HASHES = {
    "Intake": "sha256:7ab48b2e334ce87c253d46f1f56d0a73d505fabad6beff7b2265f412b4d2d517",
    "Framing": "sha256:f9b1a17342d98f09979d91ce74350b97cb9d0bb2fbc202bdbfe3e775cf236fc4",
    "Spec": "sha256:6b568c434eb1d77b5471558710c80e6432fa793ea359620f71eae02e6251cac3",
    "Plan": "sha256:95f3d45c80f94e21c9c6f9d1b55a5522ba576540b1da9131ba27a8d03878d49a",
    "Build": "sha256:371ce14e199078ef3ccda2c05cb43c09e2a1d55be55d979a9bc355fb261164c7",
    "Verify": "sha256:b08f7a178a505a649bf384e27e6d7a1ff7356a0a2eff04a716fdd180a5c5a5d0",
    "Review": "sha256:77817cc44a03837a6d40537f4b5236d1e49c5b164b61fbc15e64020ab8531224",
    "PR": "sha256:1ffb1a9e51136e733097bc19b0ce20574178e0aad7bc875c3a1072db9ec8ae8f",
    "Deploy": "sha256:74f967f6e2084c135b24e92b0cd7be27a76df05b98436d6c259e35de25fd34a9",
}


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def golden_common_facts(request: object) -> object:
    """Return caller facts that every lifecycle golden must share."""
    if not isinstance(request, dict):
        raise TypeError("golden request must be an object")
    common_facts = copy.deepcopy(request)
    for field in (
        "available_procedures",
        "phase",
        "required_procedure",
        "task_id",
    ):
        common_facts.pop(field)
    workflow = common_facts.get("workflow")
    if not isinstance(workflow, dict):
        raise TypeError("golden request workflow must be an object")
    workflow.pop("stage")
    return common_facts


def matching_golden_procedures(catalog: object, request: object) -> list[object]:
    """Return catalog entries matching the request's exact phase and pin."""
    if not isinstance(catalog, dict) or not isinstance(request, dict):
        return []
    required = request.get("required_procedure")
    procedures = catalog.get("procedures")
    if not isinstance(required, dict) or not isinstance(procedures, list):
        return []
    return [
        procedure
        for procedure in procedures
        if isinstance(procedure, dict)
        and procedure.get("phase") == request.get("phase")
        and procedure.get("identity") == required.get("identity")
        and procedure.get("revision") == required.get("revision")
    ]


class ResolverTracerTests(unittest.TestCase):
    def test_each_phase_resolves_one_complete_deterministic_golden_card(self) -> None:
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        self.assertEqual([], validate_procedure_catalog(procedures))
        self.assertEqual(
            {
                "build",
                "deploy",
                "framing",
                "intake",
                "plan",
                "pr",
                "review",
                "spec",
                "verify",
            },
            {
                path.stem
                for path in (ROOT / "tests/fixtures/resolver/golden").glob("*.json")
            },
        )

        shared_common_facts = None
        for phase, (stage, identity) in GOLDEN_PHASES.items():
            with self.subTest(phase=phase):
                fixture_name = "pr" if phase == "PR" else phase.lower()
                request = load_json(
                    ROOT / f"tests/fixtures/resolver/golden/{fixture_name}.json"
                )
                common_facts = golden_common_facts(request)
                if shared_common_facts is None:
                    shared_common_facts = common_facts
                self.assertEqual(shared_common_facts, common_facts)
                first = resolve(request, procedures)
                second = resolve(request, procedures)

                self.assertNotIsInstance(first, ResolutionRejection)
                self.assertNotIsInstance(second, ResolutionRejection)
                payload = first.to_dict()
                self.assertEqual([], validate_resolution_request(request))
                self.assertEqual(
                    [request["required_procedure"]],
                    request["available_procedures"],
                )
                matching_procedures = matching_golden_procedures(
                    procedures,
                    request,
                )
                self.assertEqual(1, len(matching_procedures))
                self.assertEqual(
                    request["required_procedure"],
                    {
                        "identity": matching_procedures[0]["identity"],
                        "revision": matching_procedures[0]["revision"],
                    },
                )
                self.assertEqual(first.canonical_bytes, second.canonical_bytes)
                self.assertEqual(first.resolution_hash, second.resolution_hash)
                self.assertEqual(GOLDEN_HASHES[phase], first.resolution_hash)
                self.assertEqual([], validate_resolution(payload))
                self.assertEqual(phase, payload["phase"])
                self.assertEqual(stage, payload["workflow_stage"])
                self.assertEqual(identity, payload["primary_procedure"])
                self.assertEqual("Evidence needed", payload["gate"])
                self.assertTrue(payload["rationale"]["principle_ids"])
                self.assertTrue(payload["rationale"]["summary"])
                self.assertTrue(payload["required_evidence"])
                self.assertTrue(payload["good"])
                self.assertTrue(payload["finished"])
                self.assertTrue(payload["anti_example"])
                if phase != "Verify":
                    self.assertEqual(
                        [f"aec-ticket-to-pr-{phase.lower()}"],
                        payload["rationale"]["principle_ids"],
                    )

    def test_unapproved_golden_request_drift_is_not_normalized_away(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/intake.json")
        baseline = golden_common_facts(request)
        mutations = []

        changed = copy.deepcopy(request)
        changed["lane"] = "OTHER"
        mutations.append(changed)

        changed = copy.deepcopy(request)
        changed["capability_profile"]["capabilities"].append("browser")
        mutations.append(changed)

        changed = copy.deepcopy(request)
        changed["evidence"] = [
            {
                "accepted": False,
                "environment": "test",
                "kind": "unexpected-evidence",
                "revision": "0123456789abcdef0123456789abcdef01234567",
            }
        ]
        mutations.append(changed)

        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                self.assertNotEqual(baseline, golden_common_facts(mutation))

    def test_golden_pin_allows_future_same_phase_procedures(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/intake.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        intake_procedure = next(
            procedure
            for procedure in procedures["procedures"]
            if procedure["identity"] == "intake-outcome"
        )
        future_procedure = copy.deepcopy(intake_procedure)
        future_procedure["identity"] = "future-intake-procedure"
        future_procedure["revision"] = "future-intake-procedure:1.0.0"
        procedures["procedures"].append(future_procedure)

        self.assertEqual([], validate_procedure_catalog(procedures))
        self.assertEqual(1, len(matching_golden_procedures(procedures, request)))
        decision = resolve(request, procedures)
        self.assertNotIsInstance(decision, ResolutionRejection)
        self.assertEqual("intake-outcome", decision.to_dict()["primary_procedure"])

    def test_rejected_evidence_changes_stable_request_binding_and_decision(
        self,
    ) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        changed = copy.deepcopy(request)
        changed["evidence"] = [
            {
                "accepted": False,
                "environment": request["environment"],
                "kind": "focused-test-report",
                "revision": request["revision"],
            }
        ]

        baseline_first = resolve(request, procedures)
        baseline_second = resolve(request, procedures)
        changed_first = resolve(changed, procedures)
        changed_second = resolve(changed, procedures)
        baseline = baseline_first.to_dict()
        changed_payload = changed_first.to_dict()

        self.assertEqual(
            baseline_first.canonical_bytes, baseline_second.canonical_bytes
        )
        self.assertEqual(changed_first.canonical_bytes, changed_second.canonical_bytes)
        self.assertEqual("2.0.0", baseline["schema_version"])
        self.assertNotEqual(
            baseline["input_bindings"]["resolution_request"],
            changed_payload["input_bindings"]["resolution_request"],
        )
        self.assertEqual(
            baseline["input_bindings"]["procedure_catalog"],
            changed_payload["input_bindings"]["procedure_catalog"],
        )
        self.assertNotEqual(
            baseline["resolution_hash"],
            changed_payload["resolution_hash"],
        )
        self.assertEqual(baseline["gate"], changed_payload["gate"])
        self.assertEqual(
            baseline["required_evidence"],
            changed_payload["required_evidence"],
        )

    def test_malformed_unrelated_catalog_revision_is_rejected_twice(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        procedures["procedures"][0]["revision"] = "not-pinned"

        first = resolve(request, procedures)
        second = resolve(request, procedures)

        self.assertIsInstance(first, ResolutionRejection)
        self.assertEqual(first, second)
        self.assertEqual(
            {
                "accepted": False,
                "code": "PROCEDURE_CATALOG_INVALID",
                "errors": ["procedures[0].revision must pin its identity and version"],
            },
            first.to_dict(),
        )

    def test_catalog_revision_rejects_schema_invalid_identity_prefixes(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")

        for identity in ("bad identity", "bad:identity"):
            with self.subTest(identity=identity):
                procedures = load_json(
                    ROOT / "config/procedures/ticket-to-pr.json"
                )
                procedures["procedures"][0]["identity"] = identity
                procedures["procedures"][0]["revision"] = f"{identity}:1.0.0"

                result = resolve(request, procedures)

                self.assertIsInstance(result, ResolutionRejection)
                self.assertEqual(
                    {
                        "accepted": False,
                        "code": "PROCEDURE_CATALOG_INVALID",
                        "errors": [
                            "procedures[0].revision must pin its identity and version"
                        ],
                    },
                    result.to_dict(),
                )

    def test_material_request_axes_change_stable_binding_and_hash(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")

        baseline_first = resolve(request, procedures)
        baseline_second = resolve(request, procedures)
        self.assertNotIsInstance(baseline_first, ResolutionRejection)
        self.assertEqual(
            baseline_first.canonical_bytes, baseline_second.canonical_bytes
        )
        baseline = baseline_first.to_dict()

        mutations = []
        changed = copy.deepcopy(request)
        changed["revision"] = "fedcba9876543210fedcba9876543210fedcba98"
        mutations.append(("revision", changed))

        changed = copy.deepcopy(request)
        changed["environment"] = "staging"
        mutations.append(("environment", changed))

        changed = copy.deepcopy(request)
        changed["consumer_profile"]["profile_version"] = "example:2.0.0"
        mutations.append(("profile-version", changed))

        changed = copy.deepcopy(request)
        changed["evidence"] = [
            {
                "accepted": False,
                "environment": request["environment"],
                "kind": "focused-test-report",
                "revision": request["revision"],
            }
        ]
        mutations.append(("rejected-evidence", changed))

        changed = copy.deepcopy(request)
        changed["evidence"] = [
            {
                "accepted": True,
                "environment": request["environment"],
                "kind": "focused-test-report",
                "revision": "fedcba9876543210fedcba9876543210fedcba98",
            }
        ]
        mutations.append(("wrong-revision-evidence", changed))

        changed = copy.deepcopy(request)
        changed["evidence"] = [
            {
                "accepted": True,
                "environment": "staging",
                "kind": "focused-test-report",
                "revision": request["revision"],
            }
        ]
        mutations.append(("cross-environment-evidence", changed))

        changed = copy.deepcopy(request)
        changed["capability_profile"]["capabilities"].append("browser")
        mutations.append(("capability-set", changed))

        changed = copy.deepcopy(request)
        changed["policy"]["facts"]["require_exact_environment"] = False
        mutations.append(("policy-facts", changed))

        for axis, mutation in mutations:
            with self.subTest(axis=axis):
                first = resolve(mutation, procedures)
                second = resolve(mutation, procedures)
                self.assertNotIsInstance(first, ResolutionRejection)
                self.assertEqual(first.canonical_bytes, second.canonical_bytes)
                payload = first.to_dict()
                self.assertNotEqual(
                    baseline["input_bindings"]["resolution_request"],
                    payload["input_bindings"]["resolution_request"],
                )
                self.assertEqual(
                    baseline["input_bindings"]["procedure_catalog"],
                    payload["input_bindings"]["procedure_catalog"],
                )
                self.assertNotEqual(
                    baseline["resolution_hash"],
                    payload["resolution_hash"],
                )
                self.assertEqual(baseline["gate"], payload["gate"])
                self.assertEqual(
                    baseline["required_evidence"],
                    payload["required_evidence"],
                )

    def test_unrelated_catalog_change_changes_only_catalog_binding_and_hash(
        self,
    ) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        changed = copy.deepcopy(procedures)
        intake = next(
            procedure
            for procedure in changed["procedures"]
            if procedure["identity"] == "intake-outcome"
        )
        intake["anti_example"] = "A changed but still valid unrelated anti-example."

        baseline_first = resolve(request, procedures)
        baseline_second = resolve(request, procedures)
        changed_first = resolve(request, changed)
        changed_second = resolve(request, changed)
        self.assertNotIsInstance(baseline_first, ResolutionRejection)
        self.assertNotIsInstance(changed_first, ResolutionRejection)
        self.assertEqual(
            baseline_first.canonical_bytes, baseline_second.canonical_bytes
        )
        self.assertEqual(changed_first.canonical_bytes, changed_second.canonical_bytes)
        baseline = baseline_first.to_dict()
        changed_payload = changed_first.to_dict()

        self.assertEqual(
            baseline["input_bindings"]["resolution_request"],
            changed_payload["input_bindings"]["resolution_request"],
        )
        self.assertNotEqual(
            baseline["input_bindings"]["procedure_catalog"],
            changed_payload["input_bindings"]["procedure_catalog"],
        )
        self.assertNotEqual(
            baseline["resolution_hash"],
            changed_payload["resolution_hash"],
        )
        for field in (
            "gate",
            "phase",
            "primary_procedure",
            "rationale",
            "required_evidence",
        ):
            self.assertEqual(baseline[field], changed_payload[field])

    def test_phase_and_procedure_mismatch_is_rejected_twice(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        request["phase"] = "Build"

        first = resolve(request, procedures)
        second = resolve(request, procedures)

        self.assertIsInstance(first, ResolutionRejection)
        self.assertEqual(first, second)
        self.assertEqual(
            {
                "accepted": False,
                "code": "RESOLUTION_REQUEST_INVALID",
                "errors": [
                    "required_procedure must identify exactly one catalog procedure"
                ],
            },
            first.to_dict(),
        )

    def test_semantically_unordered_input_collections_have_stable_decision(
        self,
    ) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        request["available_procedures"].append(
            {
                "identity": "intake-outcome",
                "revision": "intake-outcome:1.0.0",
            }
        )
        request["blockers"] = [
            {"active": False, "identity": "second", "reason_code": "SECOND"},
            {"active": False, "identity": "first", "reason_code": "FIRST"},
        ]
        request["capability_profile"]["capabilities"].append("browser")
        request["consumer_profile"]["agent_adapters"].append("other-adapter")
        request["evidence"] = [
            {
                "accepted": False,
                "environment": "staging",
                "kind": "integration-test-report",
                "revision": request["revision"],
            },
            {
                "accepted": False,
                "environment": "test",
                "kind": "focused-test-report",
                "revision": "fedcba9876543210fedcba9876543210fedcba98",
            },
        ]

        reordered_request = copy.deepcopy(request)
        for field in ("available_procedures", "blockers", "evidence"):
            reordered_request[field].reverse()
        reordered_request["capability_profile"]["capabilities"].reverse()
        reordered_request["consumer_profile"]["agent_adapters"].reverse()

        reordered_catalog = copy.deepcopy(procedures)
        reordered_catalog["procedures"].reverse()
        verify = next(
            procedure
            for procedure in reordered_catalog["procedures"]
            if procedure["identity"] == "verify-evidence"
        )
        verify["required_evidence"].reverse()

        first = resolve(request, procedures)
        first_repeat = resolve(request, procedures)
        second = resolve(reordered_request, reordered_catalog)
        second_repeat = resolve(reordered_request, reordered_catalog)

        self.assertNotIsInstance(first, ResolutionRejection)
        self.assertNotIsInstance(first_repeat, ResolutionRejection)
        self.assertNotIsInstance(second, ResolutionRejection)
        self.assertNotIsInstance(second_repeat, ResolutionRejection)
        self.assertEqual(first.canonical_bytes, first_repeat.canonical_bytes)
        self.assertEqual(first.resolution_hash, first_repeat.resolution_hash)
        self.assertEqual(second.canonical_bytes, second_repeat.canonical_bytes)
        self.assertEqual(second.resolution_hash, second_repeat.resolution_hash)
        self.assertEqual(first.canonical_bytes, second.canonical_bytes)
        self.assertEqual(first.resolution_hash, second.resolution_hash)
        self.assertEqual(
            first.to_dict()["input_bindings"],
            second.to_dict()["input_bindings"],
        )

    def test_missing_procedure_catalog_fields_return_catalog_rejection(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")

        result = resolve(request, {})

        self.assertIsInstance(result, ResolutionRejection)
        self.assertEqual(
            {
                "accepted": False,
                "code": "PROCEDURE_CATALOG_INVALID",
                "errors": [
                    "missing procedure catalog fields: procedures, schema_version"
                ],
            },
            result.to_dict(),
        )

    def test_string_procedure_catalog_returns_catalog_rejection(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")

        result = resolve(request, "not-a-catalog")

        self.assertIsInstance(result, ResolutionRejection)
        self.assertEqual(
            {
                "accepted": False,
                "code": "PROCEDURE_CATALOG_INVALID",
                "errors": ["procedure catalog must be an object"],
            },
            result.to_dict(),
        )

    def test_non_list_procedure_catalog_returns_catalog_rejection(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        invalid_catalog = {"procedures": None, "schema_version": "1.0.0"}

        result = resolve(request, invalid_catalog)

        self.assertIsInstance(result, ResolutionRejection)
        self.assertEqual(
            {
                "accepted": False,
                "code": "PROCEDURE_CATALOG_INVALID",
                "errors": ["procedure catalog procedures must be a list"],
            },
            result.to_dict(),
        )

    def test_malformed_catalog_entry_returns_catalog_rejection(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        invalid_catalog = load_json(
            ROOT / "tests/fixtures/resolver/red/malformed-procedure-catalog.json"
        )

        result = resolve(request, invalid_catalog)

        self.assertIsInstance(result, ResolutionRejection)
        self.assertEqual(
            {
                "accepted": False,
                "code": "PROCEDURE_CATALOG_INVALID",
                "errors": ["procedures[0] fields do not match the contract"],
            },
            result.to_dict(),
        )

    def test_duplicate_required_catalog_procedure_returns_catalog_rejection(
        self,
    ) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        catalog = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        duplicate = copy.deepcopy(catalog["procedures"][0])
        duplicate["anti_example"] = "Different text with the same pinned identity."
        catalog["procedures"].append(duplicate)

        result = resolve(request, catalog)

        self.assertIsInstance(result, ResolutionRejection)
        self.assertEqual(
            {
                "accepted": False,
                "code": "PROCEDURE_CATALOG_INVALID",
                "errors": ["procedure catalog references must be unique"],
            },
            result.to_dict(),
        )

    def test_matched_procedure_missing_required_fields_returns_catalog_rejection(
        self,
    ) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        catalog = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        del catalog["procedures"][0]["required_evidence"]

        result = resolve(request, catalog)

        self.assertIsInstance(result, ResolutionRejection)
        self.assertEqual("PROCEDURE_CATALOG_INVALID", result.to_dict()["code"])
        self.assertEqual(
            ["procedures[0] fields do not match the contract"],
            result.to_dict()["errors"],
        )

    def test_matched_procedure_invalid_required_evidence_returns_catalog_rejection(
        self,
    ) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        catalog = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        catalog["procedures"][0]["required_evidence"] = None

        result = resolve(request, catalog)

        self.assertIsInstance(result, ResolutionRejection)
        self.assertEqual("PROCEDURE_CATALOG_INVALID", result.to_dict()["code"])
        self.assertEqual(
            ["procedures[0].required_evidence must be a normalized string list"],
            result.to_dict()["errors"],
        )

    def test_catalog_cannot_inject_an_arbitrary_uppercase_reason_code(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        catalog = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        catalog["procedures"][0]["reason_code"] = "ARBITRARY_GREEN"

        result = resolve(request, catalog)

        self.assertIsInstance(result, ResolutionRejection)
        self.assertEqual(
            {
                "accepted": False,
                "code": "PROCEDURE_CATALOG_INVALID",
                "errors": [
                    (
                        "procedures[0].reason_code must equal "
                        "ACCEPTANCE_EVIDENCE_INCOMPLETE"
                    )
                ],
            },
            result.to_dict(),
        )

    def test_malformed_available_procedure_returns_structured_rejection(self) -> None:
        request = load_json(
            ROOT / "tests/fixtures/resolver/red/malformed-available-procedure.json"
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

    def test_invalid_untrusted_request_data_never_leaks_builtin_exceptions(
        self,
    ) -> None:
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

    def test_tampered_unavailable_decision_is_rejected_after_hash_recompute(
        self,
    ) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/red/unavailable-skill.json")
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

    def test_tampered_evidence_needed_decision_cannot_claim_ready(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        result = resolve(request, procedures)
        self.assertNotIsInstance(result, ResolutionRejection)
        tampered = result.to_dict()
        tampered["gate"] = "Ready"
        tampered["resolution_hash"] = compute_resolution_hash(tampered)

        self.assertEqual(
            [
                "Ready decisions must use ACCEPTANCE_EVIDENCE_COMPLETE",
                "Ready decisions must not require evidence",
            ],
            validate_resolution(tampered),
        )

    def test_tampered_decision_cannot_invent_an_uppercase_reason_code(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        result = resolve(request, procedures)
        self.assertNotIsInstance(result, ResolutionRejection)
        tampered = result.to_dict()
        tampered["reason_code"] = "ARBITRARY_GREEN"
        tampered["resolution_hash"] = compute_resolution_hash(tampered)

        self.assertEqual(
            [
                "reason_code is unsupported",
                ("Evidence needed decisions must use ACCEPTANCE_EVIDENCE_INCOMPLETE"),
            ],
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
            "sha256:b08f7a178a505a649bf384e27e6d7a1ff7356a0a2eff04a716fdd180a5c5a5d0",
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
                "principle_ids": ["aec-evidence-input-binding"],
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
        request = load_json(ROOT / "tests/fixtures/resolver/red/unavailable-skill.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")

        first = resolve(request, procedures)
        second = resolve(request, procedures)
        payload = first.to_dict()

        self.assertEqual(first.canonical_bytes, second.canonical_bytes)
        self.assertEqual(first.resolution_hash, second.resolution_hash)
        self.assertEqual(
            "sha256:2577f7012c06d44ae9dd89e0bd54b04a369c748a4d45c58a0133a88e5170028b",
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
        request = load_json(ROOT / "tests/fixtures/resolver/red/unavailable-skill.json")
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
        request = load_json(ROOT / "tests/fixtures/resolver/red/unavailable-skill.json")
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
