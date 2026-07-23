"""Red-first proof for the dormant base-owned admission trust root."""

from __future__ import annotations

import copy
import hashlib
import unittest
from pathlib import Path

from tools.admission_root_v1 import (
    ADMISSION_PROTOCOL,
    ARTIFACT_BASELINE,
    ARTIFACT_MANIFEST_ROOT,
    BEHAVIOR_IDENTITY,
    PROOF_CLOSURE_BASELINE,
    PYTHON_PATHS,
    SOURCE_BASELINE,
    WORKFLOW_TRANSITION_BASELINE,
    WORKFLOW_TRANSITION_BUNDLES,
    BaseAuthority,
    artifact_manifest_root,
    git_blob_oid,
    parse_git_records,
    self_check,
    validate_candidate,
)


ROOT = Path(__file__).resolve().parents[1]


class AdmissionRootV1Tests(unittest.TestCase):
    """Prove exact base authority and raw candidate-data admission."""

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
        cls.blobs: dict[str, bytes] = {}
        cls.entries: dict[bytes, tuple[str, str]] = {}
        for path, digest in SOURCE_BASELINE.items():
            cls._add_baseline(path, digest)
        for path, artifact in ARTIFACT_BASELINE.items():
            cls._add_baseline(path, artifact.sha256)
        for path, digest in WORKFLOW_TRANSITION_BASELINE.items():
            cls._add_baseline(path, digest, WORKFLOW_TRANSITION_BUNDLES[path])
        for path, baseline in PROOF_CLOSURE_BASELINE.items():
            source = ROOT / path
            content = (
                source.readlink().as_posix().encode()
                if baseline.mode == "120000"
                else source.read_bytes()
            )
            cls._add_bytes(path, content, baseline.mode)
        for path in PYTHON_PATHS:
            if path.encode() not in cls.entries:
                cls._add_bytes(path, (ROOT / path).read_bytes())

    @classmethod
    def _add_baseline(cls, path: str, digest: str, source: str | None = None) -> None:
        content = (ROOT / (source or path)).read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise AssertionError(f"baseline digest drift: {path}")
        cls._add_bytes(path, content)

    @classmethod
    def _add_bytes(cls, path: str, content: bytes, mode: str = "100644") -> None:
        """Add one exact repository path to the candidate snapshot."""
        oid = git_blob_oid(content)
        cls.blobs[oid] = content
        cls.entries[path.encode()] = (mode, oid)

    def raw_stage(self, entries: dict[bytes, tuple[str, str]] | None = None) -> bytes:
        """Return strict NUL-delimited stage records without path decoding."""
        selected = self.entries if entries is None else entries
        return b"".join(
            mode.encode() + b" " + oid.encode() + b" 0\t" + path + b"\0"
            for path, (mode, oid) in sorted(selected.items())
        )

    def prove(
        self,
        *,
        entries: dict[bytes, tuple[str, str]] | None = None,
        blobs: dict[str, bytes] | None = None,
    ):
        """Validate one candidate data snapshot against the base-owned root."""
        return validate_candidate(
            raw_records=self.raw_stage(entries),
            record_format="stage-v1",
            blobs=self.blobs if blobs is None else blobs,
            authority=self.authority,
        )

    def test_safe_baseline_passes_three_dormant_outcomes(self) -> None:
        report = self.prove()

        self.assertTrue(report.passed, report.findings)
        self.assertEqual(report.protocol, ADMISSION_PROTOCOL)
        self.assertEqual(report.behavior_identity, BEHAVIOR_IDENTITY)
        self.assertEqual(report.base_authority, self.authority)

    def test_raw_unusual_json_path_is_preserved_and_rejected(self) -> None:
        entries = dict(self.entries)
        content = b'{"project":"concrete/repository"}\n'
        oid = git_blob_oid(content)
        entries[b"rogue\n.json"] = ("100644", oid)
        blobs = dict(self.blobs)
        blobs[oid] = content

        records = parse_git_records(self.raw_stage(entries), "stage-v1")
        report = self.prove(entries=entries, blobs=blobs)

        self.assertIn(b"rogue\n.json", {record.path for record in records})
        self.assertIn("ADMISSION-001 EXACT_BASELINE", report.findings)

    def test_missing_extra_and_nonregular_entries_fail(self) -> None:
        missing = dict(self.entries)
        missing.pop(b"aec/resolver.py")
        extra = dict(self.entries)
        content = b"{}\n"
        oid = git_blob_oid(content)
        extra[b"extra.json"] = ("100644", oid)
        nonregular = dict(self.entries)
        mode, existing_oid = nonregular[b"aec/resolver.py"]
        self.assertEqual(mode, "100644")
        nonregular[b"aec/resolver.py"] = ("120000", existing_oid)
        blobs = dict(self.blobs)
        blobs[oid] = content

        for report in (
            self.prove(entries=missing),
            self.prove(entries=extra, blobs=blobs),
            self.prove(entries=nonregular),
        ):
            self.assertIn("ADMISSION-001 EXACT_BASELINE", report.findings)

    def test_duplicate_nonzero_stage_and_unterminated_records_fail_parsing(
        self,
    ) -> None:
        record = b"100644 " + b"a" * 40 + b" 0\taec/resolver.py\0"
        nonzero = b"100644 " + b"a" * 40 + b" 2\taec/resolver.py\0"
        for raw in (record + record, nonzero, record[:-1]):
            with self.assertRaises(ValueError):
                parse_git_records(raw, "stage-v1")

    def test_tree_records_are_nul_delimited_and_exact(self) -> None:
        raw = b"100644 blob " + b"a" * 40 + b"\taec/resolver.py\0"

        records = parse_git_records(raw, "tree-v1")

        self.assertEqual(records[0].path, b"aec/resolver.py")
        self.assertEqual(records[0].mode, "100644")

    def test_content_blob_hash_and_class_drift_fail(self) -> None:
        path = b"aec/resolver.py"
        changed = dict(self.entries)
        changed_content = self.blobs[changed[path][1]] + b"\n# drift\n"
        changed_oid = git_blob_oid(changed_content)
        changed[path] = ("100644", changed_oid)
        changed_blobs = dict(self.blobs)
        changed_blobs[changed_oid] = changed_content
        wrong_blob = dict(self.blobs)
        wrong_blob[self.entries[path][1]] = b"wrong bytes"
        rows = copy.deepcopy(ARTIFACT_BASELINE)
        first = next(iter(rows))
        rows[first] = rows[first]._replace(closed_class="consumer-profile")

        self.assertIn(
            "ADMISSION-001 EXACT_BASELINE",
            self.prove(entries=changed, blobs=changed_blobs).findings,
        )
        self.assertIn(
            "ADMISSION-001 EXACT_BASELINE",
            self.prove(blobs=wrong_blob).findings,
        )
        self.assertNotEqual(ARTIFACT_MANIFEST_ROOT, artifact_manifest_root(rows))

    def test_candidate_validator_replacement_is_rejected_by_base_identity(self) -> None:
        entries = dict(self.entries)
        content = b"raise SystemExit('candidate executed')\n"
        oid = git_blob_oid(content)
        entries[b"tools/admission_root_v1.py"] = ("100644", oid)
        blobs = dict(self.blobs)
        blobs[oid] = content

        report = self.prove(entries=entries, blobs=blobs)

        self.assertIn("ADMISSION-001 EXACT_BASELINE", report.findings)
        self.assertEqual(report.base_authority, self.authority)

    def test_workflow_transition_is_exact_and_closed(self) -> None:
        changed = dict(self.entries)
        target = b".github/workflows/candidate-admission.yml"
        changed_content = self.blobs[changed[target][1]] + b"\n# drift\n"
        changed_oid = git_blob_oid(changed_content)
        changed[target] = ("100644", changed_oid)
        changed_blobs = dict(self.blobs)
        changed_blobs[changed_oid] = changed_content
        duplicate = dict(self.entries)
        duplicate[b".github/workflows/duplicate.yml"] = changed[target]

        for report in (
            self.prove(entries=changed, blobs=changed_blobs),
            self.prove(entries=duplicate, blobs=changed_blobs),
        ):
            self.assertIn("ADMISSION-001 EXACT_BASELINE", report.findings)

    def test_base_workflow_admits_before_behavior_and_publishes_exact_head(
        self,
    ) -> None:
        workflow = (ROOT / ".github/workflows/candidate-admission.yml").read_text()
        admit = workflow.split("\n  admit:\n", 1)[1].split("\n  behavior:\n", 1)[0]
        behavior = workflow.split("\n  behavior:\n", 1)[1].split(
            "\n  publish-validate:\n", 1
        )[0]
        publish = workflow.split("\n  publish-validate:\n", 1)[1]

        self.assertIn("--candidate", admit)
        self.assertIn("permissions:\n      contents: read", admit)
        self.assertIn("persist-credentials: true", admit)
        self.assertLess(
            admit.index("persist-credentials: true"),
            admit.index('git fetch --no-tags --depth=1 origin "${HEAD_SHA}"'),
        )
        self.assertIn("needs: admit", behavior)
        self.assertIn("permissions:\n      contents: read", behavior)
        self.assertIn("ref: ${{ needs.admit.outputs.head-sha }}", behavior)
        self.assertIn("persist-credentials: false", behavior)
        self.assertNotIn("permissions:\n      statuses: write", behavior)
        self.assertIn("python3 -m unittest discover -s tests -v", behavior)
        self.assertIn(
            "tests/test_foundation_behavior.py",
            PROOF_CLOSURE_BASELINE,
        )
        self.assertIn("needs: [admit, behavior]", publish)
        self.assertIn("if: ${{ always() }}", publish)
        self.assertIn("permissions:\n      statuses: write", publish)
        self.assertIn("HEAD_SHA: ${{ github.event.pull_request.head.sha }}", publish)
        self.assertIn("ADMITTED_SHA: ${{ needs.admit.outputs.head-sha }}", publish)
        self.assertIn('context: "validate"', publish)
        self.assertIn("sha: headSha", publish)
        self.assertIn('state: passed ? "success" : "failure"', publish)
        self.assertNotIn("actions/checkout", publish)
        self.assertNotIn("tools.admission_root_v1 --candidate", publish)

    def test_pr_b_keeps_admission_workflow_and_changes_only_legacy_gate(self) -> None:
        active = (ROOT / ".github/workflows/candidate-admission.yml").read_bytes()
        transitioned_gate = (
            ROOT / ".github/workflows/foundation-gate.yml"
        ).read_bytes()
        future_gate = (ROOT / ".github/admission/v1/foundation-gate.yml").read_bytes()

        self.assertEqual(
            hashlib.sha256(active).hexdigest(),
            WORKFLOW_TRANSITION_BASELINE[".github/workflows/candidate-admission.yml"],
        )
        self.assertEqual(
            hashlib.sha256(future_gate).hexdigest(),
            WORKFLOW_TRANSITION_BASELINE[".github/workflows/foundation-gate.yml"],
        )
        self.assertEqual(future_gate, transitioned_gate)

    def test_base_constants_and_current_bytes_self_check(self) -> None:
        self.assertEqual(
            ARTIFACT_MANIFEST_ROOT, artifact_manifest_root(ARTIFACT_BASELINE)
        )
        self.assertEqual((), self_check(ROOT))

    def test_resolve009_controlled_transition_matches_exact_candidate_bytes(
        self,
    ) -> None:
        expected = {
            "aec/resolver.py": (
                "67b4fd4651291010e58999b782e35e9f1383d560cbcf4d6b2f239fe6e16e6ae2"
            ),
            "schemas/resolution-decision.schema.json": (
                "7ecf82040cb46e26476d50fab5c85a39b47f5b206748a71af3ca960ebc9e2d57"
            ),
            "schemas/resolution-request.schema.json": (
                "ad4a414b1ce85010e646f12851d381257c64479019232ee36cc98f4863c3ce59"
            ),
        }

        self.assertEqual(
            expected["aec/resolver.py"],
            SOURCE_BASELINE["aec/resolver.py"],
        )
        for path in expected.keys() - {"aec/resolver.py"}:
            self.assertEqual(expected[path], ARTIFACT_BASELINE[path].sha256)
        self.assertEqual(
            expected,
            {
                path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
                for path in expected
            },
        )


if __name__ == "__main__":
    unittest.main()
