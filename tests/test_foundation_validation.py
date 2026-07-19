import copy
import json
import unittest
from pathlib import Path

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

        self.assertIn(
            "resolution_hash does not match canonical payload",
            validate_resolution(resolution),
        )

    def test_aec_execution_and_mutation_are_rejected(self) -> None:
        resolution = load_json(FIXTURES / "resolution.mutating-aec.json")

        errors = validate_resolution(resolution)

        self.assertIn("AEC decisions must set executes=false", errors)
        self.assertIn("AEC decisions must set mutates=false", errors)

    def test_hash_changes_when_revision_changes(self) -> None:
        resolution = load_json(FIXTURES / "resolution.valid.json")
        changed = copy.deepcopy(resolution)
        changed["revision"] = "fedcba9876543210fedcba9876543210fedcba98"

        self.assertNotEqual(
            compute_resolution_hash(resolution),
            compute_resolution_hash(changed),
        )


class SourceContractTests(unittest.TestCase):
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

    def test_jwtravelscanner_profile_is_read_only_and_consumer_owned(self) -> None:
        profile = load_json(ROOT / "config" / "projects" / "jwtravelscanner.json")

        self.assertEqual([], validate_project_profile(profile))
        self.assertEqual("jasonewillis/jwTravelScanner", profile["project"])

    def test_aec_cannot_claim_consumer_lifecycle_authority(self) -> None:
        profile = load_json(ROOT / "config" / "projects" / "jwtravelscanner.json")
        broken = copy.deepcopy(profile)
        broken["lifecycle_authority"] = "aec"

        self.assertIn(
            "consumer must own lifecycle authority",
            validate_project_profile(broken),
        )


if __name__ == "__main__":
    unittest.main()
