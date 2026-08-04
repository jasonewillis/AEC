#!/usr/bin/env python3
"""Regenerate the candidate source declaration from the working tree.

Recomputes `python_paths` and `sources` from the git-tracked .py files admission
actually treats as source (see the `tracked_python` predicate in
tools/admission_root_v1.py). Every other section (`artifacts`, `behavior`,
`proof_closure`, `workflows`, `workflow_bundles`, `schema_version`) carries
human-assigned metadata that cannot be derived from tree structure alone
(artifact `closed_class` labels, symlink targets, which workflow bundles
which, the resolver behavior aggregate), so those are carried forward from
the currently committed declaration unchanged.

`behavior.identity` and `behavior.trust_root_lock_identity` (issue #65) are
hand-maintained like `artifacts`/`proof_closure`, but unlike those two this
tool does not detect their drift: they are not a digest of one file's bytes,
so `declared_digest_drift` below has nothing to re-hash them against. Their
correctness is instead pinned by
`tests/test_resolver_blocker_precedence.py::test_blocker_decisions_extend_the_frozen_behavior_identity`,
which recomputes `behavior.identity` from live resolver output, and by
`self_check`'s trust-root-lock check, which recomputes
`behavior.trust_root_lock_identity` from the declaration's own declared
`behavior.identity` plus the validator's structural constants.

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
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.admission_root_v1 import parse_declaration  # noqa: E402


DECLARATION_PATH = ROOT / ".github" / "admission" / "v1" / "source-declaration.json"


class UnmergedIndexError(RuntimeError):
    """Raised when the git index holds unresolved merge conflicts."""


def unmerged_paths() -> list[str]:
    """Return tracked paths that currently have unresolved merge conflicts.

    During an unmerged (conflicted) index, `git ls-files -u` emits one line
    per conflict stage (ours/theirs/base) for each conflicted path, in the
    format `<mode> <object> <stage>\\t<path>`. A plain `git ls-files -- '*.py'`
    then yields that same path once per stage, so callers deriving a path
    list from it get silent duplicates instead of a clean error.
    """
    output = subprocess.run(
        ["git", "ls-files", "-z", "--unmerged"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    entries = [entry for entry in output.decode("utf-8").split("\0") if entry]
    paths = set()
    for entry in entries:
        _, _, path = entry.partition("\t")
        if path:
            paths.add(path)
    return sorted(paths)


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


def undeclared_untracked_python() -> list[str]:
    """Return non-ignored, untracked .py paths this declaration cannot see.

    `tracked_python` enumerates with `git ls-files`, so a .py file that exists
    but has never been staged is invisible to it. `--check` would then print
    "source declaration is current" while a file that changes `python_paths`
    the moment it is added sits in the tree.

    That is not hypothetical. Both `Foundation gate` failures on 2026-08-03
    were the identical assertion, `Tuples differ: () != ('python_paths',)`,
    from exactly this: a local run reported green, `git add` followed, and CI
    red on the same content. There was no local signal at all, because the two
    checks that could have spoken -- this one and `self_check` -- both
    enumerate from the index and were structurally blind to the file.

    `--exclude-standard` is deliberate: a genuinely ignored scratch file is not
    a hazard, because it will never enter the declaration. An untracked,
    non-ignored .py is, because the next `git add -A` puts it there.
    """
    output = subprocess.run(
        ["git", "ls-files", "-z", "--others", "--exclude-standard", "--", "*.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return sorted(
        path
        for path in output.decode("utf-8").split("\0")
        if path and ("/" not in path or path.startswith(("aec/", "tests/", "tools/")))
    )


def declared_digest_drift(declaration: dict) -> list[str]:
    """Report declared paths whose bytes no longer match their digest.

    `artifacts` and `proof_closure` carry human-assigned metadata, so this tool
    deliberately does not regenerate them -- that manual step IS the control.
    A candidate declares digests for files it must not be able to change
    silently, and auto-rewriting them would make tampering and a legitimate
    edit indistinguishable at the tool level.

    But not regenerating them is not the same as not *reporting* them. Before
    this check, editing a declared file surfaced later and elsewhere as

        AssertionError: Tuples differ: () != ('artifacts',)

    from `self_check`, which names the section and not the path. Four times on
    2026-08-03/04 that cost a diagnosis detour, and once it did real damage: an
    invariant-sweep mutation left a stale artifact digest, `setUpClass` errored,
    the error was read as noise rather than as the run being invalid, and a
    guarded invariant was reported as UNGUARDED. A false finding nearly became
    a pull request.

    So this names the path and the digest to paste, and still refuses to write
    it. `self_check` remains the enforcing control; this is the diagnosis that
    reaches you first, because `--check` is in the documented done-list.
    """
    problems: list[str] = []
    for section in ("artifacts", "proof_closure"):
        for path, record in sorted(declaration.get(section, {}).items()):
            target = ROOT / path
            # Symlinks are declared by their target text, not their bytes, and
            # a directory has none; both are the owning section's business.
            if target.is_symlink() or not target.is_file():
                continue
            declared = record[1] if isinstance(record, list) else record.get("sha256")
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if declared != actual:
                problems.append(f"  {section}.{path}\n    declared {declared}\n    actual   {actual}")
    return problems


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

    conflicted = unmerged_paths()
    if conflicted:
        print(
            "FAIL git index has unmerged entries, refusing to generate: "
            + ", ".join(conflicted)
        )
        return 1

    rendered = render(build_declaration())
    if arguments.check:
        if not DECLARATION_PATH.exists():
            print(f"FAIL missing source declaration: {DECLARATION_PATH}")
            return 1
        committed = DECLARATION_PATH.read_text(encoding="utf-8")
        if committed != rendered:
            print("FAIL source declaration is stale")
            return 1
        try:
            parse_declaration(committed.encode("utf-8"))
        except ValueError as error:
            print(f"FAIL source declaration does not parse: {error}")
            return 1
        # A green here is a claim about the tree at merge, not about the working
        # directory. Untracked .py files make those two trees differ.
        drift = declared_digest_drift(json.loads(committed))
        if drift:
            print(
                "FAIL declared digests are stale. These are hand-maintained on "
                "purpose, so update them yourself rather than regenerating:\n"
                + "\n".join(drift)
            )
            return 1
        pending = undeclared_untracked_python()
        if pending:
            print(
                "FAIL source declaration is current for the index, but these "
                "untracked Python files will change python_paths when staged: "
                + ", ".join(pending)
            )
            return 1
        print("PASS source declaration is current")
        return 0
    DECLARATION_PATH.write_text(rendered, encoding="utf-8")
    print(f"WROTE {DECLARATION_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
