"""Red-first proof: generator refuses an unmerged index instead of corrupting.

Pins the bug in issue #74: `tools/generate_source_declaration.py` derived its
path list from `git ls-files -- '*.py'`, which emits a conflicted path once
per merge stage. That produced a `python_paths` list with duplicates, which
`tools/admission_root_v1.py::parse_declaration` rejects at import time -- and
`--check` compared the corrupt output against itself, so it reported
"PASS source declaration is current" on the broken state.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DECLARATION_RELATIVE_PATH = Path(".github/admission/v1/source-declaration.json")
GENERATOR = ROOT / "tools" / "generate_source_declaration.py"
CONFLICT_PATH = "aec/mentor.py"


class UnmergedIndexGeneratorTests(unittest.TestCase):
    """Prove the generator and its --check both refuse an unmerged index."""

    def _cloned_root(self) -> Path:
        clone = Path(self.enterContext(tempfile.TemporaryDirectory())) / "clone"
        subprocess.run(
            ["git", "clone", "--quiet", "--local", str(ROOT), str(clone)],
            check=True,
        )
        return clone

    def _make_index_unmerged(self, root: Path, path: str) -> None:
        """Stage `path` at conflict stages 1/2/3, as a real unresolved merge does."""
        blob = subprocess.run(
            ["git", "hash-object", "-w", str(root / path)],
            cwd=root,
            check=True,
            capture_output=True,
        ).stdout.decode().strip()
        index_info = "".join(
            f"100644 {blob} {stage}\t{path}\n" for stage in (1, 2, 3)
        )
        subprocess.run(
            ["git", "update-index", "--index-info"],
            cwd=root,
            input=index_info.encode("utf-8"),
            check=True,
        )

    def test_unmerged_index_is_refused_by_both_generate_and_check(self) -> None:
        """Pins both halves of #74 in one repo state: writing and --check."""
        root = self._cloned_root()
        declaration_path = root / DECLARATION_RELATIVE_PATH
        original = declaration_path.read_bytes()
        self._make_index_unmerged(root, CONFLICT_PATH)

        generate_result = subprocess.run(
            [sys.executable, str(GENERATOR)],
            cwd=root,
            capture_output=True,
            text=True,
        )
        check_result = subprocess.run(
            [sys.executable, str(GENERATOR), "--check"],
            cwd=root,
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(0, generate_result.returncode)
        self.assertIn("unmerged", generate_result.stdout.lower())
        self.assertEqual(
            original,
            declaration_path.read_bytes(),
            "generator must not overwrite the declaration while the index is unmerged",
        )
        self.assertNotEqual(0, check_result.returncode)
        self.assertNotIn("PASS", check_result.stdout)


if __name__ == "__main__":
    unittest.main()
