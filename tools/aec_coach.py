#!/usr/bin/env python3
"""One AEC-owned entrypoint for coaching state construction and rendering.

Combines the two consumer-side tools ported from the HealthRAG pilot (AEC
issues #58 and #52) behind a single command:

    python3.12 -m tools.aec_coach state --task <id> --phase <phase> --lane <lane>
    python3.12 -m tools.aec_coach checkpoint <state-file>

`state` builds an ignored local `tmp/aec-state.json` from proven Git facts
plus explicit flags (see aec/state_builder.py). `checkpoint` validates that
state against the resolver and renders the card. Default output is human
coaching text (`[AEC: Project Guidance]`, `[AEC: Mentoring]`); pass
`--format json` for the machine-readable card.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aec.consumer import ConsumerStateRejection, resolve_consumer_state
from aec.human_render import RenderFailure, default_rail_definition, render_human
from aec.state_builder import (
    AEC_SELF_PROFILE,
    BuildStateFailure,
    build_state,
    parse_blocker,
    parse_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
PROCEDURE_CATALOG_PATH = ROOT / "config" / "procedures" / "ticket-to-pr.json"
WORKFLOW_PATH = ROOT / "config" / "workflows" / "ticket-to-pr.json"


class CoachFailure(RuntimeError):
    """A fail-closed coaching entrypoint result."""


def load_object(path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk, failing closed on any I/O or shape error."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as error:
        raise CoachFailure(f"cannot read {label}: {error}") from error
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as error:
        raise CoachFailure(f"{label} is not valid JSON: {error}") from error
    if type(value) is not dict:
        raise CoachFailure(f"{label} must be a JSON object")
    return value


def current_revision() -> str:
    """Return the exact HEAD revision of this checkout."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise CoachFailure(f"git rev-parse HEAD failed: {result.stderr.strip()}")
    return result.stdout.strip()


def utc_now() -> str:
    """Return the current UTC time in the contract's required format."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return now.isoformat().replace("+00:00", "Z")


def run_state(arguments: argparse.Namespace) -> int:
    """Build one coaching state file, keeping failures off standard output."""
    try:
        evidence = [parse_evidence(item) for item in arguments.evidence]
        blockers = [parse_blocker(item) for item in arguments.blocker]
        decision_context = (
            load_object(arguments.decision_context, "decision context")
            if arguments.decision_context is not None
            else None
        )
        catalog = load_object(PROCEDURE_CATALOG_PATH, "procedure catalog")
        workflow = load_object(WORKFLOW_PATH, "workflow definition")
        state = build_state(
            task=arguments.task,
            phase=arguments.phase,
            lane=arguments.lane,
            environment=arguments.environment,
            expires_minutes=arguments.expires_minutes,
            evidence=evidence,
            blockers=blockers,
            revision=current_revision(),
            catalog=catalog,
            workflow=workflow,
            profile=AEC_SELF_PROFILE,
            decision_context=decision_context,
        )
        out_path = arguments.out.resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(state, indent=2, sort_keys=True), encoding="utf-8"
        )
    except (BuildStateFailure, CoachFailure, OSError, ValueError) as error:
        print(f"AEC coach state: FAIL: {error}", file=sys.stderr)
        return 1
    return 0


def run_checkpoint(arguments: argparse.Namespace) -> int:
    """Render one card, keeping rejected output off standard output."""
    try:
        state = load_object(arguments.state, "consumer state")
        catalog = load_object(PROCEDURE_CATALOG_PATH, "procedure catalog")
        revision = current_revision()
        result = resolve_consumer_state(
            state,
            catalog,
            current_time=utc_now(),
            expected_environment=arguments.environment,
            expected_revision=revision,
        )
        if isinstance(result, ConsumerStateRejection):
            detail = json.dumps(
                result.to_dict(), separators=(",", ":"), sort_keys=True
            )
            raise CoachFailure(f"consumer state rejected: {detail}")
        if current_revision() != revision:
            raise CoachFailure("HEAD changed while rendering the checkpoint")
        card = result.to_dict()
        if arguments.format == "json":
            rendered = json.dumps(card, indent=2, sort_keys=True)
        else:
            rendered = render_human(card, default_rail_definition())
    except (CoachFailure, RenderFailure, OSError, ValueError) as error:
        print(f"AEC coach checkpoint: FAIL: {error}", file=sys.stderr)
        return 1
    print(rendered)
    return 0


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the state/checkpoint subcommand and its arguments."""
    parser = argparse.ArgumentParser(prog="aec-coach", description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    state_parser = subparsers.add_parser(
        "state", help="Build one AEC coaching state file from proven Git facts."
    )
    state_parser.add_argument("--task", required=True)
    state_parser.add_argument("--phase", required=True)
    state_parser.add_argument("--lane", required=True)
    state_parser.add_argument("--out", type=Path, default=Path("tmp/aec-state.json"))
    state_parser.add_argument("--evidence", action="append", default=[])
    state_parser.add_argument("--blocker", action="append", default=[])
    state_parser.add_argument("--decision-context", type=Path, default=None)
    state_parser.add_argument("--environment", default="local")
    state_parser.add_argument("--expires-minutes", type=int, default=30)
    state_parser.set_defaults(handler=run_state)

    checkpoint_parser = subparsers.add_parser(
        "checkpoint", help="Render one AEC coaching checkpoint from a state file."
    )
    checkpoint_parser.add_argument("state", type=Path)
    checkpoint_parser.add_argument("--environment", default="local")
    checkpoint_parser.add_argument(
        "--format",
        choices=("human", "json"),
        default="human",
        help="Output format. human (default) renders coaching text.",
    )
    checkpoint_parser.set_defaults(handler=run_checkpoint)

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Dispatch to the requested subcommand handler."""
    arguments = parse_arguments(argv)
    return arguments.handler(arguments)


if __name__ == "__main__":
    raise SystemExit(main())
