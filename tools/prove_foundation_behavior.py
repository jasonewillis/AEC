"""Emit the frozen ten-decision aggregate for one process and hash seed."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Callable

from aec.resolver import ResolutionDecision, resolve


TEN_DECISION_AGGREGATE = (
    "sha256:b2cf5ae9339f80cc5da684109a4046545fc234ac525c902c02d707efb393ea4d"
)
EXPECTED_AGGREGATE = (
    "sha256:f26c33d081de721456559e8e17634d79df26d362cd127f529139857daf5a527e"
)
BLOCKER_PRECEDENCE = (
    "AUTHORITY_CONFLICT",
    "PRIVATE_INPUT_INCLUDED",
    "POLICY_CONFLICT",
    "LIFECYCLE_STATE_STALE",
    "EVIDENCE_CONTRADICTED",
)
FIXTURE_PATHS = (
    "tests/fixtures/resolver/golden/intake.json",
    "tests/fixtures/resolver/golden/framing.json",
    "tests/fixtures/resolver/golden/spec.json",
    "tests/fixtures/resolver/golden/plan.json",
    "tests/fixtures/resolver/golden/build.json",
    "tests/fixtures/resolver/golden/verify.json",
    "tests/fixtures/resolver/golden/review.json",
    "tests/fixtures/resolver/golden/pr.json",
    "tests/fixtures/resolver/golden/deploy.json",
    "tests/fixtures/resolver/red/unavailable-skill.json",
)


def _reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Build one JSON object while rejecting duplicate member names."""
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _strict_json(path: Path) -> object:
    """Read one explicit UTF-8 JSON file with duplicate-key rejection."""
    return json.loads(
        path.read_text(encoding="utf-8", errors="strict"),
        object_pairs_hook=_reject_duplicate_keys,
    )


def _exact_equal(left: object, right: object) -> bool:
    """Compare normalized JSON values with exact recursive builtin types."""
    if type(left) is not type(right):
        return False
    if type(left) is list:
        return len(left) == len(right) and all(
            _exact_equal(left_item, right_item)
            for left_item, right_item in zip(left, right, strict=True)
        )
    if type(left) is dict:
        return set(left) == set(right) and all(
            _exact_equal(left[key], right[key]) for key in left
        )
    return left == right


def ten_decision_aggregate(
    root: Path,
    resolver: Callable[[object, object], object] = resolve,
) -> str:
    """Resolve ten requests and bind exact bytes, hashes, and immutability."""
    catalog = _strict_json(root / "config/procedures/ticket-to-pr.json")
    catalog_before = copy.deepcopy(catalog)
    decisions: list[list[str]] = []
    for relative in FIXTURE_PATHS:
        request = _strict_json(root / relative)
        request_before = copy.deepcopy(request)
        decision = resolver(request, catalog)
        if not _exact_equal(request, request_before) or not _exact_equal(
            catalog, catalog_before
        ):
            raise ValueError("resolver mutated caller input")
        if not isinstance(decision, ResolutionDecision):
            raise ValueError(f"fixture did not resolve: {relative}")
        decisions.append(
            [
                Path(relative).name,
                decision.resolution_hash,
                decision.canonical_bytes.hex(),
            ]
        )
    payload = json.dumps(decisions, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def decision_aggregate(
    root: Path,
    resolver: Callable[[object, object], object] = resolve,
) -> str:
    """Extend the frozen ten-decision aggregate with blocker decisions."""
    legacy = ten_decision_aggregate(root, resolver)
    catalog = _strict_json(root / "config/procedures/ticket-to-pr.json")
    request = _strict_json(root / "tests/fixtures/resolver/golden/verify.json")
    blocker_decisions: list[list[str]] = []
    for reason_code in BLOCKER_PRECEDENCE:
        blocked_request = copy.deepcopy(request)
        blocked_request["blockers"] = [
            {
                "active": True,
                "identity": f"blocker-{reason_code.lower()}",
                "reason_code": reason_code,
            }
        ]
        decision = resolver(blocked_request, catalog)
        if not isinstance(decision, ResolutionDecision):
            raise ValueError(f"blocker did not resolve: {reason_code}")
        blocker_decisions.append(
            [
                reason_code,
                decision.resolution_hash,
                decision.canonical_bytes.hex(),
            ]
        )
    payload = json.dumps(
        [legacy, blocker_decisions],
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def prove_behavior(
    root: Path,
    resolver: Callable[[object, object], object] = resolve,
) -> str:
    """Return the aggregate only when it matches the base-owned identity."""
    aggregate = decision_aggregate(root, resolver)
    if aggregate != EXPECTED_AGGREGATE:
        raise ValueError(f"behavior aggregate mismatch: {aggregate}")
    return aggregate


def main(argv: list[str] | None = None) -> int:
    """Print one verified aggregate for the cross-seed test adapter."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    arguments = parser.parse_args(argv)
    try:
        aggregate = prove_behavior(arguments.root.resolve())
    except ValueError as error:
        print(f"FAIL {error}")
        return 1
    print(aggregate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
