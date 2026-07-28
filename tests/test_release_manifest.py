"""Contract tests for immutable AEC release metadata and publication."""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from aec._generated.resolver_program import RESOLVER_PROGRAM
from aec.cards import PUBLIC_CARD_SCHEMA_VERSION
from aec.human_render import HUMAN_RENDER_CONTRACT_VERSION
from aec.release_manifest import (
    CONTRACT_VERSIONS,
    CURRENT_RELEASE_VERSION,
    OFFICIAL_REPOSITORY,
    RELEASE_MANIFEST_SCHEMA_VERSION,
    ReleaseManifestFailure,
    build_release_manifest,
    canonical_json,
    classify_release_lookup,
    validate_release_descriptor,
    validate_release_manifest,
    validate_publication_preflight,
)


ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR_PATH = ROOT / "config" / "release" / "aec-release.json"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "publish-release.yml"
SCHEMA_PATH = ROOT / "schemas" / "release-manifest.schema.json"
FETCH_FAILURE_PATH = (
    ROOT
    / "tests"
    / "fixtures"
    / "release"
    / "run-30404752936-fetch-failure.json"
)


def descriptor() -> dict[str, object]:
    return {
        "channel": "beta",
        "compatibility": "validation-required",
        "contracts": dict(CONTRACT_VERSIONS),
        "release_notes": "docs/releases/v0.1.0.md",
        "release_version": "0.1.0",
        "repository": OFFICIAL_REPOSITORY,
        "schema_version": "1.0.0",
    }


class ReleaseDescriptorTests(unittest.TestCase):
    def test_tracked_descriptor_is_closed_and_current(self) -> None:
        tracked = json.loads(DESCRIPTOR_PATH.read_text(encoding="utf-8"))

        self.assertEqual([], validate_release_descriptor(tracked))
        self.assertEqual(descriptor(), tracked)

    def test_unknown_field_and_malformed_version_fail_closed(self) -> None:
        unknown = descriptor()
        unknown["revision"] = "a" * 40
        malformed = descriptor()
        malformed["release_version"] = "main"

        self.assertIn("fields do not match", validate_release_descriptor(unknown)[0])
        self.assertIn(
            "release_version must be semantic", validate_release_descriptor(malformed)[0]
        )

    def test_repository_and_each_declared_contract_fail_closed_on_drift(self) -> None:
        wrong_repository = descriptor()
        wrong_repository["repository"] = "fork/AEC"
        self.assertTrue(
            any(
                "repository must equal" in error
                for error in validate_release_descriptor(wrong_repository)
            )
        )

        for contract in CONTRACT_VERSIONS:
            with self.subTest(contract=contract):
                drifted = descriptor()
                drifted["contracts"] = dict(CONTRACT_VERSIONS)
                drifted["contracts"][contract] = "99.0.0"
                self.assertIn(
                    "contracts do not match this AEC release implementation",
                    validate_release_descriptor(drifted),
                )


class ReleaseManifestTests(unittest.TestCase):
    def test_schema_and_runtime_define_the_same_closed_contract(self) -> None:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        consumer_state_schema = json.loads(
            (ROOT / "schemas/consumer-state.schema.json").read_text(encoding="utf-8")
        )
        request_schema = json.loads(
            (ROOT / "schemas/resolution-request.schema.json").read_text(encoding="utf-8")
        )
        workflow = json.loads(
            (ROOT / "config/workflows/ticket-to-pr.json").read_text(encoding="utf-8")
        )
        authoritative = {
            "consumer_state": consumer_state_schema["properties"]["schema_version"][
                "const"
            ],
            "human_render": HUMAN_RENDER_CONTRACT_VERSION,
            "public_card": PUBLIC_CARD_SCHEMA_VERSION,
            "resolution_decision": RESOLVER_PROGRAM["decision_schema_version"],
            "resolution_request": request_schema["properties"]["schema_version"][
                "const"
            ],
            "workflow": workflow["schema_version"],
        }

        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(authoritative, descriptor()["contracts"])
        self.assertEqual(authoritative, CONTRACT_VERSIONS)
        self.assertEqual(
            RELEASE_MANIFEST_SCHEMA_VERSION,
            schema["properties"]["schema_version"]["const"],
        )
        self.assertEqual(
            HUMAN_RENDER_CONTRACT_VERSION,
            schema["properties"]["contracts"]["properties"]["human_render"]["const"],
        )
        self.assertEqual(
            PUBLIC_CARD_SCHEMA_VERSION,
            schema["properties"]["contracts"]["properties"]["public_card"]["const"],
        )
        self.assertEqual(
            sorted(schema["required"]),
            sorted(schema["properties"]),
        )
        self.assertEqual(
            authoritative,
            {
                name: row["const"]
                for name, row in schema["properties"]["contracts"][
                    "properties"
                ].items()
            },
        )
        release_schema = schema["properties"]["release"]["properties"]
        self.assertEqual("0.1.0", release_schema["version"]["const"])
        self.assertEqual(CURRENT_RELEASE_VERSION, release_schema["version"]["const"])
        self.assertEqual("v0.1.0", release_schema["tag"]["const"])
        self.assertEqual(
            "https://github.com/jasonewillis/AEC/releases/tag/v0.1.0",
            release_schema["notes_url"]["const"],
        )
        timestamp_pattern = re.compile(release_schema["published_at"]["pattern"])
        self.assertIsNotNone(
            timestamp_pattern.fullmatch("2026-07-26T20:00:00Z")
        )
        for malformed in (
            "2026-07-26",
            "2026-07-26T20:00:00+00:00",
            "2026-13-26T20:00:00Z",
            "2026-07-26T25:00:00Z",
        ):
            self.assertIsNone(timestamp_pattern.fullmatch(malformed))

    def test_builds_exact_tag_revision_and_contract_manifest(self) -> None:
        revision = "a" * 40

        manifest = build_release_manifest(
            descriptor(),
            repository="jasonewillis/AEC",
            revision=revision,
            tag="v0.1.0",
            published_at="2026-07-26T20:00:00Z",
        )

        self.assertEqual([], validate_release_manifest(manifest))
        self.assertEqual(RELEASE_MANIFEST_SCHEMA_VERSION, manifest["schema_version"])
        self.assertEqual(revision, manifest["release"]["revision"])
        self.assertEqual("v0.1.0", manifest["release"]["tag"])
        self.assertEqual(
            PUBLIC_CARD_SCHEMA_VERSION, manifest["contracts"]["public_card"]
        )
        self.assertEqual(
            HUMAN_RENDER_CONTRACT_VERSION,
            manifest["contracts"]["human_render"],
        )
        self.assertEqual(
            {
                "auto_merge_allowed": False,
                "compatibility": "validation-required",
                "required_probes": ["human-render", "material", "routine"],
            },
            manifest["consumer_update"],
        )
        self.assertEqual(
            "https://github.com/jasonewillis/AEC/releases/tag/v0.1.0",
            manifest["release"]["notes_url"],
        )
        self.assertEqual(canonical_json(manifest), canonical_json(manifest))

    def test_tag_revision_time_repository_and_tamper_fail_closed(self) -> None:
        cases = (
            {"tag": "v0.2.0"},
            {"revision": "main"},
            {"published_at": "2026-07-26"},
            {"repository": "fork/AEC"},
        )
        for replacement in cases:
            with self.subTest(replacement=replacement):
                arguments = {
                    "repository": "jasonewillis/AEC",
                    "revision": "b" * 40,
                    "tag": "v0.1.0",
                    "published_at": "2026-07-26T20:00:00Z",
                    **replacement,
                }
                with self.assertRaises(ReleaseManifestFailure):
                    build_release_manifest(descriptor(), **arguments)

        manifest = build_release_manifest(
            descriptor(),
            repository="jasonewillis/AEC",
            revision="b" * 40,
            tag="v0.1.0",
            published_at="2026-07-26T20:00:00Z",
        )
        tampered = copy.deepcopy(manifest)
        tampered["consumer_update"]["auto_merge_allowed"] = True
        self.assertIn("auto_merge_allowed must be false", validate_release_manifest(tampered))

    def test_runtime_rejects_every_schema_identity_and_timestamp_mismatch(self) -> None:
        baseline = build_release_manifest(
            descriptor(),
            repository=OFFICIAL_REPOSITORY,
            revision="d" * 40,
            tag="v0.1.0",
            published_at="2026-07-26T20:00:00Z",
        )
        for timestamp in (
            "2026-07-26T20:00Z",
            "2026-07-26 20:00:00Z",
            "20260726T200000Z",
            "2026-07-26T20:00:00.123Z",
        ):
            with self.subTest(timestamp=timestamp):
                candidate = copy.deepcopy(baseline)
                candidate["release"]["published_at"] = timestamp
                self.assertTrue(validate_release_manifest(candidate))

        changed_identity = copy.deepcopy(baseline)
        changed_identity["release"].update(
            {
                "notes_url": "https://github.com/jasonewillis/AEC/releases/tag/v0.2.0",
                "tag": "v0.2.0",
                "version": "0.2.0",
            }
        )
        self.assertIn(
            "release.version must equal 0.1.0",
            validate_release_manifest(changed_identity),
        )

    def test_cli_generates_and_validates_one_canonical_asset(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "aec-release-manifest.json"
            generated = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "release_manifest.py"),
                    "generate",
                    "--descriptor",
                    str(DESCRIPTOR_PATH),
                    "--repository",
                    "jasonewillis/AEC",
                    "--revision",
                    "c" * 40,
                    "--tag",
                    "v0.1.0",
                    "--published-at",
                    "2026-07-26T20:00:00Z",
                    "--output",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )
            validated = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools" / "release_manifest.py"),
                    "validate",
                    str(output),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
            )

        self.assertEqual(0, generated.returncode, generated.stderr)
        self.assertEqual(0, validated.returncode, validated.stderr)
        self.assertIn("PASS release manifest", validated.stdout)


class ReleaseWorkflowTests(unittest.TestCase):
    def test_failed_run_fixture_reproduces_forbidden_credentialless_fetch(self) -> None:
        failure = json.loads(FETCH_FAILURE_PATH.read_text(encoding="utf-8"))
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertEqual(
            {
                "checkout",
                "command",
                "exit_code",
                "run_id",
                "schema_version",
                "stderr",
                "step",
            },
            set(failure),
        )
        self.assertEqual({"persist_credentials": False}, failure["checkout"])
        self.assertEqual("git fetch origin main", failure["command"])
        self.assertEqual(128, failure["exit_code"])
        self.assertEqual(30404752936, failure["run_id"])
        self.assertEqual(
            "fatal: could not read Username for 'https://github.com': "
            "No such device or address",
            failure["stderr"],
        )
        self.assertNotIn(failure["command"], workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertIn("tools/release_api_evidence.py", workflow)

    def test_release_lookup_adapter_distinguishes_missing_from_failures(self) -> None:
        self.assertEqual(
            "missing",
            classify_release_lookup(
                1,
                "",
                "gh: Not Found (HTTP 404)\n",
            ),
        )
        self.assertEqual(
            "draft",
            classify_release_lookup(0, '{"draft": true}', ""),
        )
        self.assertEqual(
            "published",
            classify_release_lookup(0, '{"draft": false}', ""),
        )
        for exit_code, response, error in (
            (1, "", "gh: authentication failed (HTTP 401)\n"),
            (1, "", "network timeout\n"),
            (0, "not-json", ""),
            (0, '{"draft": "false"}', ""),
        ):
            with self.subTest(error=error, response=response):
                with self.assertRaises(ReleaseManifestFailure):
                    classify_release_lookup(exit_code, response, error)

    def test_publication_preflight_has_red_canaries_for_every_gate(self) -> None:
        facts = {
            "repository": OFFICIAL_REPOSITORY,
            "revision": "a" * 40,
            "tag": "v0.1.0",
            "main_contains_revision": True,
            "immutable_releases_enabled": True,
            "existing_release_state": "missing",
            "token_available": True,
        }
        self.assertEqual([], validate_publication_preflight(descriptor(), **facts))

        red_cases = (
            ("main_contains_revision", False, "ancestor of main"),
            ("immutable_releases_enabled", False, "immutability must be enabled"),
            ("existing_release_state", "published", "published release already exists"),
            ("tag", "v0.2.0", "tag must equal"),
            ("revision", "main", "40-character Git commit"),
            ("token_available", False, "AEC_RELEASE_TOKEN is required"),
        )
        for field, value, expected in red_cases:
            with self.subTest(field=field):
                candidate = dict(facts)
                candidate[field] = value
                self.assertTrue(
                    any(
                        expected in error
                        for error in validate_publication_preflight(
                            descriptor(), **candidate
                        )
                    )
                )

    def test_publication_is_tagged_serial_verified_and_never_touches_consumers(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("tags:", workflow)
        self.assertIn("- \"v*\"", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("release_tag:", workflow)
        self.assertIn("expected_revision:", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("secrets.AEC_RELEASE_TOKEN", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotIn("git fetch", workflow)
        self.assertNotIn("git merge-base", workflow)
        self.assertIn("tools/release_api_evidence.py", workflow)
        self.assertGreaterEqual(workflow.count("tools/release_api_evidence.py"), 2)
        self.assertIn('ref: ${{ steps.release-inputs.outputs.revision }}', workflow)
        self.assertIn("path: release-candidate", workflow)
        self.assertIn("working-directory: release-candidate", workflow)
        self.assertIn("python3 tools/validate_foundation.py", workflow)
        self.assertIn("python3 -m unittest discover -s tests -v", workflow)
        self.assertIn("python3 tools/release_manifest.py generate", workflow)
        self.assertIn("release_manifest.py preflight", workflow)
        self.assertIn("--immutable-releases-enabled true", workflow)
        self.assertIn("--main-contains-revision true", workflow)
        self.assertIn("--existing-release-state missing", workflow)
        self.assertIn("--token-available true", workflow)
        self.assertIn("gh release create", workflow)
        self.assertIn("--draft", workflow)
        self.assertIn("gh release upload", workflow)
        self.assertNotIn("--clobber", workflow)
        self.assertIn("--draft=false", workflow)
        self.assertIn("aec-release-manifest.json", workflow)
        self.assertIn("release-manifest.schema.json", workflow)
        self.assertNotIn(
            "aec-release-publication-evidence.json#",
            workflow,
        )
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("consumer", workflow.lower().split("jobs:", 1)[0])

    def test_publication_rechecks_tag_before_create_and_never_mutates_it(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        evidence_call = "python3 tools/release_api_evidence.py"
        publish_call = 'gh release create "$RELEASE_TAG"'

        self.assertEqual(2, workflow.count(evidence_call))
        self.assertLess(workflow.rfind(evidence_call), workflow.index(publish_call))
        self.assertNotIn("git push", workflow)
        self.assertNotIn("git tag", workflow)
        self.assertNotIn("deleteRef", workflow)
        self.assertIn("--verify-tag", workflow)


if __name__ == "__main__":
    unittest.main()
