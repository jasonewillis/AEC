#!/usr/bin/env python3
"""Prove a local mentor lens cannot change the authoritative AEC decision."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aec.mentor import (  # noqa: E402
    PrivateMentorLensError,
    apply_private_mentor_lens,
    load_private_mentor_lens,
)
from aec.resolver import ResolutionRejection, resolve  # noqa: E402


def load_json(path: Path) -> object:
    """Load one UTF-8 JSON input."""
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def parse_args() -> argparse.Namespace:
    """Parse explicit local proof inputs."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument(
        "--catalog",
        default=ROOT / "config/procedures/ticket-to-pr.json",
        type=Path,
    )
    parser.add_argument("--lens", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    """Print metadata-only proof without logging private guidance."""
    arguments = parse_args()
    try:
        decision = resolve(load_json(arguments.request), load_json(arguments.catalog))
        if isinstance(decision, ResolutionRejection):
            print(json.dumps(decision.to_dict(), indent=2, sort_keys=True))
            return 1
        lens = load_private_mentor_lens(arguments.lens)
        if lens is None:
            raise PrivateMentorLensError("explicit private mentor lens is missing")
        envelope = apply_private_mentor_lens(decision, lens).to_dict()
    except (OSError, ValueError, json.JSONDecodeError, PrivateMentorLensError) as error:
        print(json.dumps({"error": str(error), "status": "FAIL"}, sort_keys=True))
        return 1
    context = envelope["supplemental_context"]
    proof = {
        "authoritative_resolution_hash": envelope["authoritative_resolution_hash"],
        "decision_unchanged": envelope["authoritative_decision"] == decision.to_dict(),
        "executes": envelope["executes"],
        "lens_hash": context["lens_hash"] if context is not None else None,
        "mutates": envelope["mutates"],
        "selected_card_ids": (
            [card["id"] for card in context["cards"]]
            if context is not None
            else []
        ),
        "status": "PASS",
    }
    print(json.dumps(proof, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
