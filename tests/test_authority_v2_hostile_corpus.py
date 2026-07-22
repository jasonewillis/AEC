"""Red-first hostile corpus for the base-owned RESOLVE-007 authority-v2 contract."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.admission_root_v1 import BaseAuthority, git_blob_oid, validate_candidate
from tools.admission_root_v1 import (
    ARTIFACT_BASELINE,
    SOURCE_BASELINE,
    WORKFLOW_TRANSITION_BASELINE,
    WORKFLOW_TRANSITION_BUNDLES,
)


ROOT = Path(__file__).resolve().parents[1]
REJECTION = "ADMISSION-001 EXACT_BASELINE"


class AuthorityV2HostileCorpus(unittest.TestCase):
    """Freeze hostile families independently of the registries they attack."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.authority = BaseAuthority(
            base_sha="a" * 40,
            validator_blob_oid="b" * 40,
            validator_sha256="c" * 64,
            workflow_blob_oid="d" * 40,
            workflow_sha256="e" * 64,
        )
        cls.entries, cls.blobs = cls._admitted_transition_snapshot()

    @classmethod
    def _admitted_transition_snapshot(
        cls,
    ) -> tuple[dict[bytes, tuple[str, str]], dict[str, bytes]]:
        """Build the currently admitted transition without candidate registries."""
        entries: dict[bytes, tuple[str, str]] = {}
        blobs: dict[str, bytes] = {}
        for path in SOURCE_BASELINE:
            cls._put(entries, blobs, path.encode(), (ROOT / path).read_bytes())
        for path in ARTIFACT_BASELINE:
            cls._put(entries, blobs, path.encode(), (ROOT / path).read_bytes())
        for target, bundle in WORKFLOW_TRANSITION_BUNDLES.items():
            content = (ROOT / bundle).read_bytes()
            if (
                hashlib.sha256(content).hexdigest()
                != WORKFLOW_TRANSITION_BASELINE[target]
            ):
                raise AssertionError(f"workflow transition drift: {target}")
            cls._put(entries, blobs, target.encode(), content)
        for path in (
            "aec/consumer.py",
            "tools/__init__.py",
            "tools/admission_root_v1.py",
            "tools/generate_resolver.py",
            "tools/validate_blueprint_skills.py",
            "tools/validate_foundation.py",
            ".github/admission/v1/foundation-gate.yml",
        ):
            cls._put(entries, blobs, path.encode(), (ROOT / path).read_bytes())
        cls._put(
            entries,
            blobs,
            b".claude/skills/milestone",
            os.readlink(ROOT / ".claude/skills/milestone").encode(),
            mode="120000",
        )
        return entries, blobs

    @staticmethod
    def _raw_stage(entries: dict[bytes, tuple[str, str]]) -> bytes:
        return b"".join(
            mode.encode() + b" " + object_id.encode() + b" 0\t" + path + b"\0"
            for path, (mode, object_id) in sorted(entries.items())
        )

    @staticmethod
    def _put(
        entries: dict[bytes, tuple[str, str]],
        blobs: dict[str, bytes],
        path: bytes,
        content: bytes,
        mode: str = "100644",
    ) -> None:
        object_id = git_blob_oid(content)
        entries[path] = (mode, object_id)
        blobs[object_id] = content

    def _report(
        self,
        entries: dict[bytes, tuple[str, str]],
        blobs: dict[str, bytes],
        raw_records: bytes | None = None,
    ):
        return validate_candidate(
            raw_records=(
                self._raw_stage(entries) if raw_records is None else raw_records
            ),
            record_format="stage-v1",
            blobs=blobs,
            authority=self.authority,
        )

    def _assert_rejected(self, case_id: str, report) -> None:
        self.assertFalse(report.passed, f"{case_id} false green")
        self.assertIn(REJECTION, report.findings, case_id)

    def test_self_authorization_fails_without_executing_candidate_code(self) -> None:
        attacks = (
            ("SELF-001", b"tools/admission_root_v1.py"),
            ("SELF-002", b"tools/prove_foundation_behavior.py"),
            ("SELF-003", b"tests/test_foundation_behavior.py"),
            ("SELF-004", b".github/admission/v1/foundation-gate.yml"),
        )
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "candidate-executed"
            side_effect = (
                "from pathlib import Path\n"
                f"Path({str(sentinel)!r}).write_text('executed')\n"
            ).encode()
            for case_id, attacked_path in attacks:
                with self.subTest(case_id=case_id):
                    entries = dict(self.entries)
                    blobs = dict(self.blobs)
                    self._put(
                        entries, blobs, attacked_path, b"# candidate replacement\n"
                    )
                    self._put(entries, blobs, b"sitecustomize.py", side_effect)

                    report = self._report(entries, blobs)

                    self.assertFalse(sentinel.exists(), case_id)
                    self._assert_rejected(case_id, report)

    def test_closure_drift_cannot_be_reauthorized_by_candidate_claims(self) -> None:
        cases = (
            ("CLOSURE-001", "change", b"aec/consumer.py"),
            ("CLOSURE-002", "remove", b"tools/validate_foundation.py"),
            ("CLOSURE-003", "rename", b"tools/generate_resolver.py"),
            ("CLOSURE-004", "add", b"tools/proof_helper.py"),
        )
        for case_id, operation, path in cases:
            with self.subTest(case_id=case_id):
                entries = dict(self.entries)
                blobs = dict(self.blobs)
                if operation == "change":
                    self._put(entries, blobs, path, b"# changed runtime closure\n")
                elif operation == "remove":
                    entries.pop(path)
                elif operation == "rename":
                    mode, object_id = entries.pop(path)
                    entries[b"tools/generate_resolver_renamed.py"] = (mode, object_id)
                else:
                    self._put(entries, blobs, path, b"# added runtime closure\n")
                self._put(
                    entries,
                    blobs,
                    b"tools/admission_root_v1.py",
                    b"# candidate-updated closure hashes and manifests\n",
                )

                self._assert_rejected(case_id, self._report(entries, blobs))

    def test_git_paths_and_modes_are_total_fail_closed_inputs(self) -> None:
        cases = (
            ("GITPATH-001", "unterminated"),
            ("GITPATH-002", "duplicate"),
            ("GITPATH-003", "unusual"),
            ("GITPATH-004", "runtime-symlink"),
            ("GITPATH-005", "claude-target"),
        )
        for case_id, operation in cases:
            with self.subTest(case_id=case_id):
                entries = dict(self.entries)
                blobs = dict(self.blobs)
                raw_records = None
                if operation == "unterminated":
                    raw_records = self._raw_stage(entries)[:-1]
                elif operation == "duplicate":
                    first = self._raw_stage(entries).split(b"\0", 1)[0] + b"\0"
                    raw_records = self._raw_stage(entries) + first
                elif operation == "unusual":
                    self._put(entries, blobs, b"odd-\xff-path", b"ignored today\n")
                elif operation == "runtime-symlink":
                    self._put(
                        entries,
                        blobs,
                        b"aec/resolver.py",
                        b"contracts.py",
                        mode="120000",
                    )
                else:
                    self._put(
                        entries,
                        blobs,
                        b".claude/skills/milestone",
                        b"../../outside/SKILL.md",
                        mode="120000",
                    )

                report = self._report(entries, blobs, raw_records)

                self._assert_rejected(case_id, report)

    def test_ambiguous_artifact_cannot_relabel_itself_into_admission(self) -> None:
        case_id = "ARTIFACT-001"
        entries = dict(self.entries)
        blobs = dict(self.blobs)
        ambiguous = (
            b'{"repository":"jasonewillis/AEC","repository":"JLWAI/fedJobAdvisor",'
            b'"project_number":3}\n'
        )
        self._put(
            entries,
            blobs,
            b"config/resolver/resolver-program.json",
            ambiguous,
        )
        self._put(
            entries,
            blobs,
            b"tools/admission_root_v1.py",
            b"# candidate-updated artifact class and digest\n",
        )

        self._assert_rejected(case_id, self._report(entries, blobs))

    def test_hashseed_divergence_requires_a_base_owned_four_process_proof(self) -> None:
        case_id = "DECISION-001"
        fixture = b'print(next(iter({"alpha", "beta", "gamma", "delta"})))\n'
        outputs = set()
        for seed in ("1", "2", "3", "4"):
            environment = dict(os.environ, PYTHONHASHSEED=seed)
            result = subprocess.run(
                [sys.executable, "-c", fixture.decode("ascii")],
                check=True,
                capture_output=True,
                env=environment,
                text=True,
            )
            outputs.add(result.stdout)
        self.assertGreater(len(outputs), 1, "hostile fixture must actually diverge")
        entries = dict(self.entries)
        blobs = dict(self.blobs)
        self._put(entries, blobs, b"tools/prove_foundation_behavior.py", fixture)

        self._assert_rejected(case_id, self._report(entries, blobs))


if __name__ == "__main__":
    unittest.main()
