#!/usr/bin/env python3
"""One AEC-owned entrypoint for coaching state construction and rendering.

Combines the two consumer-side tools ported from the HealthRAG pilot (AEC
issues #58 and #52) behind a single command:

    python3.12 -m tools.aec_coach doctor
    python3.12 -m tools.aec_coach state --task <id> --phase <phase> --lane <lane>
    python3.12 -m tools.aec_coach checkpoint <state-file>
    python3.12 -m tools.aec_coach checkpoint --project-root <repo> <state-file>

`doctor` is the single preflight command a consumer runs before trusting a
pinned AEC checkout. It reports the pin, the released contract versions, and
both connection probes in one pass. `state` builds an ignored local
`tmp/aec-state.json` from proven Git facts plus explicit flags (see
aec/state_builder.py). `checkpoint` validates that state against the resolver
and renders the card. Default output is human coaching text
(`[AEC: Project Guidance]`, `[AEC: Mentoring]`); pass `--format json` for the
machine-readable card.

`checkpoint` binds the state to the exact HEAD of `--project-root`, which
defaults to this AEC checkout. A state document is a claim about the tree it
describes, so a *consumer* state -- built by
`docs/consumer-kit/state_producer_template.py` against the consumer's own
HEAD -- must be checked with `--project-root` pointed at that consumer
repository. Two repositories never share a HEAD, so omitting the flag on a
vendored install compares AEC's revision against the consumer's and rejects
every state with `CONSUMER_STATE_MISMATCH`. The flag supplies the revision to
compare; it never relaxes the comparison, which stays exact in both modes and
is the same binding `tools/aec_prompt_hook.py` already makes at the prompt
boundary.

`doctor` only resolves and reports. It never registers a hook, writes
consumer state, or mutates any lifecycle, review, merge, or deploy state.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# A consumer with AEC vendored under `.local/aec` runs this as a file path
# (`python3 .local/aec/tools/aec_coach.py ...`), not with `-m` from inside the
# checkout, because the state file and `--project-root` are both in their own
# repository. Run that way there is no package context and the checkout root
# is not on `sys.path`, so the imports below fail with a bare
# `ModuleNotFoundError: No module named 'aec'`. Same bootstrap, same reason,
# as tools/aec_prompt_hook.py.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aec.consumer import ConsumerStateRejection, resolve_consumer_state  # noqa: E402
from aec.human_render import RenderFailure, default_rail_definition, render_human  # noqa: E402
from aec.release_manifest import validate_release_descriptor  # noqa: E402
from aec.state_builder import (  # noqa: E402
    AEC_SELF_PROFILE,
    BuildStateFailure,
    build_state,
    parse_blocker,
    parse_evidence,
)
from tools.validate_consumer_connection import (  # noqa: E402
    ConnectionFailure,
    DEFAULT_MATERIAL_PROBE,
    DEFAULT_ROUTINE_PROBE,
    validate_connection,
)


ROOT = Path(__file__).resolve().parents[1]
PROCEDURE_CATALOG_PATH = ROOT / "config" / "procedures" / "ticket-to-pr.json"
WORKFLOW_PATH = ROOT / "config" / "workflows" / "ticket-to-pr.json"
RELEASE_DESCRIPTOR_PATH = ROOT / "config" / "release" / "aec-release.json"
HEX_REVISION = re.compile(r"^[0-9a-f]{40}$")

# The probes `doctor` reports, in the order it reports them, mapped to the
# `decision_support` shape each one must have proven. Both must be present in
# the connection receipt, both must carry status PASS, and both must carry a
# boolean `has_decision_support` equal to the value below before any report
# line is printed; see require_probe_receipts.
#
# The expected values are not decoration. The whole reason `doctor` exists is
# the `d35f535` incident, where a contract tightening broke material-decision
# consumers while every routine check still passed. A receipt whose material
# probe reports `has_decision_support` false -- or omits the key entirely --
# describes exactly that incompatibility, so `doctor` must refuse it rather
# than render `MATERIAL PASS decision_support=absent`.
DOCTOR_REQUIRED_PROBES: dict[str, bool] = {"routine": False, "material": True}


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


def current_revision(root: Path | None = None) -> str:
    """Return the exact HEAD revision of one checkout, defaulting to AEC's own.

    `root` is the repository whose revision is being proven, not a search
    hint: `git rev-parse` walks upward out of a subdirectory, so a caller that
    passes a path inside another repository gets that repository's HEAD.
    """
    target = ROOT if root is None else root
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=target,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise CoachFailure(
            f"git rev-parse HEAD failed in {target}: {result.stderr.strip()}"
        )
    revision = result.stdout.strip()
    if HEX_REVISION.fullmatch(revision) is None:
        raise CoachFailure(f"git rev-parse HEAD in {target} did not return a revision")
    return revision


def utc_now() -> str:
    """Return the current UTC time in the contract's required format."""
    now = datetime.now(timezone.utc).replace(microsecond=0)
    return now.isoformat().replace("+00:00", "Z")


def require_probe_receipts(receipt: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return one receipt per required probe, or fail closed before reporting.

    This is `doctor`'s fail-closed guard and the reason the command cannot
    print a `PASS` line it did not earn. `validate_connection` raises on a
    rejected probe, so the happy path never reaches a missing or non-PASS
    entry -- but "the current caller happens to raise first" is not a
    property a consumer-facing preflight command should depend on. A future
    receipt shape that reports a probe as skipped, absent, or anything other
    than PASS must stop the report rather than be rendered as one, because the
    whole value of `doctor` is that its output is a claim about probes that
    actually ran.

    The same argument applies to `has_decision_support`, which the report
    renders as `decision_support=present|absent`. `doctor_report` used to read
    it with `.get()`, so a material receipt that omitted the key -- or carried
    it as false -- rendered `MATERIAL PASS decision_support=absent`: a PASS
    line describing the exact contract incompatibility `doctor` exists to
    catch. The key must therefore be present, boolean, and equal to the shape
    DOCTOR_REQUIRED_PROBES says that probe proves.
    """
    entries = receipt.get("probes")
    if type(entries) is not list:
        raise CoachFailure("connection receipt has no probes list")
    by_name: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if type(entry) is not dict:
            raise CoachFailure("connection receipt probe entry is malformed")
        by_name[str(entry.get("probe"))] = entry
    for name, expected_support in DOCTOR_REQUIRED_PROBES.items():
        entry = by_name.get(name)
        if entry is None:
            raise CoachFailure(f"connection receipt is missing the {name} probe")
        if entry.get("status") != "PASS":
            raise CoachFailure(
                f"{name} probe did not report PASS "
                f"(status={entry.get('status')!r}); refusing to report a pin as usable"
            )
        support = entry.get("has_decision_support")
        if type(support) is not bool:
            raise CoachFailure(
                f"{name} probe receipt has no boolean has_decision_support "
                f"(found {support!r}); refusing to report a decision_support shape "
                "it did not prove"
            )
        if support != expected_support:
            raise CoachFailure(
                f"{name} probe proved decision_support "
                f"{'present' if support else 'absent'} but must prove "
                f"{'present' if expected_support else 'absent'}; this pin is not "
                "compatible with the probe it claims to have run"
            )
    return by_name


def contract_line(descriptor: dict[str, Any]) -> str:
    """Render the released contract versions this checkout declares."""
    errors = validate_release_descriptor(descriptor)
    if errors:
        raise CoachFailure("release descriptor is invalid: " + "; ".join(errors))
    contracts = descriptor["contracts"]
    pairs = " ".join(f"{name}={contracts[name]}" for name in sorted(contracts))
    return (
        f"CONTRACT release={descriptor['release_version']} "
        f"channel={descriptor['channel']} {pairs}"
    )


def doctor_report(revision: str, descriptor: dict[str, Any], receipt: dict[str, Any]) -> str:
    """Build the whole `doctor` report, or raise before any line is printed.

    `contract_line` runs first because it is what validates the descriptor.
    Reading `descriptor['repository']` ahead of it would raise `KeyError` on a
    malformed descriptor -- a traceback, not the advertised
    "release descriptor is invalid" failure -- so the validated line is built
    before any field of the descriptor is read directly.
    """
    probes = require_probe_receipts(receipt)
    contract = contract_line(descriptor)
    lines = [
        f"PIN revision={revision} repository={descriptor['repository']}",
        contract,
    ]
    for name in DOCTOR_REQUIRED_PROBES:
        entry = probes[name]
        support = "present" if entry["has_decision_support"] else "absent"
        lines.append(
            f"{name.upper()} PASS gate={entry['gate']} decision_support={support}"
        )
    return "\n".join(lines)


def run_doctor(arguments: argparse.Namespace) -> int:
    """Prove a pinned checkout in one pass, keeping failures off standard output.

    Reuses `tools.validate_consumer_connection.validate_connection`, the same
    ROUTINE/MATERIAL probe path a consumer already runs, rather than building
    probes here. Nothing is written and nothing is mutated.
    """
    try:
        revision = current_revision()
        descriptor = load_object(RELEASE_DESCRIPTOR_PATH, "release descriptor")
        receipt = validate_connection(
            arguments.routine, arguments.material, arguments.catalog
        )
        report = doctor_report(revision, descriptor, receipt)
        if current_revision() != revision:
            raise CoachFailure("HEAD changed while proving the pin")
    except (CoachFailure, ConnectionFailure, KeyError, OSError, ValueError) as error:
        print(f"AEC coach doctor: FAIL: {error}", file=sys.stderr)
        return 1
    print(report)
    return 0


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
    """Render one card, keeping rejected output off standard output.

    The revision the state is checked against comes from
    `--project-root` (default: this AEC checkout). A consumer state is a claim
    about the consumer's tree, so proving it requires the consumer's HEAD --
    supplying that revision is the flag's only effect. The comparison itself
    stays exact.
    """
    try:
        state = load_object(arguments.state, "consumer state")
        catalog = load_object(PROCEDURE_CATALOG_PATH, "procedure catalog")
        project_root = arguments.project_root.resolve()
        revision = current_revision(project_root)
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
        if current_revision(project_root) != revision:
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

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Prove this pin, its contract versions, and both probes in one pass.",
    )
    doctor_parser.add_argument("--routine", type=Path, default=DEFAULT_ROUTINE_PROBE)
    doctor_parser.add_argument("--material", type=Path, default=DEFAULT_MATERIAL_PROBE)
    doctor_parser.add_argument("--catalog", type=Path, default=PROCEDURE_CATALOG_PATH)
    doctor_parser.set_defaults(handler=run_doctor)

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
    checkpoint_parser.add_argument(
        "--project-root",
        type=Path,
        default=ROOT,
        help=(
            "Repository whose exact HEAD the state must match. Defaults to this "
            "AEC checkout; point it at your own repository when checking a "
            "consumer state built against your HEAD."
        ),
    )
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
