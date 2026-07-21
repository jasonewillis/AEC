import hashlib
import json
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path

from tools.validate_blueprint_skills import (
    EXPECTED_SKILL_NAMES,
    validate_blueprint_installation,
)


ROOT = Path(__file__).resolve().parents[1]


class BlueprintSkillInstallationTests(unittest.TestCase):
    def test_repository_installation_is_exact_and_agent_agnostic(self) -> None:
        self.assertEqual([], validate_blueprint_installation(ROOT))

    def test_manifest_pins_source_and_records_permission_without_license_claim(
        self,
    ) -> None:
        manifest = json.loads(
            (ROOT / "provenance/blueprint-skills.json").read_text(encoding="utf-8")
        )

        self.assertEqual(
            "3af769db122e3c16f64bb78bcd93eb64d3e541e8",
            manifest["source"]["revision"],
        )
        self.assertIsNone(manifest["source"]["license"])
        self.assertEqual(
            "operator-attested-course-participant-permission",
            manifest["source"]["authorization"]["basis"],
        )
        self.assertEqual(
            list(EXPECTED_SKILL_NAMES),
            [skill["name"] for skill in manifest["skills"]],
        )
        self.assertEqual("1.5.19", manifest["installer"]["version"])
        self.assertEqual(
            "local-exact-revision-checkout", manifest["installer"]["method"]
        )
        self.assertEqual(
            {
                "design": "dbaea31c7d0dcc54901c86e785dad32aadd66dfa891b7db9adee28d926127baa",
                "improve": "3c884673e4300e86569c5545ac2ae97b16460ab566c02b5de85dbdb07af8ea11",
                "milestone": "2e2a1135cec50ef558dfb26a1a87170f8f1b120430578adb936fc8f6d09dc3b1",
                "plan": "56e77acf66bcd38aa6e0151eab1cc3b9e6089e6748c19081d8d11e05a28507a5",
                "review": "54b65fc112dcfe03b273dc96a97ce3b0bef4ce79467186cb2d337de7562e2f17",
                "task-to-pr": "29091f69c0791c77b1f7f1c6e2d490408909878fd915e11294eef968b2823ea0",
                "test": "3ec39ad062a195d801334a3cff5b45f77c2dbc1a08ea603bb7420aabb64e4ec7",
            },
            {skill["name"]: skill["sha256"] for skill in manifest["skills"]},
        )

    def test_modified_canonical_skill_fails_closed(self) -> None:
        with self._copy_repository() as copied_root:
            skill_path = copied_root / ".agents/skills/design/SKILL.md"
            skill_path.write_text(
                skill_path.read_text(encoding="utf-8") + "\nmodified\n",
                encoding="utf-8",
            )

            self.assertIn(
                "Blueprint skill design SHA-256 does not match the pinned manifest",
                validate_blueprint_installation(copied_root),
            )

    def test_changed_skill_and_self_consistent_manifest_still_fail_closed(self) -> None:
        with self._copy_repository() as copied_root:
            skill_path = copied_root / ".agents/skills/design/SKILL.md"
            changed_content = skill_path.read_text(encoding="utf-8") + "\nmodified\n"
            skill_path.write_text(changed_content, encoding="utf-8")
            manifest_path = copied_root / "provenance/blueprint-skills.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["skills"][0]["sha256"] = hashlib.sha256(
                changed_content.encode("utf-8")
            ).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, indent=2) + "\n",
                encoding="utf-8",
            )

            errors = validate_blueprint_installation(copied_root)

            self.assertIn(
                "Blueprint skill manifest must pin the exact seven skill records",
                errors,
            )
            self.assertIn(
                "Blueprint skill design SHA-256 does not match the pinned manifest",
                errors,
            )

    def test_missing_canonical_skill_fails_closed(self) -> None:
        with self._copy_repository() as copied_root:
            shutil.rmtree(copied_root / ".agents/skills/design")

            self.assertIn(
                "Blueprint canonical skill design is missing",
                validate_blueprint_installation(copied_root),
            )

    def test_unpinned_extra_skill_cannot_create_duplicate_discovery(self) -> None:
        with self._copy_repository() as copied_root:
            extra_skill = copied_root / ".agents/skills/duplicate"
            extra_skill.mkdir()
            (extra_skill / "SKILL.md").write_text(
                "---\nname: duplicate\ndescription: duplicate\n---\n",
                encoding="utf-8",
            )

            self.assertIn(
                "canonical skill root must contain the exact seven Blueprint skills",
                validate_blueprint_installation(copied_root),
            )

    def test_claude_copy_cannot_diverge_from_codex_canonical_source(self) -> None:
        with self._copy_repository() as copied_root:
            claude_skill = copied_root / ".claude/skills/design"
            claude_skill.unlink()
            claude_skill.mkdir()
            (claude_skill / "SKILL.md").write_text(
                (copied_root / ".agents/skills/design/SKILL.md").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )

            self.assertIn(
                "Claude skill design must be a symlink to the canonical skill",
                validate_blueprint_installation(copied_root),
            )

    def test_canonical_skill_directory_cannot_escape_the_repository(self) -> None:
        with self._copy_repository() as copied_root:
            canonical_skill = copied_root / ".agents/skills/design"
            shutil.rmtree(canonical_skill)
            canonical_skill.symlink_to("../../../outside")

            self.assertIn(
                "Blueprint canonical skill design directory must not be a symlink",
                validate_blueprint_installation(copied_root),
            )

    def test_claude_symlink_cannot_escape_the_canonical_root(self) -> None:
        with self._copy_repository() as copied_root:
            claude_skill = copied_root / ".claude/skills/design"
            claude_skill.unlink()
            claude_skill.symlink_to("../../../outside")

            self.assertIn(
                "Claude skill design must target ../../.agents/skills/design",
                validate_blueprint_installation(copied_root),
            )

    def test_blueprint_license_cannot_be_invented(self) -> None:
        with self._copy_repository() as copied_root:
            lock_path = copied_root / "provenance/upstream-lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            blueprint = next(
                item for item in lock["upstreams"] if item["name"] == "blueprint"
            )
            blueprint["license"] = "MIT"
            lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")

            self.assertIn(
                "Blueprint license must remain null unless independently verified",
                validate_blueprint_installation(copied_root),
            )

    def test_aec_mit_license_must_exclude_the_blueprint_files(self) -> None:
        with self._copy_repository() as copied_root:
            (copied_root / "THIRD_PARTY_NOTICES.md").unlink()

            self.assertIn(
                "third-party notice must preserve the Blueprint license boundary",
                validate_blueprint_installation(copied_root),
            )

    @contextmanager
    def _copy_repository(self) -> Iterator[Path]:
        with tempfile.TemporaryDirectory() as temporary_directory:
            copied_root = Path(temporary_directory) / "repository"
            shutil.copytree(ROOT, copied_root, symlinks=True)
            yield copied_root


if __name__ == "__main__":
    unittest.main()
