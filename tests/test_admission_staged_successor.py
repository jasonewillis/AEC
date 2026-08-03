"""Red-first proof for the base-staged successor validator promotion path.

Issue #65: a candidate that modifies `tools/admission_root_v1.py` can never be
admitted, because the base-owned CI job supplies the validator identity from
the BASE checkout and `validate_candidate` requires byte equality with it. The
prototype under proof here adds exactly one additional way to satisfy that
clause: the candidate's validator bytes are byte-identical to a successor the
BASE revision already committed at `tools/admission_root_next_v1.py`, and the
candidate deletes that staged file in the same change.

Every test builds a real candidate tree snapshot (Git stage records plus blob
bytes plus a self-consistent source declaration) and calls
`validate_candidate` directly, so no shell replay is involved. Each red canary
additionally asserts that `_verify_local` finds nothing wrong with the
candidate tree, which pins the rejection to the validator-identity clause and
not to some incidental declaration drift.
"""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from tools.admission_root_v1 import (
    ARTIFACT_BASELINE,
    DECLARATION_PATH,
    PROOF_CLOSURE_BASELINE,
    PYTHON_PATHS,
    SOURCE_BASELINE,
    STAGED_SUCCESSOR_PATH,
    VALIDATOR_PATH,
    WORKFLOW_TRANSITION_BASELINE,
    WORKFLOW_TRANSITION_BUNDLES,
    BaseAuthority,
    GitRecord,
    GitRecordTreeView,
    _verify_local,
    git_blob_oid,
    load_staged_successor,
    parse_declaration,
    validate_candidate,
)


ROOT = Path(__file__).resolve().parents[1]
ADMISSION_FINDING = "ADMISSION-001 EXACT_BASELINE"


class StagedSuccessorPromotionTests(unittest.TestCase):
    """Prove the promotion path admits only a base-pre-authorized successor."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.live_validator = (ROOT / VALIDATOR_PATH).read_bytes()
        # Two distinct candidate validators. Neither is ever imported or
        # executed; admission only ever hashes and compares their bytes.
        cls.successor = cls.live_validator + b"\n# staged successor v1\n"
        cls.impostor = cls.live_validator + b"\n# not the staged successor\n"

        workflow = (ROOT / ".github/workflows/candidate-admission.yml").read_bytes()
        cls.authority = BaseAuthority(
            base_sha="a" * 40,
            validator_blob_oid=git_blob_oid(cls.live_validator),
            validator_sha256=hashlib.sha256(cls.live_validator).hexdigest(),
            workflow_blob_oid=git_blob_oid(workflow),
            workflow_sha256=hashlib.sha256(workflow).hexdigest(),
        )

        blobs: dict[str, bytes] = {}
        entries: dict[bytes, tuple[str, str]] = {}

        def add(path: str, content: bytes, mode: str = "100644") -> None:
            oid = git_blob_oid(content)
            blobs[oid] = content
            entries[path.encode()] = (mode, oid)

        for path in SOURCE_BASELINE:
            add(path, (ROOT / path).read_bytes())
        for path in ARTIFACT_BASELINE:
            add(path, (ROOT / path).read_bytes())
        for path, bundle in WORKFLOW_TRANSITION_BUNDLES.items():
            add(path, (ROOT / bundle).read_bytes())
        for path, baseline in PROOF_CLOSURE_BASELINE.items():
            source = ROOT / path
            content = (
                source.readlink().as_posix().encode()
                if baseline.mode == "120000"
                else source.read_bytes()
            )
            add(path, content, baseline.mode)
        for path in PYTHON_PATHS:
            if path.encode() not in entries:
                add(path, (ROOT / path).read_bytes())
        add(DECLARATION_PATH, (ROOT / DECLARATION_PATH).read_bytes())

        cls.base_blobs = blobs
        cls.base_entries = entries
        cls.base_declaration = json.loads(
            (ROOT / DECLARATION_PATH).read_text(encoding="utf-8")
        )

    # -- snapshot construction -------------------------------------------

    def snapshot(
        self,
        *,
        validator: bytes | None = None,
        staged: bytes | None = None,
        sources: dict[str, bytes] | None = None,
        tamper: dict[str, bytes] | None = None,
    ):
        """Return (entries, blobs) for one self-consistent candidate tree.

        `validator` replaces the live validator bytes, `staged` places a
        staged successor file in the candidate tree, `sources` replaces other
        declared source paths, and `tamper` rewrites path bytes WITHOUT
        updating the declaration, which is how a hostile candidate looks.
        """
        entries = dict(self.base_entries)
        blobs = dict(self.base_blobs)
        declaration = json.loads(json.dumps(self.base_declaration))

        def place(path: str, content: bytes, declare: bool) -> None:
            oid = git_blob_oid(content)
            blobs[oid] = content
            entries[path.encode()] = ("100644", oid)
            if declare:
                declaration["sources"][path] = hashlib.sha256(content).hexdigest()
                if path not in declaration["python_paths"]:
                    declaration["python_paths"] = sorted(
                        declaration["python_paths"] + [path]
                    )

        if validator is not None:
            place(VALIDATOR_PATH, validator, declare=True)
        for path, content in (sources or {}).items():
            place(path, content, declare=True)
        if staged is not None:
            place(STAGED_SUCCESSOR_PATH, staged, declare=True)

        rendered = (
            json.dumps(declaration, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        oid = git_blob_oid(rendered)
        blobs[oid] = rendered
        entries[DECLARATION_PATH.encode()] = ("100644", oid)

        for path, content in (tamper or {}).items():
            oid = git_blob_oid(content)
            blobs[oid] = content
            entries[path.encode()] = ("100644", oid)
        return entries, blobs

    def raw_stage(self, entries) -> bytes:
        return b"".join(
            mode.encode() + b" " + oid.encode() + b" 0\t" + path + b"\0"
            for path, (mode, oid) in sorted(entries.items())
        )

    def prove(self, entries, blobs, staged_successor: bytes | None):
        return validate_candidate(
            raw_records=self.raw_stage(entries),
            record_format="stage-v1",
            blobs=blobs,
            authority=self.authority,
            staged_successor=staged_successor,
        )

    def assert_tree_is_locally_clean(self, entries, blobs) -> None:
        """Pin a rejection to the validator clause, not to declaration drift."""
        by_path = {
            path: GitRecord(mode, oid, path) for path, (mode, oid) in entries.items()
        }
        findings, _ = _verify_local(GitRecordTreeView(by_path, blobs))
        self.assertEqual(findings, (), "candidate tree must be internally consistent")

    # -- O1 green path ----------------------------------------------------

    def test_promotion_to_base_staged_successor_is_admitted(self) -> None:
        """O1: staged grant + exact successor bytes + grant spent -> admitted."""
        entries, blobs = self.snapshot(validator=self.successor)
        self.assertNotIn(STAGED_SUCCESSOR_PATH.encode(), entries)

        report = self.prove(entries, blobs, staged_successor=self.successor)

        self.assertTrue(report.passed, report.findings)
        self.assertEqual(report.findings, ())

    # -- O2 tampered promotion -------------------------------------------

    def test_validator_matching_neither_baseline_nor_grant_is_rejected(self) -> None:
        """O2: a grant exists, but these are not the pre-authorized bytes."""
        entries, blobs = self.snapshot(validator=self.impostor)
        self.assertNotEqual(self.impostor, self.successor)
        self.assertNotEqual(self.impostor, self.live_validator)
        self.assert_tree_is_locally_clean(entries, blobs)

        report = self.prove(entries, blobs, staged_successor=self.successor)

        self.assertFalse(report.passed)
        self.assertIn(ADMISSION_FINDING, report.findings)

    # -- O3 no grant staged ----------------------------------------------

    def test_validator_change_without_a_base_grant_is_rejected(self) -> None:
        """O3: without a base-staged successor the path cannot be entered."""
        entries, blobs = self.snapshot(validator=self.successor)
        self.assert_tree_is_locally_clean(entries, blobs)

        report = self.prove(entries, blobs, staged_successor=None)

        self.assertFalse(report.passed)
        self.assertIn(ADMISSION_FINDING, report.findings)

    # -- O4 grant not spent ----------------------------------------------

    def test_promotion_that_leaves_the_grant_staged_is_rejected(self) -> None:
        """O4: correct successor bytes, but the staged file is not deleted."""
        entries, blobs = self.snapshot(
            validator=self.successor, staged=self.successor
        )
        self.assertIn(STAGED_SUCCESSOR_PATH.encode(), entries)
        self.assert_tree_is_locally_clean(entries, blobs)

        report = self.prove(entries, blobs, staged_successor=self.successor)

        self.assertFalse(report.passed)
        self.assertIn(ADMISSION_FINDING, report.findings)

    def test_promotion_cannot_restage_a_new_grant_in_the_same_candidate(self) -> None:
        """A promotion that re-stages different successor bytes is rejected."""
        entries, blobs = self.snapshot(
            validator=self.successor, staged=self.impostor
        )
        self.assert_tree_is_locally_clean(entries, blobs)

        report = self.prove(entries, blobs, staged_successor=self.successor)

        self.assertFalse(report.passed)
        self.assertIn(ADMISSION_FINDING, report.findings)

    # -- O5 no regression --------------------------------------------------

    def test_ordinary_source_change_still_passes(self) -> None:
        """O5a: a non-validator source change is admitted, grant or not."""
        changed = (ROOT / "tools/aec_coach.py").read_bytes() + b"\n# candidate\n"
        entries, blobs = self.snapshot(sources={"tools/aec_coach.py": changed})

        for grant in (None, self.successor):
            with self.subTest(grant=grant is not None):
                report = self.prove(entries, blobs, staged_successor=grant)
                self.assertTrue(report.passed, report.findings)

    def test_staging_a_successor_is_an_ordinary_admissible_change(self) -> None:
        """O5b: PR 1 stages the successor and passes under unchanged rules."""
        entries, blobs = self.snapshot(staged=self.successor)

        report = self.prove(entries, blobs, staged_successor=None)

        self.assertTrue(report.passed, report.findings)

    def test_frozen_path_tamper_still_fails_even_during_a_promotion(self) -> None:
        """O5c: the grant relaxes nothing outside the validator identity."""
        entries, blobs = self.snapshot(
            validator=self.successor,
            tamper={"tools/aec_coach.py": b"# undeclared tamper\n"},
        )

        report = self.prove(entries, blobs, staged_successor=self.successor)

        self.assertFalse(report.passed)
        self.assertIn(ADMISSION_FINDING, report.findings)

    def test_workflow_identity_is_unaffected_by_a_grant(self) -> None:
        """A grant must not let a candidate move the active workflow."""
        entries, blobs = self.snapshot(validator=self.successor)
        content = (ROOT / ".github/workflows/candidate-admission.yml").read_bytes()
        rogue = content + b"\n# rogue\n"
        oid = git_blob_oid(rogue)
        blobs[oid] = rogue
        entries[b".github/workflows/candidate-admission.yml"] = ("100644", oid)

        report = self.prove(entries, blobs, staged_successor=self.successor)

        self.assertFalse(report.passed)
        self.assertIn(ADMISSION_FINDING, report.findings)


class StagedGrantResolutionTests(unittest.TestCase):
    """Prove the grant itself fails closed and is declaration-bound."""

    def declaration(self, **sources: str):
        raw = json.loads(
            (ROOT / DECLARATION_PATH).read_text(encoding="utf-8")
        )
        raw["sources"].update(sources)
        if sources:
            raw["python_paths"] = sorted(set(raw["python_paths"]) | set(sources))
        return parse_declaration(
            (json.dumps(raw, ensure_ascii=False, sort_keys=True) + "\n").encode()
        )

    def test_absent_staged_file_is_no_grant(self) -> None:
        self.assertIsNone(load_staged_successor(ROOT, self.declaration()))

    def test_repository_ships_no_open_grant(self) -> None:
        """A grant is exceptional state; main must not carry one by default."""
        self.assertFalse((ROOT / STAGED_SUCCESSOR_PATH).exists())

    def test_staged_file_not_matching_its_declared_digest_is_no_grant(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / "tools").mkdir()
            (root / STAGED_SUCCESSOR_PATH).write_bytes(b"# successor\n")
            declared = self.declaration(**{STAGED_SUCCESSOR_PATH: "0" * 64})
            self.assertIsNone(load_staged_successor(root, declared))

            honest = self.declaration(
                **{
                    STAGED_SUCCESSOR_PATH: hashlib.sha256(b"# successor\n").hexdigest()
                }
            )
            self.assertEqual(
                load_staged_successor(root, honest), b"# successor\n"
            )


if __name__ == "__main__":
    unittest.main()
