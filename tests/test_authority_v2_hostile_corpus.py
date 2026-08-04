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
    PROOF_CLOSURE_BASELINE,
    SOURCE_BASELINE,
    WORKFLOW_TRANSITION_BASELINE,
    WORKFLOW_TRANSITION_BUNDLES,
)


ROOT = Path(__file__).resolve().parents[1]
REJECTION = "ADMISSION-001 EXACT_BASELINE"
# FROZEN_PYTHON_PATHS unpacks *SOURCE_BASELINE, which derives from the source
# declaration. That is the artifact the corpus attacks, so corpus coverage would
# otherwise shrink silently whenever a path left the declaration: the tree each
# hostile case is built on would simply stop containing that file, and every
# assertion below would still pass. Pinning the count makes such a shrink a test
# failure instead.
#
# The tuple holds duplicates by construction, because the literal tail repeats 17
# paths that SOURCE_BASELINE already supplies. Pin the DISTINCT count, not len():
# it is the real coverage number, and it cannot be inflated back to green by
# adding a repeat. Of the 52 distinct paths, 44 arrive via SOURCE_BASELINE and
# only 8 are pinned independently of the declaration.
#
# Bump these deliberately when adding or removing tracked source.
#
# TWO pins are required, and neither is sufficient alone:
#   * EXPECTED_DISTINCT_FROZEN_PATHS guards the corpus tree. It fires when a path
#     leaves coverage entirely.
#   * EXPECTED_SOURCE_BASELINE_PATHS guards the declaration. It is the only one
#     that fires for the 17 paths the literal tail duplicates: dropping one of
#     those from the declaration leaves the distinct count unchanged, because the
#     literal tail still supplies it. Without this pin the canary covered only
#     part of the declared source set directly.
#
# Bumped 2026-07-25: +6 tracked files (aec/state_builder.py,
# aec/human_render.py, tools/aec_coach.py, and their three test files) when
# build_state.py/render_checkpoint.py were ported from HealthRAG (#58, #52).
# Merged with the +2 from #72 (tools/validate_consumer_connection.py,
# tests/test_consumer_connection_proof.py), giving 37 declared paths.
# Bumped 2026-07-26: +3 release-contract files (aec/release_manifest.py,
# tools/release_manifest.py, and tests/test_release_manifest.py).
# Bumped 2026-07-28: +2 authenticated release-evidence files
# (tools/release_api_evidence.py and tests/test_release_api_evidence.py).
# Bumped 2026-07-29: +1 red-first regression test
# (tests/test_generate_source_declaration.py) for #74.
# Bumped 2026-07-29: +1 in-tree adversarial replay corpus
# (tests/test_admission_attack_corpus.py) for #67.
# Bumped 2026-08-03: +1 doctor fail-closed proof
# (tests/test_aec_doctor_fails_closed.py) for #109. The `doctor` subcommand
# itself added no new tracked path: it landed inside the already-declared
# tools/aec_coach.py.
# Bumped 2026-08-03: +1 executable proof for the consumer install kit
# (tests/test_consumer_install_kit.py) for #109. It walks the documented
# install steps in a throwaway consumer repository, which is what
# docs/consumer-kit/state_producer_template.py needed: that template is a
# tracked, copy-and-run .py outside the coverage clause, so it can never be a
# frozen path itself and had nothing executing it.
# Bumped 2026-08-03: +1 for tests/test_declaration_sees_untracked_python.py, the
# canary for the untracked-.py control. Both Foundation gate failures that day
# were the identical `python_paths` assertion; the control closes the local gap.
# Bumped 2026-08-03: +1 for tests/test_read_only_authority_boundary.py, the
# first red canary on AEC's central read-only claim. Widening either boundary
# check previously left the whole suite green.
# Bumped 2026-08-03: +1 for tests/test_state_binds_consumer_repo.py, which pins
# that `state` can describe a repository other than AEC's own. Before it, the
# prompt hook rendered AEC's revision and project on every consumer's card.
EXPECTED_DISTINCT_FROZEN_PATHS = 60
# Bumped 2026-08-03 alongside the count above: tests/test_consumer_install_kit.py
# is a new tracked source path, so it enters the declaration as well as the tree.
#
# Bumped again 2026-08-03: +1 for tests/test_docs_links.py, which resolves every
# documentation path this repository names. This canary fired on it correctly and
# is the reason the addition is recorded here rather than absorbed silently.
EXPECTED_SOURCE_BASELINE_PATHS = 52
FROZEN_PYTHON_PATHS = (
    *SOURCE_BASELINE,
    "aec/adapters.py",
    "aec/consumer.py",
    "aec/mentor.py",
    "tests/test_admission_root_v1.py",
    "tests/test_agent_adapters.py",
    "tests/test_authority_v2_hostile_corpus.py",
    "tests/test_blueprint_skills.py",
    "tests/test_consumer_interface.py",
    "tests/test_exact_json.py",
    "tests/test_foundation_validation.py",
    "tests/test_foundation_behavior.py",
    "tests/test_private_mentor_lens.py",
    "tests/test_resolver.py",
    "tests/test_resolver_blocker_precedence.py",
    "tests/test_resolver_program.py",
    "tests/test_review_attestation.py",
    "tools/__init__.py",
    "tools/admission_root_v1.py",
    "tools/generate_resolver.py",
    "tools/generate_source_declaration.py",
    "tools/prove_agent_adapter_parity.py",
    "tools/prove_foundation_behavior.py",
    "tools/prove_private_mentor_lens.py",
    "tools/validate_blueprint_skills.py",
    "tools/validate_foundation.py",
)


class AuthorityV2HostileCorpus(unittest.TestCase):
    """Freeze hostile families independently of the registries they attack."""

    @classmethod
    def setUpClass(cls) -> None:
        validator = (ROOT / "tools/admission_root_v1.py").read_bytes()
        workflow = (ROOT / ".github/workflows/candidate-admission.yml").read_bytes()
        cls.authority = BaseAuthority(
            base_sha="a" * 40,
            validator_blob_oid=git_blob_oid(validator),
            validator_sha256=hashlib.sha256(validator).hexdigest(),
            workflow_blob_oid=git_blob_oid(workflow),
            workflow_sha256=hashlib.sha256(workflow).hexdigest(),
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
        for path, baseline in PROOF_CLOSURE_BASELINE.items():
            source = ROOT / path
            content = (
                os.readlink(source).encode()
                if baseline.mode == "120000"
                else source.read_bytes()
            )
            cls._put(entries, blobs, path.encode(), content, mode=baseline.mode)
        for path in FROZEN_PYTHON_PATHS:
            if path.encode() not in entries:
                cls._put(entries, blobs, path.encode(), (ROOT / path).read_bytes())
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

    def test_frozen_python_path_coverage_has_not_shrunk(self) -> None:
        """RED CANARY: corpus coverage is derived, so it can shrink in silence."""
        self.assertEqual(
            len(set(FROZEN_PYTHON_PATHS)),
            EXPECTED_DISTINCT_FROZEN_PATHS,
            "distinct FROZEN_PYTHON_PATHS coverage changed. If a tracked source "
            "file was added or removed on purpose, update "
            "EXPECTED_DISTINCT_FROZEN_PATHS. If not, a path silently left the "
            "source declaration and every hostile case below is now building its "
            "tree without it.",
        )
        self.assertEqual(
            len(SOURCE_BASELINE),
            EXPECTED_SOURCE_BASELINE_PATHS,
            "the source declaration changed size. This is the only assertion "
            "that fires when a dropped path is also present in the literal tail "
            "of FROZEN_PYTHON_PATHS, where the distinct count above stays "
            "constant and notices nothing.",
        )

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
