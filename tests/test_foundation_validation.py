import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from aec.contracts import PROJECT_PROFILE_FIELDS
from aec.resolver import (
    PROCEDURE_FIELDS,
    REQUIRED_CATALOG_FIELDS,
    REQUIRED_REQUEST_FIELDS,
    validate_procedure_catalog,
    validate_resolution_request,
)
from tools.validate_foundation import (
    REQUIRED_RESOLUTION_FIELDS,
    SUPPORTED_REASON_CODES,
    compute_resolution_hash,
    validate_course_inventory,
    validate_principle_registry,
    validate_project_profile,
    validate_procedure_principles,
    validate_provenance,
    validate_resolution,
    validate_runtime_authority,
    validate_workflow,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


class ResolutionValidationTests(unittest.TestCase):
    def test_valid_resolution_has_stable_hash_and_no_errors(self) -> None:
        resolution = load_json(FIXTURES / "resolution.valid.json")

        self.assertEqual([], validate_resolution(resolution))
        self.assertEqual(resolution["resolution_hash"], compute_resolution_hash(resolution))

    def test_wrong_hash_fails_closed(self) -> None:
        resolution = load_json(FIXTURES / "resolution.wrong-hash.json")

        self.assertEqual(
            ["resolution_hash does not match canonical payload"],
            validate_resolution(resolution),
        )

    def test_aec_execution_and_mutation_are_rejected(self) -> None:
        resolution = load_json(FIXTURES / "resolution.mutating-aec.json")

        errors = validate_resolution(resolution)

        self.assertEqual(
            [
                "AEC decisions must set executes=false",
                "AEC decisions must set mutates=false",
            ],
            errors,
        )

    def test_hash_changes_when_revision_changes(self) -> None:
        resolution = load_json(FIXTURES / "resolution.valid.json")
        changed = copy.deepcopy(resolution)
        changed["revision"] = "fedcba9876543210fedcba9876543210fedcba98"

        self.assertNotEqual(
            compute_resolution_hash(resolution),
            compute_resolution_hash(changed),
        )


class SourceContractTests(unittest.TestCase):
    def test_request_schema_and_validator_reject_stage_phase_mismatch(self) -> None:
        schema = load_json(ROOT / "schemas" / "resolution-request.schema.json")
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        request["workflow"]["stage"] = "Design"

        self.assertIn(
            "phase does not belong to workflow.stage",
            validate_resolution_request(request),
        )
        required_stage = next(
            rule["then"]["properties"]["workflow"]["properties"]["stage"]["const"]
            for rule in schema["allOf"]
            if request["phase"] in rule["if"]["properties"]["phase"]["enum"]
        )
        self.assertNotEqual(request["workflow"]["stage"], required_stage)

    def test_request_schema_and_validator_reject_trailing_newline_in_project(
        self,
    ) -> None:
        schema = load_json(ROOT / "schemas" / "resolution-request.schema.json")
        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        request["consumer_profile"]["project"] = "owner/repository\n"

        self.assertIn(
            "consumer_profile: consumer project must use owner/repository format",
            validate_resolution_request(request),
        )
        pattern = schema["properties"]["consumer_profile"]["properties"]["project"][
            "pattern"
        ]
        self.assertIsNone(re.search(pattern, request["consumer_profile"]["project"]))

    def test_rejection_schema_matches_the_public_rejection_shape(self) -> None:
        schema = load_json(ROOT / "schemas" / "resolution-rejection.schema.json")

        self.assertFalse(schema["additionalProperties"])
        self.assertEqual({"accepted", "code", "errors"}, set(schema["required"]))
        self.assertFalse(schema["properties"]["accepted"]["const"])
        self.assertEqual(
            {"PROCEDURE_CATALOG_INVALID", "RESOLUTION_REQUEST_INVALID"},
            set(schema["properties"]["code"]["enum"]),
        )

    def test_catalog_schema_and_validator_share_the_structural_contract(self) -> None:
        schema = load_json(ROOT / "schemas" / "procedure-catalog.schema.json")
        fixture = load_json(ROOT / "config/procedures/ticket-to-pr.json")

        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(REQUIRED_CATALOG_FIELDS, set(schema["required"]))
        procedure_schema = schema["properties"]["procedures"]["items"]
        self.assertFalse(procedure_schema["additionalProperties"])
        self.assertEqual(PROCEDURE_FIELDS, set(procedure_schema["required"]))
        self.assertEqual(
            "ACCEPTANCE_EVIDENCE_INCOMPLETE",
            procedure_schema["properties"]["reason_code"]["const"],
        )
        self.assertEqual([], validate_procedure_catalog(fixture))

    def test_catalog_python_validator_adds_semantic_reference_uniqueness(self) -> None:
        schema = load_json(ROOT / "schemas" / "procedure-catalog.schema.json")
        catalog = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        duplicate = copy.deepcopy(catalog["procedures"][0])
        duplicate["anti_example"] = "Different text with the same pinned identity."
        catalog["procedures"].append(duplicate)

        self.assertNotEqual(catalog["procedures"][0], catalog["procedures"][1])
        self.assertTrue(schema["properties"]["procedures"]["uniqueItems"])
        self.assertIn(
            "procedure catalog references must be unique",
            validate_procedure_catalog(catalog),
        )

    def test_request_schema_validator_and_fixture_share_one_contract(self) -> None:
        schema = load_json(ROOT / "schemas" / "resolution-request.schema.json")
        fixture = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")

        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(REQUIRED_REQUEST_FIELDS, set(schema["required"]))
        consumer_schema = schema["properties"]["consumer_profile"]
        self.assertFalse(consumer_schema["additionalProperties"])
        self.assertEqual(PROJECT_PROFILE_FIELDS, set(consumer_schema["required"]))
        self.assertEqual([], validate_resolution_request(fixture))

    def test_schema_and_validator_require_the_same_resolution_fields(self) -> None:
        schema = load_json(ROOT / "schemas" / "resolution-decision.schema.json")

        self.assertEqual(REQUIRED_RESOLUTION_FIELDS, set(schema["required"]))
        self.assertEqual(
            SUPPORTED_REASON_CODES,
            set(schema["properties"]["reason_code"]["enum"]),
        )

    def test_course_inventory_has_complete_source_coverage(self) -> None:
        guidance = load_json(ROOT / "provenance" / "course-inventory.json")

        self.assertEqual([], validate_course_inventory(guidance))

    def test_course_inventory_rejects_expressive_content(self) -> None:
        guidance = load_json(
            FIXTURES / "course-boundary/course-inventory-expressive.json"
        )

        self.assertIn(
            "course inventory contains forbidden expressive field: principle",
            validate_course_inventory(guidance),
        )

    def test_course_inventory_rejects_disguised_expressive_content(self) -> None:
        inventory = load_json(ROOT / "provenance" / "course-inventory.json")
        inventory["source_sets"][0]["lessons"][0]["description"] = (
            "Synthetic expressive content."
        )

        self.assertIn(
            "course inventory contains forbidden expressive field: description",
            validate_course_inventory(inventory),
        )

    def test_ai_engineer_inventory_has_exact_lesson_hashes(self) -> None:
        inventory = load_json(ROOT / "provenance" / "course-inventory.json")
        ai_engineer = next(
            item for item in inventory["source_sets"] if item["id"] == "ai-engineer"
        )

        self.assertEqual(
            [
                "cedad90972f6dff876b5549964bccaa4f5036d2a3c164eca41fc2d5c01e8bb64",
                "fa9eee23f8396ea6452850c4c7379816128c5aea85321c094aeffac17d31543a",
                "ea3ece74e598476330b758c06bce300d41361c879f52cd0735cc2da7387ad515",
                "3fca81dc82eb2c93125dd259c9b25ce346b0f5e9b87a9c1c62b10fa3667703c6",
                "36cb20c37f4f51f82294de68deacc9aec94ec403e66230da394f49b098a39b47",
                "840fc9fa2a946cad8692ad6309a7cce299031faab3f948c6867d7a997c92eda6",
                "29bcf2e81764aafb02b773791f3550ee0f7a8d3b7058851c43fea73c0848c748",
                "0df87b9138090380163a9379a89498963005700fbc5c75e8f2e296b0907524ec",
                "eaefc642913ee7234b3f99765f54d8cdae76749d9bcbfa6c807a0d689a5d1e05",
                "58bd76df8c2cc7a6dc0cd0232c761a3420f880d16448dc9108b7e610d8048391",
                "ca2d968a390c8682eee559fc86a21a0e7897c3addcbde0a95da5b29257f72ba7",
                "9837b27ce179b6a123b7fe26a0a565e311c65a1e30c3c5201777618ff3921218",
                "9e09e88233d2502b3fd233a11bad47d14ac5bb685b75fca723d64a9dd856a594",
            ],
            [lesson["sha256"] for lesson in ai_engineer["lessons"]],
        )
        self.assertEqual(
            [
                "The Shift To Agentic Engineering",
                "How Coding Agents Work",
                "The Agent Development Workflow",
                "Choose Your Agent",
                "Project Foundations",
                "Agent Skills",
                "Spec-Driven Development",
                "Task Management",
                "Testing Agent Work",
                "Reviewing Agent Work",
                "Deploy With Agents",
                "Scaling Your Impact",
                "BONUS: Agent Loops And Goals",
            ],
            [lesson["title"] for lesson in ai_engineer["lessons"]],
        )
        self.assertEqual(
            "9ec5e796ad9ee48e8b46e030f2bbf0cafacc8b7c987950b43bc1acc6c2bd4144",
            ai_engineer["supplemental"][0]["sha256"],
        )
        self.assertEqual(
            {
                "id": "ai-engineer-gateway",
                "source_file": "2a. coding-agents-and-the-gateway.md.pdf",
                "title": "Coding Agents And The Gateway",
            },
            {
                key: ai_engineer["supplemental"][0][key]
                for key in ("id", "source_file", "title")
            },
        )
        self.assertEqual(13, len(ai_engineer["lessons"]))
        self.assertEqual(1, len(ai_engineer["supplemental"]))

    def test_course_inventory_schema_allows_only_factual_metadata(self) -> None:
        schema = load_json(ROOT / "schemas/course-inventory.schema.json")

        self.assertFalse(schema["additionalProperties"])
        self.assertEqual({"schema_version", "source_sets"}, set(schema["required"]))
        source_set = schema["properties"]["source_sets"]["items"]
        self.assertFalse(source_set["additionalProperties"])
        self.assertEqual(
            {
                "id",
                "lessons",
                "relationship",
                "supplemental",
                "title",
                "visibility",
            },
            set(source_set["required"]),
        )
        record = source_set["properties"]["lessons"]["items"]
        self.assertFalse(record["additionalProperties"])
        self.assertEqual(
            {"id", "sha256", "source_file", "title"},
            set(record["required"]),
        )

    def test_missing_course_lesson_is_rejected(self) -> None:
        guidance = load_json(ROOT / "provenance" / "course-inventory.json")
        broken = copy.deepcopy(guidance)
        broken["source_sets"][0]["lessons"].pop()

        self.assertIn(
            "AI Engineer coverage must be exactly 13 lessons",
            validate_course_inventory(broken),
        )

    def test_course_inventory_requires_honest_missing_hashes(self) -> None:
        guidance = load_json(ROOT / "provenance" / "course-inventory.json")
        mutations = {
            "id": "unrelated-id",
            "title": "Synthetic operational summary",
            "source_file": "invented-source.rtf",
            "sha256": "a" * 64,
        }

        for field, value in mutations.items():
            with self.subTest(field=field):
                broken = copy.deepcopy(guidance)
                broken["source_sets"][1]["lessons"][0][field] = value

                self.assertIn(
                    "course inventory factual manifest must match the verified record",
                    validate_course_inventory(broken),
                )

    def test_course_inventory_binds_every_factual_manifest_field(self) -> None:
        inventory = load_json(ROOT / "provenance" / "course-inventory.json")
        mutations = []

        broken = copy.deepcopy(inventory)
        broken["source_sets"][0]["lessons"][0]["source_file"] = (
            "Synthetic operational guidance.rtf"
        )
        mutations.append(broken)

        broken = copy.deepcopy(inventory)
        broken["source_sets"][0]["title"] = "A derived operational summary"
        mutations.append(broken)

        broken = copy.deepcopy(inventory)
        broken["source_sets"][1]["title"] = "A derived operational summary"
        mutations.append(broken)

        broken = copy.deepcopy(inventory)
        broken["source_sets"][1]["supplemental"].append(
            {
                "id": "evals-monitoring-derived",
                "sha256": None,
                "source_file": None,
                "title": "A derived operational summary",
            }
        )
        mutations.append(broken)

        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index):
                self.assertIn(
                    "course inventory factual manifest must match the verified record",
                    validate_course_inventory(mutation),
                )

    def test_procedure_cannot_use_course_identity_as_runtime_authority(self) -> None:
        catalog = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        verify_procedure = next(
            procedure
            for procedure in catalog["procedures"]
            if procedure["identity"] == "verify-evidence"
        )
        verify_procedure["rationale"]["principle_ids"] = ["ai-engineer-09"]
        principle_registry = load_json(
            ROOT / "config/principles/aec-engineering.json"
        )

        self.assertIn(
            "procedure verify-evidence references non-AEC principle ai-engineer-09",
            validate_procedure_principles(
                catalog,
                principle_registry,
            ),
        )

    def test_procedure_uses_only_registered_aec_principles(self) -> None:
        catalog = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        registry = load_json(ROOT / "config/principles/aec-engineering.json")

        self.assertEqual(
            [],
            validate_principle_registry(registry),
        )
        self.assertEqual(
            [],
            validate_procedure_principles(catalog, registry),
        )

    def test_principle_registry_schema_is_closed_and_factual(self) -> None:
        schema = load_json(ROOT / "schemas/principle-registry.schema.json")

        self.assertFalse(schema["additionalProperties"])
        self.assertEqual({"principles", "schema_version"}, set(schema["required"]))
        principle_schema = schema["properties"]["principles"]["items"]
        self.assertFalse(principle_schema["additionalProperties"])
        self.assertEqual(
            {"id", "revision", "statement"},
            set(principle_schema["required"]),
        )

    def test_principle_registry_validator_enforces_schema_identity_pattern(self) -> None:
        registry = load_json(ROOT / "config/principles/aec-engineering.json")

        for identity in ("aec-", "aec-INVALID", "aec-with space"):
            with self.subTest(identity=identity):
                broken = copy.deepcopy(registry)
                broken["principles"][0]["id"] = identity

                self.assertIn(
                    "AEC principle id must match ^aec-[a-z0-9-]+$",
                    validate_principle_registry(broken),
                )

    def test_aec_principle_cannot_launder_private_course_identity(self) -> None:
        registry = load_json(ROOT / "config/principles/aec-engineering.json")
        catalog = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        laundered_identity = "aec-ai-engineer-09"
        registry["principles"][0]["id"] = laundered_identity
        registry["principles"][0]["revision"] = f"{laundered_identity}:1.0.0"
        catalog["procedures"][0]["rationale"]["principle_ids"] = [
            laundered_identity
        ]

        expected = "AEC principle id must not embed a private course identity"
        self.assertIn(expected, validate_principle_registry(registry))
        self.assertIn(expected, validate_procedure_principles(catalog, registry))

        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture = Path(temporary_directory) / "runtime-laundered.json"
            fixture.write_text(json.dumps(catalog), encoding="utf-8")

            self.assertTrue(validate_runtime_authority([fixture]))

    def test_neutral_ai_engineering_identity_is_not_a_course_reference(self) -> None:
        registry = load_json(ROOT / "config/principles/aec-engineering.json")
        catalog = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        neutral_identity = "aec-ai-engineering-practice"
        registry["principles"][0]["id"] = neutral_identity
        registry["principles"][0]["revision"] = f"{neutral_identity}:1.0.0"
        catalog["procedures"][0]["rationale"]["principle_ids"] = [neutral_identity]

        self.assertEqual([], validate_principle_registry(registry))
        self.assertEqual([], validate_procedure_principles(catalog, registry))

        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture = Path(temporary_directory) / "runtime-neutral.json"
            fixture.write_text(json.dumps(catalog), encoding="utf-8")

            self.assertEqual([], validate_runtime_authority([fixture]))

    def test_runtime_authority_scan_rejects_course_identity(self) -> None:
        fixture = FIXTURES / "course-boundary/runtime-authority-course-id.json"

        self.assertEqual(
            [
                "runtime authority references private course identity in "
                "tests/fixtures/course-boundary/runtime-authority-course-id.json"
            ],
            validate_runtime_authority([fixture]),
        )

    def test_runtime_authority_scan_rejects_every_private_identity_class(self) -> None:
        identities = (
            "ai-engineer",
            "ai-engineer-gateway",
            "ai-engineer-09",
            "aia-week-5-evals-monitoring",
            "evals-monitoring-01",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            for index, identity in enumerate(identities):
                with self.subTest(identity=identity):
                    fixture = Path(temporary_directory) / f"runtime-{index}.json"
                    fixture.write_text(
                        json.dumps({"principle_ids": [identity]}),
                        encoding="utf-8",
                    )

                    self.assertTrue(validate_runtime_authority([fixture]))

    def test_runtime_authority_scan_decodes_json_before_inspection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture = Path(temporary_directory) / "runtime-escaped.json"
            fixture.write_text(
                '{"principle_ids":["ai\\u002dengineer\\u002d09"]}',
                encoding="utf-8",
            )

            self.assertTrue(validate_runtime_authority([fixture]))

    def test_runtime_authority_scan_fails_closed_on_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            fixture = Path(temporary_directory) / "runtime-invalid.json"
            fixture.write_text("{not-json", encoding="utf-8")

            self.assertEqual(
                [f"runtime authority file is not valid JSON: {fixture}"],
                validate_runtime_authority([fixture]),
            )

    def test_support_docs_state_no_adoption_without_safe_harbor(self) -> None:
        provenance = (ROOT / "docs/provenance.md").read_text(encoding="utf-8")
        traceability = (ROOT / "docs/course-traceability/README.md").read_text(
            encoding="utf-8"
        )
        combined = provenance + traceability
        normalized_traceability = " ".join(traceability.split())

        self.assertNotIn("original operational summaries", combined)
        self.assertNotIn("materials inform original operating principles", combined)
        self.assertIn(
            "Private storage does not make those forms safe to adopt.",
            normalized_traceability,
        )

    def test_blueprint_adoption_mode_is_rejected_without_license(self) -> None:
        provenance = load_json(ROOT / "provenance" / "upstream-lock.json")
        broken = copy.deepcopy(provenance)
        blueprint = next(item for item in broken["upstreams"] if item["name"] == "blueprint")
        blueprint["relationship"] = "adopted"

        self.assertIn(
            "Blueprint must remain reference-only without a verified adoption license",
            validate_provenance(broken),
        )

    def test_pinned_provenance_is_valid(self) -> None:
        provenance = load_json(ROOT / "provenance" / "upstream-lock.json")

        self.assertEqual([], validate_provenance(provenance))

    def test_duplicate_upstream_is_rejected(self) -> None:
        provenance = load_json(ROOT / "provenance" / "upstream-lock.json")
        broken = copy.deepcopy(provenance)
        broken["upstreams"].append(copy.deepcopy(broken["upstreams"][0]))

        self.assertIn("upstream names must be unique", validate_provenance(broken))

    def test_invalid_gate_and_reason_code_are_rejected(self) -> None:
        resolution = load_json(FIXTURES / "resolution.valid.json")
        broken = copy.deepcopy(resolution)
        broken["gate"] = "Looks good"
        broken["reason_code"] = "free form"

        errors = validate_resolution(broken)

        self.assertIn("gate is unsupported", errors)
        self.assertIn("reason_code must be uppercase snake case", errors)


class RegistryContractTests(unittest.TestCase):
    def test_ticket_to_pr_workflow_is_valid(self) -> None:
        workflow = load_json(ROOT / "config" / "workflows" / "ticket-to-pr.json")

        self.assertEqual([], validate_workflow(workflow))

    def test_skipped_workflow_phase_is_rejected(self) -> None:
        workflow = load_json(ROOT / "config" / "workflows" / "ticket-to-pr.json")
        broken = copy.deepcopy(workflow)
        broken["stages"][2]["phases"].remove("Verify")

        self.assertIn(
            "workflow phases must preserve the canonical nine-phase order",
            validate_workflow(broken),
        )

    def test_generic_consumer_profile_shape_validates(self) -> None:
        profile = {
            "aec_mode": "read-only-mentor",
            "agent_adapters": ["some-adapter"],
            "lifecycle_authority": "consumer-owned",
            "project": "example-owner/example-repo",
            "profile_version": "example:0.1.0",
            "schema_version": "1.0.0",
            "workflow": "ticket-to-pr",
        }

        self.assertEqual([], validate_project_profile(profile))

    def test_consumer_profile_cannot_claim_aec_as_lifecycle_writer(self) -> None:
        profile = {
            "aec_mode": "read-only-mentor",
            "agent_adapters": ["some-adapter"],
            "lifecycle_authority": "aec",
            "project": "example-owner/example-repo",
            "profile_version": "example:0.1.0",
            "schema_version": "1.0.0",
            "workflow": "ticket-to-pr",
        }

        self.assertIn(
            "consumer must own lifecycle authority",
            validate_project_profile(profile),
        )

    def test_agent_adapters_rejects_whitespace_only(self) -> None:
        profile = {
            "aec_mode": "read-only-mentor",
            "agent_adapters": ["   "],
            "lifecycle_authority": "consumer-owned",
            "project": "example-owner/example-repo",
            "profile_version": "example:0.1.0",
            "schema_version": "1.0.0",
            "workflow": "ticket-to-pr",
        }

        self.assertIn(
            "agent_adapters must be a non-empty list of non-whitespace strings",
            validate_project_profile(profile),
        )


if __name__ == "__main__":
    unittest.main()
