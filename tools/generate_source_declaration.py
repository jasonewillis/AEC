#!/usr/bin/env python3
"""Regenerate the candidate source declaration from the working tree.

Recomputes `python_paths` and `sources` from the git-tracked .py files admission
actually treats as source (see the `tracked_python` predicate in
tools/admission_root_v1.py). Every other section (`artifacts`, `proof_closure`,
`workflows`, `workflow_bundles`, `schema_version`) carries human-assigned
metadata that cannot be derived from tree structure alone (artifact
`closed_class` labels, symlink targets, which workflow bundles which), so
those are carried forward from the currently committed declaration unchanged.

Digests are computed exactly the way tools/admission_root_v1.py verifies a
`sources` entry: `hashlib.sha256(content).hexdigest()` over the raw file
bytes, at the default REGULAR_MODE. A path already covered by
`proof_closure` is left to that section and skipped here, so no path ever
carries two conflicting digests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DECLARATION_PATH = ROOT / ".github" / "admission" / "v1" / "source-declaration.json"


def tracked_python_paths() -> list[str]:
    """Return every git-tracked .py path admission's coverage clause requires.

    Mirrors the `tracked_python` predicate in validate_candidate: a .py path
    either has no directory component, or lives under aec/, tests/, or
    tools/.
    """
    output = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    paths = [entry for entry in output.decode("utf-8").split("\0") if entry]
    return sorted(
        path
        for path in paths
        if "/" not in path or path.startswith(("aec/", "tests/", "tools/"))
    )


def build_declaration() -> dict:
    """Recompute sources and python_paths; keep every other section pinned."""
    current = json.loads(DECLARATION_PATH.read_text(encoding="utf-8"))
    proof_closure_paths = set(current["proof_closure"])
    python_paths = tracked_python_paths()
    sources = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in python_paths
        if path not in proof_closure_paths
    }
    declaration = dict(current)
    declaration["python_paths"] = python_paths
    declaration["sources"] = sources
    return declaration


def render(declaration: dict) -> str:
    """Render the declaration exactly as it is committed: sorted, 2-space."""
    return (
        json.dumps(declaration, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def main(argv: list[str] | None = None) -> int:
    """Write the regenerated declaration, or check the committed copy is current."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args(argv)
    rendered = render(build_declaration())
    if arguments.check:
        if not DECLARATION_PATH.exists():
            print(f"FAIL missing source declaration: {DECLARATION_PATH}")
            return 1
        if DECLARATION_PATH.read_text(encoding="utf-8") != rendered:
            print("FAIL source declaration is stale")
            return 1
        print("PASS source declaration is current")
        return 0
    DECLARATION_PATH.write_text(rendered, encoding="utf-8")
    print(f"WROTE {DECLARATION_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
