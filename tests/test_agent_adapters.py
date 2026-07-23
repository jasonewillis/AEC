import copy
import json
import unittest
from pathlib import Path

from aec.adapters import (
    AdapterRejection,
    LoaderEvidence,
    build_adapter_receipt,
    codex_nonproject_conflicts,
    parse_claude_loader_log,
    parse_codex_prompt_input,
)


ROOT = Path(__file__).resolve().parents[1]
SKILL_NAMES = (
    "design",
    "improve",
    "milestone",
    "plan",
    "review",
    "task-to-pr",
    "test",
)


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def codex_prompt_input(*, duplicate: bool = False) -> list[object]:
    lines = [
        "## Skills",
        "### Skill roots",
        f"- `r15` = `{ROOT / '.agents/skills'}`",
        "- `r1` = `/opt/global/skills`",
        "### Available skills",
    ]
    lines.extend(
        f"- {name}: Project skill (file: r15/{name}/SKILL.md)"
        for name in SKILL_NAMES
    )
    if duplicate:
        lines.append("- review: Global duplicate (file: r1/review/SKILL.md)")
    return [
        {
            "type": "message",
            "role": "developer",
            "content": [{"type": "input_text", "text": "\n".join(lines)}],
        }
    ]


def claude_loader_log(*, project_count: int = 7, duplicate_count: int = 0) -> str:
    return "\n".join(
        (
            "Loading skills from: managed=/managed, user=/user, "
            f"project=[{ROOT / '.claude/skills'}]",
            f"Total plugin skills loaded: 0 ({duplicate_count} duplicate/user-owned "
            "entries skipped)",
            f"Loaded {project_count} unique skills ({project_count} unconditional, "
            f"0 conditional, managed: 0, user: 0, project: {project_count}, "
            "additional: 0, legacy commands: 0)",
            f"getSkills returning: {project_count} skill dir commands, 0 plugin skills, "
            "34 bundled skills, 0 builtin plugin skills",
        )
    )


class AgentAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        self.catalog = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        self.manifest = load_json(ROOT / "provenance/blueprint-skills.json")

    def test_real_loader_shapes_produce_identical_authoritative_hashes(self) -> None:
        codex = parse_codex_prompt_input(
            codex_prompt_input(),
            runtime_version="codex-cli 0.144.4",
            project_root=ROOT,
        )
        claude = parse_claude_loader_log(
            claude_loader_log(),
            runtime_version="2.1.217 (Claude Code)",
            project_root=ROOT,
        )

        codex_receipt = build_adapter_receipt(
            codex,
            self.request,
            self.catalog,
            self.manifest,
            installation_errors=(),
            project_root=ROOT,
        )
        claude_receipt = build_adapter_receipt(
            claude,
            self.request,
            self.catalog,
            self.manifest,
            installation_errors=(),
            project_root=ROOT,
        )

        self.assertEqual("ready", codex_receipt.status)
        self.assertEqual("ready", claude_receipt.status)
        self.assertTrue(codex_receipt.authoritative)
        self.assertTrue(claude_receipt.authoritative)
        self.assertFalse(codex_receipt.executes)
        self.assertFalse(codex_receipt.mutates)
        self.assertEqual("1.0.0", codex_receipt.schema_version)
        self.assertEqual(7, codex_receipt.discovery_count)
        self.assertEqual(7, claude_receipt.discovery_count)
        self.assertEqual(codex_receipt.request_hash, claude_receipt.request_hash)
        self.assertEqual(codex_receipt.decision_hash, claude_receipt.decision_hash)
        self.assertEqual(
            codex_receipt.skill_manifest_hash,
            claude_receipt.skill_manifest_hash,
        )
        self.assertEqual(
            "sha256:8489f951e3b1cb41b63d7673aeb18a56bd5b16b2d45fa976275f8c16205526ee",
            codex_receipt.decision_hash,
        )

    def test_duplicate_codex_skill_name_fails_closed(self) -> None:
        result = parse_codex_prompt_input(
            codex_prompt_input(duplicate=True),
            runtime_version="codex-cli 0.144.4",
            project_root=ROOT,
        )

        self.assertIsInstance(result, AdapterRejection)
        self.assertEqual("DUPLICATE_SKILL_DISCOVERY", result.code)

    def test_codex_conflict_preflight_returns_only_the_nonproject_path(self) -> None:
        conflicts = codex_nonproject_conflicts(
            codex_prompt_input(duplicate=True),
            project_root=ROOT,
        )

        self.assertEqual(("/opt/global/skills/review/SKILL.md",), conflicts)

    def test_missing_or_stale_codex_project_root_fails_closed(self) -> None:
        payload = codex_prompt_input()
        payload[0]["content"][0]["text"] = payload[0]["content"][0]["text"].replace(
            str(ROOT / ".agents/skills"),
            "/stale/project/.agents/skills",
        )

        result = parse_codex_prompt_input(
            payload,
            runtime_version="codex-cli 0.144.4",
            project_root=ROOT,
        )

        self.assertIsInstance(result, AdapterRejection)
        self.assertEqual("PROJECT_SKILL_ROOT_MISSING", result.code)

    def test_malformed_codex_evidence_fails_closed(self) -> None:
        result = parse_codex_prompt_input(
            {"unexpected": True},
            runtime_version="codex-cli 0.144.4",
            project_root=ROOT,
        )

        self.assertIsInstance(result, AdapterRejection)
        self.assertEqual("LOADER_EVIDENCE_INVALID", result.code)

    def test_claude_missing_skill_or_duplicate_skip_fails_closed(self) -> None:
        missing = parse_claude_loader_log(
            claude_loader_log(project_count=6),
            runtime_version="2.1.217 (Claude Code)",
            project_root=ROOT,
        )
        duplicate = parse_claude_loader_log(
            claude_loader_log(duplicate_count=1),
            runtime_version="2.1.217 (Claude Code)",
            project_root=ROOT,
        )

        self.assertIsInstance(missing, AdapterRejection)
        self.assertEqual("SKILL_SET_MISMATCH", missing.code)
        self.assertIsInstance(duplicate, AdapterRejection)
        self.assertEqual("DUPLICATE_SKILL_DISCOVERY", duplicate.code)

    def test_invalid_installation_or_manifest_mismatch_never_claims_parity(self) -> None:
        evidence = parse_codex_prompt_input(
            codex_prompt_input(),
            runtime_version="codex-cli 0.144.4",
            project_root=ROOT,
        )
        invalid_install = build_adapter_receipt(
            evidence,
            self.request,
            self.catalog,
            self.manifest,
            installation_errors=("skill hash mismatch",),
            project_root=ROOT,
        )
        changed_manifest = copy.deepcopy(self.manifest)
        changed_manifest["skills"][0]["name"] = "renamed"
        mismatched_manifest = build_adapter_receipt(
            evidence,
            self.request,
            self.catalog,
            changed_manifest,
            installation_errors=(),
            project_root=ROOT,
        )

        self.assertEqual("SKILL_INSTALLATION_INVALID", invalid_install.code)
        self.assertEqual("rejected", invalid_install.status)
        self.assertFalse(invalid_install.authoritative)
        self.assertIsNone(invalid_install.decision_hash)
        self.assertEqual("SKILL_MANIFEST_MISMATCH", mismatched_manifest.code)
        self.assertIsNone(mismatched_manifest.decision_hash)

    def test_direct_malformed_loader_evidence_fails_closed(self) -> None:
        valid = {
            "agent": "codex",
            "runtime_version": "codex-cli 0.144.4",
            "skill_names": SKILL_NAMES,
            "project_root": str(ROOT / ".agents/skills"),
            "suppressed_conflicts": 0,
        }
        malformed = {
            "unsupported agent": {"agent": "evil"},
            "empty runtime": {"runtime_version": ""},
            "wrong skill order": {"skill_names": tuple(reversed(SKILL_NAMES))},
            "relative project root": {"project_root": ".agents/skills"},
            "stale project root": {"project_root": "/stale/.agents/skills"},
            "wrong root kind": {"project_root": str(ROOT / ".claude/skills")},
            "negative conflict count": {"suppressed_conflicts": -1},
            "boolean conflict count": {"suppressed_conflicts": False},
            "claude conflict suppression": {
                "agent": "claude",
                "project_root": str(ROOT / ".claude/skills"),
                "suppressed_conflicts": 1,
            },
        }

        for label, changes in malformed.items():
            with self.subTest(label=label):
                evidence = LoaderEvidence(**(valid | changes))
                result = build_adapter_receipt(
                    evidence,
                    self.request,
                    self.catalog,
                    self.manifest,
                    installation_errors=(),
                    project_root=ROOT,
                )

                self.assertEqual("LOADER_EVIDENCE_INVALID", result.code)
                self.assertEqual("rejected", result.status)
                self.assertFalse(result.authoritative)
                self.assertIsNone(result.decision_hash)

    def test_aec_unavailable_is_explicit_non_authoritative_degraded_mode(self) -> None:
        evidence = parse_codex_prompt_input(
            codex_prompt_input(),
            runtime_version="codex-cli 0.144.4",
            project_root=ROOT,
        )

        result = build_adapter_receipt(
            evidence,
            self.request,
            self.catalog,
            self.manifest,
            installation_errors=(),
            project_root=ROOT,
            aec_available=False,
        )

        self.assertEqual("degraded", result.status)
        self.assertEqual("AEC_UNAVAILABLE", result.code)
        self.assertFalse(result.authoritative)
        self.assertIsNone(result.request_hash)
        self.assertIsNone(result.decision_hash)
        self.assertIsNone(result.skill_manifest_hash)

    def test_aec_unavailable_dominates_loader_rejection(self) -> None:
        result = build_adapter_receipt(
            AdapterRejection(code="PROJECT_SKILL_ROOT_MISSING", agent="codex"),
            self.request,
            self.catalog,
            self.manifest,
            installation_errors=(),
            project_root=ROOT,
            aec_available=False,
        )

        self.assertEqual("degraded", result.status)
        self.assertEqual("AEC_UNAVAILABLE", result.code)
        self.assertFalse(result.authoritative)


if __name__ == "__main__":
    unittest.main()
