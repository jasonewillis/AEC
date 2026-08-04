"""Every documentation path this repository names must resolve.

Moving a document is a silent operation: nothing in the test suite noticed that
the consumer contract, before it moved under `docs/architecture/`, was
referenced from `README.md`, from two source comments, and from three sibling
documents at once. A relocation could rot all six references and every gate
would stay green, because the only control was a reader happening to click the
link.

The historical path is deliberately not spelled out above. This module is
itself scanned by the second test below, so naming a since-moved path here
would red the suite — which is the control working, and is exactly how this
docstring was caught: the first green run happened while this file was still
untracked, so `git ls-files` excluded it and it could not see itself.

This is that control. It walks the tracked tree and resolves two reference
classes:

* Markdown inline links, `[text](target)`, excluding external schemes.
* Bare `docs/...` mentions inside Python source, which is how prose comments
  point at contracts. These rot the most quietly of all, because no renderer
  ever tries to follow them.

It deliberately claims nothing about link *accuracy* — a link may resolve and
still point somewhere useless. It pins existence only, which is the failure
mode a file move actually causes.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# `](target)` with the target captured up to the closing paren. Markdown does
# not allow an unescaped `)` inside a bare target, so this is exact for the
# link style this repository uses.
MARKDOWN_LINK = re.compile(r"\]\(([^)\s]+)\)")

# A `docs/...` path mentioned in prose or code, ending in a real file suffix.
# Restricted to `.md` and `.py` so that directory-shaped mentions such as
# `docs/AI Engineer Course/` are not read as files.
PYTHON_DOCS_MENTION = re.compile(r"docs/[\w./-]+\.(?:md|py)")

EXTERNAL_SCHEMES = ("http://", "https://", "mailto:", "#")


def tracked_files(suffix: str) -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", f"*{suffix}"],
        check=True,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return [ROOT / line for line in result.stdout.splitlines() if line]


def resolve(reference: str, source: Path) -> bool:
    """True when `reference`, written inside `source`, names a real path.

    A reference is tried against the referring file's own directory first and
    the repository root second. Both are legitimate in this tree: sibling
    documents link relatively, while `README.md` and source comments spell the
    full `docs/...` path from the root.
    """
    target = reference.split("#", 1)[0]
    if not target:
        return True
    return (source.parent / target).exists() or (ROOT / target).exists()


class DocumentationLinkTests(unittest.TestCase):
    def test_every_markdown_link_resolves(self) -> None:
        broken: list[str] = []
        for document in tracked_files(".md"):
            text = document.read_text(encoding="utf-8")
            for reference in MARKDOWN_LINK.findall(text):
                if reference.startswith(EXTERNAL_SCHEMES):
                    continue
                if not resolve(reference, document):
                    broken.append(f"{document.relative_to(ROOT)} -> {reference}")

        self.assertEqual(
            [],
            broken,
            "markdown links naming paths that do not exist:\n" + "\n".join(broken),
        )

    def test_every_docs_path_named_in_python_source_resolves(self) -> None:
        broken: list[str] = []
        for module in tracked_files(".py"):
            text = module.read_text(encoding="utf-8")
            for reference in PYTHON_DOCS_MENTION.findall(text):
                # An f-string template is a path shape, not a path.
                if "{" in reference:
                    continue
                if not (ROOT / reference).exists():
                    broken.append(f"{module.relative_to(ROOT)} -> {reference}")

        self.assertEqual(
            [],
            broken,
            "python source names documentation paths that do not exist:\n"
            + "\n".join(broken),
        )


if __name__ == "__main__":
    unittest.main()
