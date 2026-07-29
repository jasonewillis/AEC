"""In-tree port of the adversarial replay corpus cited as O2 evidence in PR #64.

PR #64's Review Evidence section reported a five-case corpus run (1 positive
control, 4 rejections) via a driver script that was never committed to the
repository, so nobody reading the PR from a fresh clone could re-run it
(issue #67). This file is that corpus, ported to unittest so it lives inside
the declared source set and runs in CI like everything else.

The defining property of the original corpus, preserved here: every attack
tree is rebuilt ON the commit under test. Each test clones ROOT (the actual
checked-out worktree HEAD, whatever commit that happens to be), regenerates
the declaration's python_paths/sources directly from that clone's own
git-tracked .py files, commits that clean baseline, and only THEN applies
its tampering. An attack tree built against a stale, hand-typed baseline
would be rejected for declaration staleness rather than for the tampering
under test, which is a satisfying FAIL that proves nothing about the clause
being exercised.

The regeneration logic here is deliberately self-contained rather than a
call to `tools.generate_source_declaration` (the in-tree regenerator). That
tool is itself SUT-owned source, introduced by the same PR (#64) this corpus
is meant to independently exercise, and did not exist at all before it - a
corpus that shells out to it cannot run against commits that predate it,
which defeats mutation-verification against a pre-fix commit. The original
out-of-tree driver was independent of the tree it tested for the same
reason; this keeps that property.

Case list (mirrors PR #64's reported table exactly):

    O1  legit change + regenerated declaration      -> PASS (positive control)
    A1  tamper + drop digest from declaration        -> FAIL
    B   empty declaration + tamper two files          -> FAIL
    A4  tamper, no declaration edit                   -> FAIL
    A3  new undeclared .py file                        -> FAIL

The O1 positive control is load-bearing on its own: without it, a validator
that rejected every tree unconditionally would sweep all four attacks and
look flawless. A3 has no synthetic (non-cloned) equivalent elsewhere in this
suite because the coverage clause it exercises depends on `git ls-files`
seeing a path that genuinely was not there at the last commit — dropping an
entry from an otherwise-real declaration is the mirror image of that input,
not the same one.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.admission_root_v1 import DECLARATION_PATH, self_check


ROOT = Path(__file__).resolve().parents[1]


class AdmissionAttackCorpusTests(unittest.TestCase):
    """Five-case adversarial replay corpus, rebuilt on the commit under test."""

    def _cloned_root(self) -> Path:
        """Clone ROOT at its current HEAD into a disposable temp directory.

        self_check reads real files via a real `git ls-files`/working tree,
        so it needs an actual checkout, not in-memory data. Cloning (rather
        than mutating ROOT in place) means every case rebuilds independently
        against the exact commit under test without ever touching the real
        repository.
        """
        clone = Path(self.enterContext(tempfile.TemporaryDirectory())) / "clone"
        subprocess.run(
            ["git", "clone", "--quiet", "--local", str(ROOT), str(clone)],
            check=True,
        )
        return clone

    @staticmethod
    def _git(root: Path, *args: str) -> None:
        subprocess.run(["git", "-C", str(root), *args], check=True)

    @classmethod
    def _commit_all(cls, root: Path, message: str) -> None:
        """Stage and commit everything, even if regeneration produced no
        diff (e.g. the clean-baseline step when the declaration was already
        current) - an empty commit still advances history, which is all
        these tests need."""
        cls._git(root, "add", "-A")
        subprocess.run(
            ["git", "-C", str(root), "-c", "user.name=corpus",
             "-c", "user.email=corpus@corpus.invalid", "commit", "--quiet",
             "--allow-empty", "-m", message],
            check=True,
        )

    @staticmethod
    def _tracked_python_paths(root: Path) -> set[str]:
        """Reproduce admission's `tracked_python` predicate directly from
        `git ls-files`, independent of any in-tree helper."""
        listed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--", "*.py"],
            capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        return {
            path for path in listed
            if "/" not in path or path.startswith(("aec/", "tests/", "tools/"))
        }

    @classmethod
    def _regenerate_declaration(cls, root: Path) -> None:
        """Regenerate python_paths/sources from `root`'s own tree, the way a
        real PR does. This is what makes every case below built ON the
        commit under test rather than against a fixed, staling base.

        Computed independently of `tools.generate_source_declaration` (see
        module docstring) so this same logic runs unmodified against a
        pre-#64 commit that never shipped that tool.
        """
        declaration_path = root / DECLARATION_PATH
        payload = (
            json.loads(declaration_path.read_text(encoding="utf-8"))
            if declaration_path.exists() else {}
        )
        for key in ("artifacts", "proof_closure", "workflows", "workflow_bundles"):
            payload.setdefault(key, {})
        payload.setdefault("schema_version", 1)

        tracked = cls._tracked_python_paths(root)
        proof_closure = set(payload["proof_closure"])
        sources = {
            path: digest
            for path, digest in payload.get("sources", {}).items()
            if path not in tracked
        }
        for path in sorted(tracked - proof_closure):
            sources[path] = hashlib.sha256((root / path).read_bytes()).hexdigest()

        payload["python_paths"] = sorted(tracked)
        payload["sources"] = sources
        declaration_path.write_text(json.dumps(payload), encoding="utf-8")

    @staticmethod
    def _tamper(root: Path, relative_path: str, suffix: bytes) -> None:
        target = root / relative_path
        target.write_bytes(target.read_bytes() + suffix)

    @staticmethod
    def _load_declaration(root: Path) -> dict:
        return json.loads((root / DECLARATION_PATH).read_text(encoding="utf-8"))

    @staticmethod
    def _write_declaration(root: Path, payload: dict) -> None:
        (root / DECLARATION_PATH).write_text(json.dumps(payload), encoding="utf-8")

    # -- O1: legit change + regenerated declaration -> PASS ------------------

    def test_o1_legit_change_with_regenerated_declaration_passes(self) -> None:
        """Positive control. Without this, a reject-everything validator
        would sweep A1/B/A4/A3 below and look like a working gate."""
        root = self._cloned_root()
        self._tamper(root, "aec/mentor.py", b"\n# corpus O1: ordinary source change\n")
        self._regenerate_declaration(root)
        self._commit_all(root, "corpus O1: legit change + regenerated declaration")

        self.assertEqual((), self_check(root))

    # -- A1: tamper + drop digest from declaration -> FAIL -------------------

    def test_a1_tamper_and_drop_digest_from_declaration_fails(self) -> None:
        """Tamper a tracked file, then scrub its digest from the declaration
        instead of updating it. Simulates an attacker who edits content and
        launders the evidence by deleting the entry rather than fixing it -
        the declaration still lists the path in python_paths (it is still a
        tracked .py file) but no longer covers it with a digest anywhere."""
        root = self._cloned_root()
        self._regenerate_declaration(root)
        self._commit_all(root, "corpus A1: clean baseline")

        self._tamper(root, "aec/mentor.py", b"\n# corpus A1: tampered\n")
        payload = self._load_declaration(root)
        self.assertIn("aec/mentor.py", payload["sources"])
        del payload["sources"]["aec/mentor.py"]
        self._write_declaration(root, payload)
        self._commit_all(root, "corpus A1: tamper + drop digest")

        findings = self_check(root)
        # Pin the specific clause, not just "something failed": an unrelated
        # finding elsewhere (e.g. a workflow digest drift) could keep this
        # green after the coverage clause under test regresses, since the
        # tampered bytes are never actually checked once its digest is gone.
        self.assertIn("python_paths-coverage", findings)

    # -- B: empty declaration + tamper two files -> FAIL ----------------------

    def test_b_empty_declaration_with_two_tampered_files_fails(self) -> None:
        """Empty the declaration's coverage sections (sources, proof_closure)
        while leaving python_paths and the rest of the schema intact, then
        tamper two tracked files. An attacker betting that no digests means
        no evidence to contradict must still be rejected.

        Deliberately NOT a wholesale-empty declaration: wiping every section
        (including python_paths) makes the declaration schema-invalid, which
        self_check treats as a parse failure and falls back to this
        process's own trusted baseline - a real rejection, but for parse
        failure, not for the coverage gap this case means to exercise. This
        keeps the declaration valid so the failure is attributable to the
        actual clause under test.
        """
        root = self._cloned_root()
        self._regenerate_declaration(root)
        self._commit_all(root, "corpus B: clean baseline")

        self._tamper(root, "aec/mentor.py", b"\n# corpus B: tampered one\n")
        self._tamper(root, "aec/resolver.py", b"\n# corpus B: tampered two\n")
        payload = self._load_declaration(root)
        payload["sources"] = {}
        payload["proof_closure"] = {}
        self._write_declaration(root, payload)
        self._commit_all(root, "corpus B: empty coverage sections + tamper two files")

        findings = self_check(root)
        # Confirm the declaration still parsed (this is the coverage gap,
        # not a parse-failure fallback) and pin the specific clause.
        self.assertNotIn(DECLARATION_PATH, findings)
        self.assertIn("python_paths-coverage", findings)

    # -- A4: tamper, no declaration edit -> FAIL ------------------------------

    def test_a4_tamper_with_no_declaration_edit_fails(self) -> None:
        """The plain case: edit a tracked file's bytes and leave the
        (now-stale) declaration exactly as regenerated. The digest the
        declaration carries for that path no longer matches disk."""
        root = self._cloned_root()
        self._regenerate_declaration(root)
        self._commit_all(root, "corpus A4: clean baseline")

        self._tamper(root, "aec/mentor.py", b"\n# corpus A4: tampered, declaration untouched\n")
        self._commit_all(root, "corpus A4: tamper, no declaration edit")

        findings = self_check(root)
        self.assertNotEqual((), findings)
        self.assertIn("aec/mentor.py", findings)

    # -- A3: new undeclared .py file -> FAIL ----------------------------------

    def test_a3_new_undeclared_python_file_fails(self) -> None:
        """Add a genuinely NEW tracked .py file after the declaration was
        regenerated, and never declare it. Every attack above simulates an
        undeclared file by DROPPING an entry from the declaration, which is
        the mirror image of this input, not the same one: a validator that
        only iterates the declaration and checks each entry against disk
        passes those while never noticing a file that only disk has.
        Coverage has to be driven from the tree (`git ls-files`), not from
        the declaration, to catch this one."""
        root = self._cloned_root()
        self._regenerate_declaration(root)
        self._commit_all(root, "corpus A3: clean baseline")

        new_file = root / "aec" / "_corpus_a3_new.py"
        new_file.write_text("VALUE = 'corpus A3: new undeclared file'\n", encoding="utf-8")
        self._git(root, "add", "aec/_corpus_a3_new.py")
        self._commit_all(root, "corpus A3: new undeclared .py")

        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "aec/_corpus_a3_new.py"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        self.assertEqual("aec/_corpus_a3_new.py", tracked)
        declaration = self._load_declaration(root)
        self.assertNotIn("aec/_corpus_a3_new.py", declaration.get("python_paths", []))

        findings = self_check(root)
        # Pin the specific clause: python_paths set-equality is what has to
        # notice a tree-only addition, since nothing else in _verify_local
        # ever inspects a path the declaration doesn't already know about.
        self.assertIn("python_paths", findings)


if __name__ == "__main__":
    unittest.main()
