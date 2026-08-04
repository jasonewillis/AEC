import copy
import json
import unittest
from pathlib import Path

from aec.mentoring import validate_decision_context
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
    "Intake": "sha256:26c8a4cba539657d74cb32a847dc275b42e6bdd66a3b5eb8f89a33b8c77276ac",
    "Framing": "sha256:da1817d1c51b2a3d8edf8949703f6acbca356fcbb5c90e4c9feb636d8f3089d5",
    "Spec": "sha256:ea7fda42dcb03fe0040e1ba6dcab584a65d21a3eaaaa9e481720966d11e0c045",
    "Plan": "sha256:fed2bf404aa1b6c340490c09b3ae98d4becce6db57ec4b73b6d95687b9284b91",
    "Build": "sha256:178f1acfc74e2105040adbd5b8a2895d060d3b298b01197ee456ef1c6e6b6870",
    "Verify": "sha256:8489f951e3b1cb41b63d7673aeb18a56bd5b16b2d45fa976275f8c16205526ee",
    "Review": "sha256:9bfa2df8d5718b80a06dac9996b63f4872f729d2fb2df14c3aecdfdfbdd31152",
    "PR": "sha256:ca2b967370e1a1795b215d9da2b61dbe4b756f609e53d3ae9752314d2e9e2a30",
    "Deploy": "sha256:246b06e43f2d575246543f4984cc3459706972add6875fe0085e18b5c9954f01",
}

MATERIAL_DECISION_CONTEXT = {
    "authority": {
        "owner": "consumer-owner",
        "reason": "The repository owner controls dependency and environment policy.",
    },
    "choices": [
        {
            "identity": "isolate-import-boundary",
            "summary": "Move optional ML imports behind an explicit runtime boundary.",
            "tradeoffs": {
                "maintainability": "Keeps optional dependencies out of unrelated paths.",
                "quality": "Preserves real UI proof without replacing the production path.",
                "reversibility": "Can be reverted as one bounded adapter change.",
                "risk": "Requires care to preserve existing ML behavior.",
                "scope": "One import boundary and focused regression coverage.",
            },
        },
        {
            "identity": "install-ml-stack",
            "summary": "Install the complete ML dependency stack in every test environment.",
            "tradeoffs": {
                "maintainability": "Couples all test paths to a platform-specific stack.",
                "quality": "Exercises the production import path directly.",
                "reversibility": "Dependency changes can be rolled back.",
                "risk": "May hide an unnecessary eager-import dependency.",
                "scope": "Environment and dependency configuration changes.",
            },
        },
    ],
    "context": {
        "evidence_quality": "direct-verified",
        "revision": "0123456789abcdef0123456789abcdef01234567",
    },
    "question": "How should optional ML imports be isolated for real UI proof?",
    "recommendation": {
        "choice": "isolate-import-boundary",
        "confidence": "high",
        "expected_result": {
            "baseline": "4",
            "direction": "decrease",
            "measure": "unrelated-import-failures",
            "target": "0",
            "threshold": "Zero unrelated import failures in the focused UI proof run.",
            "unit": "failures",
        },
        "falsifier": (
            "The pinned adapter is invoked and the same normalized request "
            "still resolves to a different decision hash."
        ),
        "principal_uncertainty": (
            "Whether any production entry point still imports the ML stack eagerly."
        ),
        "revisit_when": [
            "The ML stack becomes a required dependency for every application entry point."
        ],
        "why": "It removes the unrelated import failure at the narrowest durable seam.",
    },
    "schema_version": "2.0.0",
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
                self.assertEqual(
                    "Needs review" if phase == "Review" else "Evidence needed",
                    payload["gate"],
                )
                self.assertTrue(payload["rationale"]["principle_ids"])
                self.assertTrue(payload["rationale"]["summary"])
                self.assertTrue(payload["required_evidence"])
                self.assertTrue(payload["good"])
                self.assertTrue(payload["finished"])
                self.assertTrue(payload["anti_example"])
                self.assertEqual(
                    {
                        "lesson",
                        "recognition_heuristic",
                        "why_gate_exists",
                    },
                    set(payload["mentoring"]),
                )
                self.assertTrue(all(payload["mentoring"].values()))
                self.assertIsNone(payload["decision_support"])
                if phase != "Verify":
                    self.assertEqual(
                        [f"aec-ticket-to-pr-{phase.lower()}"],
                        payload["rationale"]["principle_ids"],
                    )

    def test_material_decision_context_is_validated_bound_and_rendered(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/intake.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        assert isinstance(request, dict)
        request["decision_context"] = copy.deepcopy(MATERIAL_DECISION_CONTEXT)

        first = resolve(request, procedures)
        second = resolve(copy.deepcopy(request), procedures)

        self.assertNotIsInstance(first, ResolutionRejection)
        self.assertEqual(first, second)
        self.assertEqual(
            MATERIAL_DECISION_CONTEXT,
            first.to_dict()["decision_support"],
        )

        changed = copy.deepcopy(request)
        changed["decision_context"]["recommendation"]["why"] = (
            "A changed reason must change the bound resolution."
        )
        changed_result = resolve(changed, procedures)
        self.assertNotIsInstance(changed_result, ResolutionRejection)
        self.assertNotEqual(first.resolution_hash, changed_result.resolution_hash)

    def test_malformed_decision_context_fails_closed(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/intake.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        assert isinstance(request, dict)
        invalid_contexts = []

        one_choice = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
        one_choice["choices"] = one_choice["choices"][:1]
        invalid_contexts.append(one_choice)

        duplicate = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
        duplicate["choices"][1]["identity"] = duplicate["choices"][0]["identity"]
        invalid_contexts.append(duplicate)

        unknown_recommendation = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
        unknown_recommendation["recommendation"]["choice"] = "not-a-choice"
        invalid_contexts.append(unknown_recommendation)

        unknown_authority = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
        unknown_authority["authority"]["owner"] = "aec"
        invalid_contexts.append(unknown_authority)

        missing_tradeoff = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
        del missing_tradeoff["choices"][0]["tradeoffs"]["risk"]
        invalid_contexts.append(missing_tradeoff)

        unknown_field = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
        unknown_field["agent_decision"] = True
        invalid_contexts.append(unknown_field)

        unversioned = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
        del unversioned["schema_version"]
        invalid_contexts.append(unversioned)

        missing_context = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
        del missing_context["context"]
        invalid_contexts.append(missing_context)

        stale_context = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
        stale_context["context"]["revision"] = "f" * 40
        invalid_contexts.append(stale_context)

        insufficient_context = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
        insufficient_context["context"]["evidence_quality"] = "assumed"
        invalid_contexts.append(insufficient_context)

        missing_uncertainty = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
        del missing_uncertainty["recommendation"]["principal_uncertainty"]
        invalid_contexts.append(missing_uncertainty)

        # RED CANARY for #59. A recommendation that never says what would
        # refute it can be marked supported because the measure moved for an
        # unrelated reason -- right answer, wrong reason, with nothing in the
        # contract able to catch it. Absent falsifier, absent card.
        missing_falsifier = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
        del missing_falsifier["recommendation"]["falsifier"]
        invalid_contexts.append(missing_falsifier)

        # Blank is not a falsifier. The field being present must not be
        # satisfiable by whitespace, the same bar every other prose field here
        # is held to.
        blank_falsifier = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
        blank_falsifier["recommendation"]["falsifier"] = "   "
        invalid_contexts.append(blank_falsifier)

        unmeasurable = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
        unmeasurable["recommendation"]["expected_result"]["measure"] = "Faster Builds"
        invalid_contexts.append(unmeasurable)

        uncitable_choice = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
        uncitable_choice["choices"][0]["identity"] = "Isolate the import boundary"
        uncitable_choice["recommendation"]["choice"] = "Isolate the import boundary"
        invalid_contexts.append(uncitable_choice)

        # An expected result is comparable only when baseline, target, and direction agree.
        for field, value in (
            ("target", "4"),
            ("target", "9"),
            ("direction", "increase"),
            ("direction", "hold"),
            ("baseline", 4),
            ("baseline", 4.0),
            ("baseline", True),
            ("target", "0.0"),
            ("target", "+0"),
            ("target", "-0"),
            ("target", "00"),
            ("unit", "Failures Per Run"),
            ("unit", ""),
        ):
            incomparable = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
            incomparable["recommendation"]["expected_result"][field] = value
            invalid_contexts.append(incomparable)

        for field in ("baseline", "target", "unit"):
            incomplete = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
            del incomplete["recommendation"]["expected_result"][field]
            invalid_contexts.append(incomplete)

        held = copy.deepcopy(MATERIAL_DECISION_CONTEXT)
        held["recommendation"]["expected_result"].update(
            {"baseline": "4", "direction": "hold", "target": "4"}
        )
        self.assertEqual(
            [],
            validate_decision_context(held, revision=held["context"]["revision"]),
        )

        for context in invalid_contexts:
            with self.subTest(context=context):
                invalid = copy.deepcopy(request)
                invalid["decision_context"] = context
                self.assertIsInstance(
                    resolve(invalid, procedures),
                    ResolutionRejection,
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
        self.assertEqual("4.0.0", baseline["schema_version"])
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
                procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
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
            {
                "active": False,
                "identity": "second",
                "reason_code": "POLICY_CONFLICT",
            },
            {
                "active": False,
                "identity": "first",
                "reason_code": "LIFECYCLE_STATE_STALE",
            },
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
        invalid_catalog = {"procedures": None, "schema_version": "2.0.0"}

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

    def test_decision_rejects_both_primary_subjects_after_hash_recompute(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/red/unavailable-skill.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        result = resolve(request, procedures)
        self.assertNotIsInstance(result, ResolutionRejection)
        tampered = result.to_dict()
        tampered["primary_procedure"] = request["required_procedure"]["identity"]
        tampered["resolution_hash"] = compute_resolution_hash(tampered)

        self.assertEqual(
            [
                "decision must contain exactly one primary procedure or blocker",
                "unavailable required procedure cannot be selected",
            ],
            validate_resolution(tampered),
        )

    def test_decision_rejects_neither_primary_subject_after_hash_recompute(
        self,
    ) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        result = resolve(request, procedures)
        self.assertNotIsInstance(result, ResolutionRejection)
        tampered = result.to_dict()
        tampered["primary_procedure"] = None
        tampered["primary_blocker"] = None
        tampered["resolution_hash"] = compute_resolution_hash(tampered)

        self.assertEqual(
            [
                "decision must contain exactly one primary procedure or blocker",
                "primary_procedure must identify the selected procedure",
                "selected procedure must equal the required procedure",
            ],
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

    def test_complete_review_cannot_claim_needs_review_after_hash_recompute(
        self,
    ) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/review.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        request["evidence"] = [
            {
                "accepted": True,
                "environment": request["environment"],
                "kind": kind,
                "revision": request["revision"],
            }
            for kind in ("base-head-binding", "independent-review")
        ]
        result = resolve(request, procedures)
        self.assertNotIsInstance(result, ResolutionRejection)
        tampered = result.to_dict()
        self.assertEqual("Ready", tampered["gate"])
        tampered["gate"] = "Needs review"
        tampered["resolution_hash"] = compute_resolution_hash(tampered)

        self.assertEqual(
            [
                "Needs review decisions must use ACCEPTANCE_EVIDENCE_INCOMPLETE",
                "Needs review decisions must require review evidence",
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
            "sha256:8489f951e3b1cb41b63d7673aeb18a56bd5b16b2d45fa976275f8c16205526ee",
            first.resolution_hash,
        )
        self.assertEqual(request_before, request)
        self.assertEqual(procedures_before, procedures)
        self.assertEqual(canonical_resolution_bytes(first_payload), first.hashed_bytes)
        self.assertEqual([], validate_resolution(first_payload))
        self.assertEqual("Verify", first_payload["phase"])
        self.assertEqual("verify-evidence", first_payload["primary_procedure"])
        self.assertIsNone(first_payload["primary_blocker"])
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
            "sha256:2dcd3f4b60449f41a0f2a4e19d4e63be02f4beaa1608bc86520a7bfb27718c88",
            first.resolution_hash,
        )
        self.assertEqual([], validate_resolution(payload))
        self.assertEqual("Blocked", payload["gate"])
        self.assertFalse(payload["allowed"])
        self.assertEqual("SKILL_UNAVAILABLE", payload["reason_code"])
        self.assertIsNone(payload["primary_procedure"])
        self.assertEqual(
            {
                "identity": "verify-evidence",
                "reason_code": "SKILL_UNAVAILABLE",
            },
            payload["primary_blocker"],
        )
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

    def test_complete_primary_subject_matrix_covers_goldens_and_blocked(self) -> None:
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        requests = [
            load_json(
                ROOT
                / "tests/fixtures/resolver/golden"
                / ("pr.json" if phase == "PR" else f"{phase.lower()}.json")
            )
            for phase in GOLDEN_PHASES
        ]
        requests.append(
            load_json(ROOT / "tests/fixtures/resolver/red/unavailable-skill.json")
        )

        self.assertEqual(10, len(requests))
        for request in requests:
            with self.subTest(task_id=request["task_id"]):
                result = resolve(request, procedures)
                self.assertNotIsInstance(result, ResolutionRejection)
                payload = result.to_dict()

                self.assertEqual("4.0.0", payload["schema_version"])
                self.assertEqual([], validate_resolution(payload))
                self.assertTrue(payload["rationale"]["principle_ids"])
                self.assertTrue(payload["rationale"]["summary"])
                self.assertIsInstance(payload["required_evidence"], list)
                self.assertTrue(payload["good"])
                self.assertTrue(payload["finished"])
                self.assertTrue(payload["anti_example"])
                self.assertNotEqual(
                    payload["primary_procedure"] is None,
                    payload["primary_blocker"] is None,
                )
                if payload["gate"] == "Blocked":
                    self.assertEqual(
                        {
                            "identity": request["required_procedure"]["identity"],
                            "reason_code": "SKILL_UNAVAILABLE",
                        },
                        payload["primary_blocker"],
                    )
                    self.assertIsNone(payload["primary_procedure"])
                else:
                    self.assertEqual(
                        request["required_procedure"]["identity"],
                        payload["primary_procedure"],
                    )
                    self.assertIsNone(payload["primary_blocker"])

    def test_ready_decision_has_exact_procedure_and_null_blocker(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        required_kinds = next(
            procedure["required_evidence"]
            for procedure in procedures["procedures"]
            if procedure["identity"] == request["required_procedure"]["identity"]
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

        result = resolve(request, procedures)
        self.assertNotIsInstance(result, ResolutionRejection)
        payload = result.to_dict()

        self.assertEqual([], validate_resolution(payload))
        self.assertEqual("Ready", payload["gate"])
        self.assertTrue(payload["allowed"])
        self.assertEqual(
            request["required_procedure"]["identity"],
            payload["primary_procedure"],
        )
        self.assertIsNone(payload["primary_blocker"])
        self.assertEqual([], payload["required_evidence"])
        self.assertTrue(payload["rationale"]["principle_ids"])
        self.assertTrue(payload["rationale"]["summary"])
        self.assertTrue(payload["good"])
        self.assertTrue(payload["finished"])
        self.assertTrue(payload["anti_example"])

    def test_primary_blocker_participates_in_canonical_hash(self) -> None:
        request = load_json(ROOT / "tests/fixtures/resolver/red/unavailable-skill.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        result = resolve(request, procedures)
        self.assertNotIsInstance(result, ResolutionRejection)
        baseline = result.to_dict()
        changed = copy.deepcopy(baseline)
        changed["primary_blocker"]["identity"] = "other-procedure"
        changed["resolution_hash"] = compute_resolution_hash(changed)

        self.assertNotEqual(baseline["resolution_hash"], changed["resolution_hash"])
        self.assertIn(
            "primary_blocker.identity must equal required_procedure.identity",
            validate_resolution(changed),
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
