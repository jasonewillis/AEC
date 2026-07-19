import copy
import json
import unittest
from pathlib import Path

from aec.contracts import PROJECT_PROFILE_FIELDS
from aec.resolver import REQUIRED_REQUEST_FIELDS, validate_resolution_request
from tools.validate_foundation import (
    REQUIRED_RESOLUTION_FIELDS,
    compute_resolution_hash,
    validate_course_guidance,
    validate_project_profile,
    validate_provenance,
    validate_resolution,
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
    def test_rejection_schema_matches_the_public_rejection_shape(self) -> None:
        schema = load_json(ROOT / "schemas" / "resolution-rejection.schema.json")

        self.assertFalse(schema["additionalProperties"])
        self.assertEqual({"accepted", "code", "errors"}, set(schema["required"]))
        self.assertFalse(schema["properties"]["accepted"]["const"])
        self.assertEqual(
            "RESOLUTION_REQUEST_INVALID",
            schema["properties"]["code"]["const"],
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

    def test_course_guidance_has_complete_source_coverage(self) -> None:
        guidance = load_json(ROOT / "provenance" / "course-guidance.json")

        self.assertEqual([], validate_course_guidance(guidance))

    def test_missing_course_lesson_is_rejected(self) -> None:
        guidance = load_json(ROOT / "provenance" / "course-guidance.json")
        broken = copy.deepcopy(guidance)
        broken["ai_engineer_lessons"].pop()

        self.assertIn(
            "AI Engineer coverage must be exactly 13 lessons",
            validate_course_guidance(broken),
        )

    def test_course_lesson_without_phase_coverage_is_rejected(self) -> None:
        guidance = load_json(ROOT / "provenance" / "course-guidance.json")
        broken = copy.deepcopy(guidance)
        del broken["ai_engineer_lessons"][0]["phase"]

        self.assertIn(
            "course lesson ai-engineer-01 needs phase coverage",
            validate_course_guidance(broken),
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
