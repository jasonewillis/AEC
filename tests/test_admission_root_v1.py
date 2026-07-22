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
        cls.authority = BaseAuthority(
            base_sha="a" * 40,
            validator_blob_oid="b" * 40,
            validator_sha256="c" * 64,
            workflow_blob_oid="d" * 40,
            workflow_sha256="e" * 64,
        )
        cls.blobs: dict[str, bytes] = {}
        cls.entries: dict[bytes, tuple[str, str]] = {}
        for path, digest in SOURCE_BASELINE.items():
            cls._add_baseline(path, digest)
        for path, artifact in ARTIFACT_BASELINE.items():
            cls._add_baseline(path, artifact.sha256)
        for path, digest in WORKFLOW_TRANSITION_BASELINE.items():
            cls._add_baseline(path, digest, WORKFLOW_TRANSITION_BUNDLES[path])

    @classmethod
    def _add_baseline(cls, path: str, digest: str, source: str | None = None) -> None:
        content = (ROOT / (source or path)).read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise AssertionError(f"baseline digest drift: {path}")
        oid = git_blob_oid(content)
        cls.blobs[oid] = content
        cls.entries[path.encode()] = ("100644", oid)

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

    def test_candidate_validator_replacement_cannot_change_base_identity(self) -> None:
        entries = dict(self.entries)
        content = b"raise SystemExit('candidate executed')\n"
        oid = git_blob_oid(content)
        entries[b"tools/admission_root_v1.py"] = ("100644", oid)
        blobs = dict(self.blobs)
        blobs[oid] = content

        report = self.prove(entries=entries, blobs=blobs)

        self.assertTrue(report.passed, report.findings)
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

    def test_base_constants_and_current_bytes_self_check(self) -> None:
        self.assertEqual(
            ARTIFACT_MANIFEST_ROOT, artifact_manifest_root(ARTIFACT_BASELINE)
        )
        self.assertEqual((), self_check(ROOT))


if __name__ == "__main__":
    unittest.main()
