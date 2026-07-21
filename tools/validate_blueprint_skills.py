#!/usr/bin/env python3
"""Validate the pinned Blueprint skill installation and agent discovery parity."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BLUEPRINT_REPOSITORY = "https://github.com/owainlewis/blueprint"
BLUEPRINT_REVISION = "3af769db122e3c16f64bb78bcd93eb64d3e541e8"
EXPECTED_SKILLS = (
    {
        "computed_hash": "b666527f8ba5fd0e899c4a4fc0dce9daf4862bd33029162710a770f974d76b26",
        "name": "design",
        "path": "skills/design/SKILL.md",
        "sha256": "dbaea31c7d0dcc54901c86e785dad32aadd66dfa891b7db9adee28d926127baa",
    },
    {
        "computed_hash": "f4dc5b78d8fffdb56f72a57f3e649ea7def8e67c1980325dbc37372e667c48ef",
        "name": "improve",
        "path": "skills/improve/SKILL.md",
        "sha256": "3c884673e4300e86569c5545ac2ae97b16460ab566c02b5de85dbdb07af8ea11",
    },
    {
        "computed_hash": "7e5a581c75036dfede93a0a382e1f4bf6249c303b2d5c7acd0ec1c77bead98a0",
        "name": "milestone",
        "path": "skills/milestone/SKILL.md",
        "sha256": "2e2a1135cec50ef558dfb26a1a87170f8f1b120430578adb936fc8f6d09dc3b1",
    },
    {
        "computed_hash": "7f9113696698b2150da9ecdc13949ef2e586fd25d19d0c5f009bb2ddc0ee8d80",
        "name": "plan",
        "path": "skills/plan/SKILL.md",
        "sha256": "56e77acf66bcd38aa6e0151eab1cc3b9e6089e6748c19081d8d11e05a28507a5",
    },
    {
        "computed_hash": "4f0d38e2eb0f6337391f5490d6a3728b70a7ad5949d3a858d0f0fabb4cfa2ebc",
        "name": "review",
        "path": "skills/review/SKILL.md",
        "sha256": "54b65fc112dcfe03b273dc96a97ce3b0bef4ce79467186cb2d337de7562e2f17",
    },
    {
        "computed_hash": "63ebd02b06f5e3fcb7107eb9e48904d4f1de0a0ec0cc2edfe14613a0478a5bda",
        "name": "task-to-pr",
        "path": "skills/task-to-pr/SKILL.md",
        "sha256": "29091f69c0791c77b1f7f1c6e2d490408909878fd915e11294eef968b2823ea0",
    },
    {
        "computed_hash": "a2a1ae92ffd61da6c953c6393d60c1544490e367a546b25b2b5e716a30b405b9",
        "name": "test",
        "path": "skills/test/SKILL.md",
        "sha256": "3ec39ad062a195d801334a3cff5b45f77c2dbc1a08ea603bb7420aabb64e4ec7",
    },
)
EXPECTED_SKILL_NAMES = tuple(skill["name"] for skill in EXPECTED_SKILLS)
EXPECTED_AUTHORIZATION = {
    "application": "exact-byte installation in AEC directed by repository owner",
    "asserted_by": "AEC repository owner",
    "basis": "operator-attested-course-participant-permission",
    "granted_by": "Owain Lewis",
    "recorded_on": "2026-07-21",
    "scope": "course-participant use of the seven Blueprint skills",
}
EXPECTED_INSTALL_PATTERN = "npx skills add owainlewis/blueprint"
EXPECTED_INSTALLER = {
    "agents": ["claude-code", "codex"],
    "lock": "skills-lock.json",
    "method": "local-exact-revision-checkout",
    "name": "skills",
    "version": "1.5.19",
}


def _load_json(path: Path, label: str, errors: list[str]) -> object:
    """Load one JSON object or append a deterministic error."""
    try:
        with path.open(encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError):
        errors.append(f"{label} is missing or invalid JSON")
        return {}


def _frontmatter_name(content: str) -> str | None:
    """Return the simple YAML frontmatter name without importing YAML."""
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        return None
    try:
        closing_index = lines.index("---", 1)
    except ValueError:
        return None
    for line in lines[1:closing_index]:
        if line.startswith("name:"):
            name = line.partition(":")[2].strip()
            return name or None
    return None


def validate_blueprint_installation(root: Path = ROOT) -> list[str]:
    """Return fail-closed errors for the authorized Blueprint skill install."""
    errors: list[str] = []
    manifest = _load_json(
        root / "provenance/blueprint-skills.json",
        "Blueprint skill manifest",
        errors,
    )
    upstream_lock = _load_json(
        root / "provenance/upstream-lock.json",
        "upstream provenance lock",
        errors,
    )
    skills_lock = _load_json(root / "skills-lock.json", "skills lock", errors)
    if errors:
        return errors

    if not isinstance(manifest, dict) or set(manifest) != {
        "discovery",
        "installer",
        "schema_version",
        "skills",
        "source",
    }:
        errors.append("Blueprint skill manifest fields do not match the contract")
        return errors
    if manifest.get("schema_version") != "1.0.0":
        errors.append("Blueprint skill manifest schema_version must equal 1.0.0")

    source = manifest.get("source")
    expected_source = {
        "authorization": EXPECTED_AUTHORIZATION,
        "license": None,
        "repository": BLUEPRINT_REPOSITORY,
        "revision": BLUEPRINT_REVISION,
        "upstream_install_pattern": EXPECTED_INSTALL_PATTERN,
    }
    if source != expected_source:
        errors.append("Blueprint skill source does not match the authorized pin")

    expected_discovery = {
        "canonical_root": ".agents/skills",
        "claude_root": ".claude/skills",
        "claude_strategy": "relative-symlink-to-canonical",
        "codex_root": ".agents/skills",
    }
    if manifest.get("discovery") != expected_discovery:
        errors.append("Blueprint agent discovery contract does not match")
    if manifest.get("installer") != EXPECTED_INSTALLER:
        errors.append("Blueprint installer contract does not match")

    blueprint_lock: dict[str, Any] = {}
    if isinstance(upstream_lock, dict) and isinstance(
        upstream_lock.get("upstreams"), list
    ):
        matches = [
            item
            for item in upstream_lock["upstreams"]
            if isinstance(item, dict) and item.get("name") == "blueprint"
        ]
        if len(matches) == 1:
            blueprint_lock = matches[0]
        else:
            errors.append("upstream provenance must contain one Blueprint record")
    else:
        errors.append("upstream provenance must contain an upstreams list")
    if blueprint_lock.get("license") is not None:
        errors.append("Blueprint license must remain null unless independently verified")
    if blueprint_lock.get("revision") != BLUEPRINT_REVISION:
        errors.append("Blueprint upstream revision does not match the skill manifest")
    if blueprint_lock.get("relationship") != "authorized-skill-source":
        errors.append("Blueprint relationship must be authorized-skill-source")
    if blueprint_lock.get("authorization") != EXPECTED_AUTHORIZATION:
        errors.append("Blueprint authorization record does not match")

    try:
        notice_text = (root / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        errors.append("third-party notice must preserve the Blueprint license boundary")
    else:
        normalized_notice = " ".join(notice_text.split())
        required_notice_fragments = (
            BLUEPRINT_REVISION,
            "did not declare a license",
            "does not claim that Blueprint is MIT licensed",
            "The AEC MIT license covers AEC-authored content and does not relicense",
        )
        if any(
            fragment not in normalized_notice
            for fragment in required_notice_fragments
        ):
            errors.append(
                "third-party notice must preserve the Blueprint license boundary"
            )

    skills = manifest.get("skills")
    if not isinstance(skills, list):
        return errors + ["Blueprint skill manifest skills must be a list"]
    if skills != list(EXPECTED_SKILLS):
        errors.append("Blueprint skill manifest must pin the exact seven skill records")

    lock_skills: object = None
    if isinstance(skills_lock, dict) and skills_lock.get("version") == 1:
        lock_skills = skills_lock.get("skills")
    if not isinstance(lock_skills, dict):
        errors.append("skills lock must contain a version 1 skills object")
        lock_skills = {}
    elif list(lock_skills) != list(EXPECTED_SKILL_NAMES):
        errors.append("skills lock must contain the exact seven Blueprint skills")

    canonical_root = root / ".agents/skills"
    claude_root = root / ".claude/skills"
    canonical_names = (
        sorted(path.name for path in canonical_root.iterdir())
        if canonical_root.is_dir()
        else []
    )
    if canonical_names != list(EXPECTED_SKILL_NAMES):
        errors.append(
            "canonical skill root must contain the exact seven Blueprint skills"
        )
    claude_names = (
        sorted(path.name for path in claude_root.iterdir())
        if claude_root.is_dir()
        else []
    )
    if claude_names != list(EXPECTED_SKILL_NAMES):
        errors.append("Claude skill root must contain the exact seven Blueprint skills")
    for skill in EXPECTED_SKILLS:
        name = skill["name"]
        expected_upstream_path = skill["path"]

        canonical_path = canonical_root / name / "SKILL.md"
        if (canonical_root / name).is_symlink():
            errors.append(
                f"Blueprint canonical skill {name} directory must not be a symlink"
            )
        if not canonical_path.is_file() or canonical_path.is_symlink():
            errors.append(f"Blueprint canonical skill {name} is missing")
        else:
            try:
                content = canonical_path.read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                errors.append(f"Blueprint canonical skill {name} is not UTF-8")
            else:
                digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
                if digest != skill["sha256"]:
                    errors.append(
                        f"Blueprint skill {name} SHA-256 does not match the pinned manifest"
                    )
                if _frontmatter_name(content) != name:
                    errors.append(
                        f"Blueprint skill {name} frontmatter name does not match"
                    )

        claude_path = claude_root / name
        expected_target = Path(f"../../.agents/skills/{name}")
        if not claude_path.is_symlink():
            errors.append(
                f"Claude skill {name} must be a symlink to the canonical skill"
            )
        else:
            try:
                actual_target = Path(claude_path.readlink())
            except OSError:
                errors.append(f"Claude skill {name} symlink cannot be read")
            else:
                if actual_target != expected_target:
                    errors.append(
                        f"Claude skill {name} must target {expected_target}"
                    )
                elif not (claude_path / "SKILL.md").is_file():
                    errors.append(f"Claude skill {name} symlink is dangling")

        lock_record = lock_skills.get(name)
        expected_lock_record = {
            "source": "owainlewis/blueprint",
            "sourceType": "github",
            "skillPath": expected_upstream_path,
            "computedHash": skill["computed_hash"],
        }
        if lock_record != expected_lock_record:
            errors.append(f"skills lock record for {name} does not match")

    return errors


def main() -> int:
    """Report Blueprint installation validation for CI and local use."""
    errors = validate_blueprint_installation()
    if not errors:
        print("PASS blueprint-skills")
        return 0
    for error in errors:
        print(f"FAIL blueprint-skills: {error}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
