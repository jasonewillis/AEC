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
    DECLARATION_PATH,
    STAGED_SUCCESSOR_PATH,
    VALIDATOR_PATH,
    BaseAuthority,
    FilesystemTreeView,
    GitRecord,
    GitRecordTreeView,
    _verify_local,
    derive_promotion_declaration,
    git_blob_oid,
    load_staged_successor,
    parse_declaration,
    render_declaration,
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

        # The candidate snapshot is the WHOLE tracked tree, exactly as CI
        # supplies it (`git ls-tree -r --full-tree`), not just the paths the
        # declaration binds. Promotion minimality is judged over every tracked
        # path, so a partial snapshot would look like a mass deletion.
        base_view = FilesystemTreeView(ROOT)
        for raw_path in base_view.paths():
            entry = base_view.get(raw_path)
            assert entry is not None, raw_path
            oid = git_blob_oid(entry.content)
            blobs[oid] = entry.content
            entries[raw_path] = (entry.mode, oid)

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
        workflows: dict[str, bytes] | None = None,
        undeclared: dict[str, bytes] | None = None,
        deletes: tuple[str, ...] = (),
        tamper: dict[str, bytes] | None = None,
        declaration_edit=None,
        declaration_render=None,
    ):
        """Return (entries, blobs) for one self-consistent candidate tree.

        `validator` replaces the live validator bytes, `staged` places a
        staged successor file in the candidate tree, `sources` replaces other
        declared source paths, `workflows` replaces a workflow and restates
        its declared digest, `undeclared` places paths the declaration is not
        required to cover at all, `deletes` removes paths, and `tamper`
        rewrites path bytes WITHOUT updating the declaration, which is how a
        hostile candidate looks. `declaration_edit` mutates the declaration
        payload in place after every other section is settled, and
        `declaration_render` replaces the canonical serializer, which is how a
        candidate smuggles content or formatting into the declaration itself.
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
        for path, content in (workflows or {}).items():
            oid = git_blob_oid(content)
            blobs[oid] = content
            entries[path.encode()] = ("100644", oid)
            declaration["workflows"][path] = hashlib.sha256(content).hexdigest()
        for path, content in (undeclared or {}).items():
            oid = git_blob_oid(content)
            blobs[oid] = content
            entries[path.encode()] = ("100644", oid)
        for path in deletes:
            entries.pop(path.encode(), None)

        if declaration_edit is not None:
            declaration_edit(declaration)
        serialize = declaration_render or (
            lambda payload: (
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
        )
        rendered = serialize(declaration)
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

    # -- promotion minimality ---------------------------------------------

    def test_promotion_cannot_plant_an_alternate_staging_path(self) -> None:
        """The re-staging block must not be escapable by renaming the grant.

        Deleting the canonical staged path while ADDING a second, candidate-
        controlled staging file was admitted before promotion minimality
        existed. If the promoted validator reads its grant from that added
        path, one promotion installs a candidate-controlled grant and the next
        pull request can promote arbitrary bytes. The tree is locally clean,
        so only the minimality clause can reject it.
        """
        alternate = "tools/admission_root_next_v2.py"
        entries, blobs = self.snapshot(
            validator=self.successor, sources={alternate: self.impostor}
        )
        self.assertNotIn(STAGED_SUCCESSOR_PATH.encode(), entries)
        self.assertIn(alternate.encode(), entries)
        self.assert_tree_is_locally_clean(entries, blobs)

        report = self.prove(entries, blobs, staged_successor=self.successor)

        self.assertFalse(report.passed)
        self.assertIn(ADMISSION_FINDING, report.findings)

    def test_promotion_cannot_add_an_undeclared_path(self) -> None:
        """Minimality is generic, not a blacklist of known staging names.

        A planted path the declaration is not required to cover at all - no
        .py, .json, or workflow suffix - is outside every digest section, so
        nothing but the change-set comparison can see it.
        """
        entries, blobs = self.snapshot(
            validator=self.successor,
            undeclared={"tools/successor-grant.bin": self.impostor},
        )
        self.assert_tree_is_locally_clean(entries, blobs)

        report = self.prove(entries, blobs, staged_successor=self.successor)

        self.assertFalse(report.passed)
        self.assertIn(ADMISSION_FINDING, report.findings)

    def test_promotion_cannot_carry_an_unrelated_source_change(self) -> None:
        """A promotion is a mechanical replacement; it may edit nothing else.

        The same edit is admitted on its own (see the ordinary-source-change
        test below), which is what makes this a minimality finding rather than
        an incidental one.
        """
        changed = (ROOT / "tools/aec_coach.py").read_bytes() + b"\n# smuggled\n"
        entries, blobs = self.snapshot(
            validator=self.successor, sources={"tools/aec_coach.py": changed}
        )
        self.assert_tree_is_locally_clean(entries, blobs)

        report = self.prove(entries, blobs, staged_successor=self.successor)

        self.assertFalse(report.passed)
        self.assertIn(ADMISSION_FINDING, report.findings)

    def test_promotion_cannot_delete_an_unrelated_path(self) -> None:
        """Only the spent grant may disappear in a promotion."""
        entries, blobs = self.snapshot(validator=self.successor, deletes=("LICENSE",))
        self.assertNotIn(b"LICENSE", entries)
        self.assert_tree_is_locally_clean(entries, blobs)

        report = self.prove(entries, blobs, staged_successor=self.successor)

        self.assertFalse(report.passed)
        self.assertIn(ADMISSION_FINDING, report.findings)

    # -- declaration derivation -------------------------------------------

    def test_promotion_cannot_smuggle_a_payload_in_declaration_metadata(self) -> None:
        """The declaration is not exempt; it is derived byte-for-byte.

        Replay of the round-2 finding. `artifacts[*].closed_class` is free
        text no other admission check constrains, and the declaration was
        exempt from the base comparison because its digests legitimately move.
        A 416-character candidate-chosen payload therefore rode through a
        promotion with no findings at all. The promoted validator can read the
        declaration, so that payload is a next grant.
        """
        payload = ("GRANT:" + "Zq7" * 137)[:416]
        self.assertEqual(len(payload), 416)

        def smuggle(declaration: dict) -> None:
            target = sorted(declaration["artifacts"])[0]
            declaration["artifacts"][target] = [
                payload,
                declaration["artifacts"][target][1],
            ]

        entries, blobs = self.snapshot(
            validator=self.successor, declaration_edit=smuggle
        )
        self.assert_tree_is_locally_clean(entries, blobs)

        report = self.prove(entries, blobs, staged_successor=self.successor)

        self.assertFalse(report.passed)
        self.assertIn(ADMISSION_FINDING, report.findings)

    def test_promotion_declaration_must_match_byte_for_byte_not_semantically(
        self,
    ) -> None:
        """Formatting alone carries data, so equality must be at the bytes.

        Same declaration content, different serialization: 4-space indent and
        unsorted keys. A semantically-equal comparison would admit this, and
        whitespace and key order are enough to encode an arbitrary payload.
        """
        entries, blobs = self.snapshot(
            validator=self.successor,
            declaration_render=lambda payload: (
                json.dumps(payload, ensure_ascii=False, indent=4, sort_keys=False)
                + "\n"
            ).encode("utf-8"),
        )
        self.assert_tree_is_locally_clean(entries, blobs)
        honest, _ = self.snapshot(validator=self.successor)
        self.assertNotEqual(
            entries[DECLARATION_PATH.encode()], honest[DECLARATION_PATH.encode()]
        )

        report = self.prove(entries, blobs, staged_successor=self.successor)

        self.assertFalse(report.passed)
        self.assertIn(ADMISSION_FINDING, report.findings)

    def test_derivation_drops_the_spent_grant_from_the_declaration(self) -> None:
        """The derivation removes every section entry keyed on the grant.

        The live base ships no staged file, so this exercises the shape a real
        base-with-a-grant has: the staged path is declared in `sources` and
        `python_paths`, the promotion deletes the file, and the derived
        declaration must therefore no longer mention it anywhere.
        """
        staged_declaration = json.loads(json.dumps(self.base_declaration))
        staged_declaration["sources"][STAGED_SUCCESSOR_PATH] = hashlib.sha256(
            self.successor
        ).hexdigest()
        staged_declaration["python_paths"] = sorted(
            staged_declaration["python_paths"] + [STAGED_SUCCESSOR_PATH]
        )
        base_raw = render_declaration(staged_declaration)

        derived = derive_promotion_declaration(base_raw, self.successor)

        self.assertIsNotNone(derived)
        rebuilt = json.loads(derived.decode("utf-8"))
        self.assertNotIn(STAGED_SUCCESSOR_PATH, rebuilt["sources"])
        self.assertNotIn(STAGED_SUCCESSOR_PATH, rebuilt["python_paths"])
        self.assertEqual(
            rebuilt["sources"][VALIDATOR_PATH],
            hashlib.sha256(self.successor).hexdigest(),
        )
        # Nothing else moved.
        expected = json.loads(json.dumps(self.base_declaration))
        expected["sources"][VALIDATOR_PATH] = hashlib.sha256(
            self.successor
        ).hexdigest()
        self.assertEqual(rebuilt, expected)

    def test_derivation_refuses_a_non_canonical_base_declaration(self) -> None:
        """Fail closed when "base bytes plus the transformation" is ambiguous."""
        padded = (
            json.dumps(self.base_declaration, ensure_ascii=False, indent=4) + "\n"
        ).encode("utf-8")

        self.assertIsNone(derive_promotion_declaration(padded, self.successor))

    def test_validator_render_matches_the_declaration_generator(self) -> None:
        """The canonical writer is duplicated in two files; pin them together.

        tools/admission_root_v1.py cannot import the generator (the generator
        imports it, and the validator runs as a script from a checkout where
        `tools` is not an importable package), so the serializer is written
        twice. If they ever drift, an honest promotion's declaration stops
        matching the derivation and the promotion path silently bricks.
        """
        from tools.generate_source_declaration import render

        self.assertEqual(
            render_declaration(self.base_declaration),
            render(self.base_declaration).encode("utf-8"),
        )
        self.assertEqual(
            render_declaration(self.base_declaration),
            (ROOT / DECLARATION_PATH).read_bytes(),
        )

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
        """A grant must not let a candidate move the active workflow.

        Deliberately NOT a promotion: the validator is left at the baseline, so
        the promotion-minimality clause never runs and the base-owned workflow
        blob identity is the ONLY thing that can reject this tree. The
        declaration is regenerated for the rogue workflow bytes too, so
        `_verify_local` is clean and cannot reject on a stale digest. An
        earlier version of this test skipped that regeneration and therefore
        passed for the wrong reason: it stayed green even with the
        workflow-authority guard deleted.
        """
        content = (ROOT / ".github/workflows/candidate-admission.yml").read_bytes()
        entries, blobs = self.snapshot(
            workflows={
                ".github/workflows/candidate-admission.yml": content + b"\n# rogue\n"
            }
        )
        self.assert_tree_is_locally_clean(entries, blobs)

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
