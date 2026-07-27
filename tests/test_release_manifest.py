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
    OFFICIAL_REPOSITORY,
    RELEASE_MANIFEST_SCHEMA_VERSION,
    ReleaseManifestFailure,
    build_release_manifest,
    canonical_json,
    validate_release_descriptor,
    validate_release_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR_PATH = ROOT / "config" / "release" / "aec-release.json"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "publish-release.yml"
SCHEMA_PATH = ROOT / "schemas" / "release-manifest.schema.json"


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
    def test_publication_is_tagged_serial_verified_and_never_touches_consumers(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("tags:", workflow)
        self.assertIn("- \"v*\"", workflow)
        self.assertIn("contents: read", workflow)
        self.assertIn("secrets.AEC_RELEASE_TOKEN", workflow)
        self.assertIn("AEC_RELEASE_TOKEN is required", workflow)
        self.assertIn("git merge-base --is-ancestor", workflow)
        self.assertIn("python3 tools/validate_foundation.py", workflow)
        self.assertIn("python3 -m unittest discover -s tests -v", workflow)
        self.assertIn("python3 tools/release_manifest.py generate", workflow)
        self.assertIn("immutable-releases", workflow)
        self.assertIn('test "$ENABLED" = "true"', workflow)
        self.assertIn("gh release create", workflow)
        self.assertIn("--draft", workflow)
        self.assertIn("gh release upload", workflow)
        self.assertIn("--clobber", workflow)
        self.assertIn("--draft=false", workflow)
        self.assertIn("aec-release-manifest.json", workflow)
        self.assertIn("release-manifest.schema.json", workflow)
        self.assertNotIn("pull_request_target", workflow)
        self.assertNotIn("consumer", workflow.lower().split("jobs:", 1)[0])


if __name__ == "__main__":
    unittest.main()
