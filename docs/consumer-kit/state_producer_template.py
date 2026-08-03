#!/usr/bin/env python3
"""Consumer install kit: copy this file into your repository and fill it in.

This is a template, not a library. Copy it (for example to
`scripts/aec_state.py`), edit the three constants under CONFIGURE, and run it
before each coaching interaction. It writes one ignored local state file that
`tools/aec_prompt_hook.py` and `tools/aec_coach.py checkpoint` read.

Why a template you own rather than a command AEC ships: the state file is a
claim about *your* repository -- your task identity, your lane, your evidence,
your environment. AEC cannot prove any of those and must never invent them.
What it can prove -- the exact revision, the workflow shape, the required
procedure for a phase -- is derived here from your own checkout and AEC's
pinned catalog. Anything else is passed explicitly or rejected.

Prerequisites:

    1. AEC vendored at one exact commit (see register-hook.md, step 1).
    2. `python3 -m tools.aec_coach doctor` green inside that checkout.

Usage after copying:

    python3 scripts/aec_state.py --task myrepo#12 --phase Framing --lane FEATURE
    python3 scripts/aec_state.py --task myrepo#12 --phase Verify --lane FEATURE \
        --evidence unit-test:accepted --evidence lint:accepted

Exit code 0 means the state file was written. Any nonzero exit means no state
was written and no coaching should be trusted; the message names the fact that
could not be proven.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


# --------------------------------------------------------------------------
# CONFIGURE: these three values are yours. Nothing else in this file needs to
# change for a normal install.
# --------------------------------------------------------------------------

# Where you vendored AEC, relative to this script's repository root.
AEC_CHECKOUT = Path(".local/aec")

# Your repository, in owner/repository form. Must match the real remote.
CONSUMER_PROJECT = "your-owner/your-repository"

# Bump this string whenever you change anything in this file. It is recorded in
# every state document so a card can be traced back to the producer that made it.
PROFILE_VERSION = "your-repository:1.0.0"

# --------------------------------------------------------------------------
# Below here is the copied wiring. Read it, but you should not need to edit it.
# --------------------------------------------------------------------------

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AEC_ROOT = (REPOSITORY_ROOT / AEC_CHECKOUT).resolve()
sys.path.insert(0, str(AEC_ROOT))

from aec.state_builder import (  # noqa: E402  (path setup must precede this import)
    BuildStateFailure,
    build_state,
    parse_blocker,
    parse_evidence,
)


CATALOG_PATH = AEC_ROOT / "config" / "procedures" / "ticket-to-pr.json"
WORKFLOW_PATH = AEC_ROOT / "config" / "workflows" / "ticket-to-pr.json"

# `lifecycle_authority`, `aec_mode`, and `workflow` are fixed by the contract:
# AEC is a read-only mentor over the ticket-to-pr workflow and never owns your
# lifecycle. `agent_adapters` lists the agents that will render these cards.
CONSUMER_PROFILE = {
    "aec_mode": "read-only-mentor",
    "agent_adapters": ["claude-code"],
    "lifecycle_authority": "consumer-owned",
    "profile_version": PROFILE_VERSION,
    "project": CONSUMER_PROJECT,
    "schema_version": "1.0.0",
    "workflow": "ticket-to-pr",
}


def load_object(path: Path, label: str) -> dict:
    """Load one JSON object, failing closed on any I/O or shape error."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SystemExit(f"aec state: FAIL: cannot read {label}: {error}")
    if type(value) is not dict:
        raise SystemExit(f"aec state: FAIL: {label} must be a JSON object")
    return value


def consumer_revision() -> str:
    """Return YOUR repository's exact HEAD, never AEC's.

    This is the fact the whole binding rests on: a card is valid only for the
    tree it was resolved against. Reading AEC's HEAD here instead would silently
    bind every card to the framework's commit and let stale evidence survive a
    change to your own source.
    """
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SystemExit(f"aec state: FAIL: git rev-parse HEAD: {result.stderr.strip()}")
    return result.stdout.strip()


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write one local AEC coaching state.")
    parser.add_argument("--task", required=True, help="e.g. myrepo#12")
    parser.add_argument("--phase", required=True, help="e.g. Framing, Verify, Review")
    parser.add_argument("--lane", required=True, help="e.g. FEATURE, INFRA, DOCS")
    parser.add_argument("--out", type=Path, default=Path("tmp/aec-state.json"))
    parser.add_argument(
        "--evidence",
        action="append",
        default=[],
        help="repeatable KIND[:accepted|:rejected]",
    )
    parser.add_argument(
        "--blocker",
        action="append",
        default=[],
        help="repeatable IDENTITY:REASON_CODE[:active|:inactive]",
    )
    parser.add_argument(
        "--decision-context",
        type=Path,
        default=None,
        help="JSON file, only at a material fork; omit for routine steps",
    )
    parser.add_argument("--environment", default="local")
    parser.add_argument("--expires-minutes", type=int, default=30)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    if CONSUMER_PROJECT == "your-owner/your-repository":
        print(
            "aec state: FAIL: set CONSUMER_PROJECT before using this template",
            file=sys.stderr,
        )
        return 1
    try:
        decision_context = (
            load_object(arguments.decision_context, "decision context")
            if arguments.decision_context is not None
            else None
        )
        state = build_state(
            task=arguments.task,
            phase=arguments.phase,
            lane=arguments.lane,
            environment=arguments.environment,
            expires_minutes=arguments.expires_minutes,
            evidence=[parse_evidence(item) for item in arguments.evidence],
            blockers=[parse_blocker(item) for item in arguments.blocker],
            revision=consumer_revision(),
            catalog=load_object(CATALOG_PATH, "procedure catalog"),
            workflow=load_object(WORKFLOW_PATH, "workflow definition"),
            profile=CONSUMER_PROFILE,
            decision_context=decision_context,
        )
        out_path = (REPOSITORY_ROOT / arguments.out).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")
    except (BuildStateFailure, OSError, ValueError) as error:
        print(f"aec state: FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
