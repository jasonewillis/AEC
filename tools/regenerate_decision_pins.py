#!/usr/bin/env python3
"""Recompute the decision hashes pinned as literals across the test suite.

Any edit to `config/procedures/ticket-to-pr.json` changes every card's hash,
because `_normalized_catalog_binding` folds the whole catalog into
`input_bindings.procedure_catalog`. That is by design — the binding is what
proves a card was resolved from a known catalog — but it means a one-line copy
change cascades into every pinned literal in `tests/`.

Those literals are real controls. A test that recomputed the expected hash from
the same code it exercises would pass for any catalog whatsoever, so the pins
must stay literal. They just have to be *derived* rather than hand-edited.

An earlier attempt at this cascade (2026-07-29) was reverted because a global
find-and-replace mismapped: the same OLD hash was reused at sites that resolve
to DIFFERENT new hashes, so replacing it everywhere corrupted the pins that
happened to share a prefix state. This tool fails closed on exactly that case —
see `--check`, which reports an ambiguous mapping instead of writing one.

Usage:
    python3 tools/regenerate_decision_pins.py --check   # report, write nothing
    python3 tools/regenerate_decision_pins.py --write   # rewrite the literals
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aec.resolver import resolve  # noqa: E402

CATALOG_PATH = ROOT / "config/procedures/ticket-to-pr.json"
GOLDEN_DIR = ROOT / "tests/fixtures/resolver/golden"
HASH = re.compile(r"sha256:[0-9a-f]{64}")

# Files carrying pinned decision hashes. Digests of file bytes (Blueprint skill
# hashes, admission source digests) live elsewhere and are deliberately absent:
# they are not derived from the catalog and must never be rewritten from it.
PINNED_FILES = (
    "tests/test_resolver.py",
    "tests/test_resolver_blocker_precedence.py",
    "tests/test_agent_adapters.py",
    "tests/fixtures/outcomes/golden.json",
)

# Aggregates fold many decisions into one digest, so they cannot be recovered
# from the per-golden mapping above: a changed input hash does not appear in
# them literally. They are recomputed from their own producers instead.
AGGREGATE_PINS = (
    ("tools/prove_foundation_behavior.py", "TEN_DECISION_AGGREGATE", "ten_decision"),
    ("tools/prove_foundation_behavior.py", "EXPECTED_AGGREGATE", "full"),
)


def current_aggregates() -> dict[str, str]:
    """Recompute the frozen behavior aggregates from their own producer."""
    import tools.prove_foundation_behavior as prover

    return {
        "ten_decision": prover.ten_decision_aggregate(ROOT, resolve),
        "full": prover.decision_aggregate(ROOT, resolve),
    }


def rewrite_aggregates() -> None:
    """Repin each frozen aggregate to its recomputed value."""
    values = current_aggregates()
    for relative, constant, key in AGGREGATE_PINS:
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        pattern = re.compile(
            rf'({re.escape(constant)} = \(\n\s*")sha256:[0-9a-f]{{64}}(")'
        )
        replaced, count = pattern.subn(rf"\g<1>{values[key]}\g<2>", text)
        if count != 1:
            raise SystemExit(f"{constant} not found exactly once in {relative}")
        path.write_text(replaced, encoding="utf-8")
        print(f"  repinned {constant} -> {values[key]}")


def golden_decisions() -> dict[str, str]:
    """Resolve every committed golden request to its current decision hash."""
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    hashes: dict[str, str] = {}
    for path in sorted(GOLDEN_DIR.glob("*.json")):
        request = json.loads(path.read_text(encoding="utf-8"))
        decision = resolve(request, catalog)
        resolution_hash = getattr(decision, "resolution_hash", None)
        if resolution_hash is None:
            raise SystemExit(f"{path.name} no longer resolves to a decision")
        hashes[path.stem] = resolution_hash
    return hashes


def build_mapping(previous: dict[str, str], current: dict[str, str]) -> dict[str, str]:
    """Map each old hash to its new value, refusing an ambiguous mapping.

    This is the guard the 2026-07-29 attempt did not have. If one old literal
    corresponds to two different new hashes, no textual substitution can be
    correct, and silently picking one is how that attempt corrupted the pins.
    """
    mapping: dict[str, set[str]] = {}
    for name, old in previous.items():
        if name in current:
            mapping.setdefault(old, set()).add(current[name])
    ambiguous = {old: news for old, news in mapping.items() if len(news) > 1}
    if ambiguous:
        for old, news in sorted(ambiguous.items()):
            print(f"AMBIGUOUS {old} -> {sorted(news)}", file=sys.stderr)
        raise SystemExit(
            "one old hash maps to several new hashes; substitution cannot be "
            "correct here and must be resolved per site by hand"
        )
    return {old: news.pop() for old, news in mapping.items() if old not in ambiguous}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--write", action="store_true")
    arguments = parser.parse_args(argv)

    current = golden_decisions()
    print("current golden decision hashes:")
    for name, value in sorted(current.items()):
        print(f"  {name:8} {value}")

    # The previous values are whatever the suite currently pins for each golden.
    # Read them from the phase map in test_resolver.py, which is the one place
    # that names a phase and its hash together.
    source = (ROOT / "tests/test_resolver.py").read_text(encoding="utf-8")
    block = re.search(r"GOLDEN_HASHES = \{(.*?)\n\}", source, re.S)
    if block is None:
        raise SystemExit("GOLDEN_HASHES map not found in tests/test_resolver.py")
    previous = {
        phase.lower(): value
        for phase, value in re.findall(
            r'"(\w+)":\s*"(sha256:[0-9a-f]{64})"', block.group(1)
        )
    }

    mapping = build_mapping(previous, current)
    changed = {old: new for old, new in mapping.items() if old != new}
    print(f"\n{len(changed)} of {len(previous)} pinned golden hashes changed")
    if not arguments.write:
        for old, new in sorted(changed.items()):
            print(f"  {old}\n  -> {new}")
        print("\ncurrent behavior aggregates:")
        for key, value in sorted(current_aggregates().items()):
            print(f"  {key:12} {value}")
        return 0

    for relative in PINNED_FILES:
        path = ROOT / relative
        text = path.read_text(encoding="utf-8")
        replaced = HASH.sub(lambda m: changed.get(m.group(0), m.group(0)), text)
        if replaced != text:
            path.write_text(replaced, encoding="utf-8")
            hits = sum(text.count(old) for old in changed)
            print(f"  rewrote {relative} ({hits} literal(s))")
    # Aggregates must be repinned after the per-golden literals, because their
    # producer resolves the same fixtures this run just proved current.
    rewrite_aggregates()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
