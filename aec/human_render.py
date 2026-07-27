"""Render one validated AEC public card as human coaching text.

Ported from the HealthRAG pilot's `AEC/render_checkpoint.py --format human`
(issues #58, #52). The pilot re-parsed `config/workflows/ticket-to-pr.json`
per render, guarding against a pin bump changing that contract underneath a
downstream copy. Inside AEC there is no downstream copy: `aec/cards.py`
already hardcodes `PHASE_RAIL` / `STAGE_PHASES`, so `default_rail_definition()`
reads those directly. `RailDefinition` stays an explicit parameter so tests
can prove the renderer is data-driven and force the fail-closed mismatch path.
"""

from __future__ import annotations

from typing import Any, NamedTuple

from aec.cards import PHASE_RAIL, STAGE_PHASES


class RenderFailure(RuntimeError):
    """A fail-closed human rendering result."""


class RailDefinition(NamedTuple):
    """The phase order and stage grouping for one rendered rail."""

    phase_names: tuple[str, ...]
    stage_groups: tuple[tuple[str, tuple[str, ...]], ...]


def default_rail_definition() -> RailDefinition:
    """Return the rail definition derived from AEC's own canonical phase rail."""
    stage_groups = tuple((name.upper(), phases) for name, phases in STAGE_PHASES.items())
    return RailDefinition(phase_names=PHASE_RAIL, stage_groups=stage_groups)


RAIL_MARGIN = 2
RAIL_COLUMN_WIDTH = 15
HUMAN_RENDER_CONTRACT_VERSION = "1.1.0"
FULL_CARD_TRIGGERS: tuple[str, ...] = (
    "task-intake",
    "phase-transition",
    "gate-transition",
    "gate-failure",
    "review-finding",
    "pr-created",
    "deploy-observe",
    "status-request",
)
INTERACTION_TRIGGERS = frozenset((*FULL_CARD_TRIGGERS, "routine-progress"))
PHASE_DISPLAY_NAMES = {"Deploy": "Deploy/Observe"}
EVIDENCE_CLASS_BY_KIND = {
    "base-head-binding": "source-audited",
    "independent-review": "source-audited",
    "resolved-findings": "source-audited",
    "red-case-result": "test-verified",
    "green-case-result": "test-verified",
    "focused-test-report": "test-verified",
    "integration-test-report": "test-verified",
    "current-required-checks": "ci-verified",
    "live-revision": "runtime-verified",
    "recovery-path": "runtime-verified",
    "live-observation": "live-data-verified",
    "stacked-base-readiness": "source-audited",
}
TRADEOFF_DIMENSIONS: tuple[str, ...] = (
    "maintainability",
    "quality",
    "reversibility",
    "risk",
    "scope",
)


def render_rail(card: dict[str, Any], rail_definition: RailDefinition) -> str:
    """Render the ASCII workflow rail for one validated card.

    A rail is a straight line with one marker for each pinned phase. A
    marker shows one of three states: cleared, current, or not reached yet.
    Fails closed if the card's own rail_total disagrees with the rail
    definition's phase count, instead of drawing a rail whose text and
    columns silently disagree.
    """
    position = card["rail_position"]
    rail = int(position["rail"])
    rail_total = int(position["rail_total"])
    phase = int(position["phase"])
    phase_total = int(position["phase_total"])
    current_index = rail - 1

    phase_names = rail_definition.phase_names
    if rail_total != len(phase_names):
        raise RenderFailure(
            "card rail_total ({0}) does not match the rail definition's phase "
            "count ({1})".format(rail_total, len(phase_names))
        )

    header_characters = [" "] * (RAIL_MARGIN + len(phase_names) * RAIL_COLUMN_WIDTH)
    cursor = RAIL_MARGIN
    for label, phases in rail_definition.stage_groups:
        span = len(phases) * RAIL_COLUMN_WIDTH
        start = cursor + max(0, (span - len(label)) // 2)
        for offset, character in enumerate(label):
            index = start + offset
            if index < len(header_characters):
                header_characters[index] = character
        cursor += span
    header_line = "".join(header_characters).rstrip()

    markers = []
    for index in range(len(phase_names)):
        if index < current_index:
            markers.append("●")  # cleared
        elif index == current_index:
            markers.append("◉")  # current
        else:
            markers.append("○")  # not reached
    marker_line = " " * RAIL_MARGIN + ("─" * (RAIL_COLUMN_WIDTH - 1)).join(markers)

    name_line = " " * RAIL_MARGIN + "".join(
        PHASE_DISPLAY_NAMES.get(name, name).ljust(RAIL_COLUMN_WIDTH)
        for name in phase_names
    )
    name_line = name_line.rstrip()

    column_start = RAIL_MARGIN + current_index * RAIL_COLUMN_WIDTH
    detail_indent = " " * (column_start + 4)
    lines = [
        header_line,
        marker_line,
        name_line,
        " " * column_start + "▲",
        " " * column_start
        + f"└── you are here · rail {rail}/{rail_total} "
        + f"· phase {phase} of {phase_total} in stage",
        detail_indent + f"gate status: {card['gate']}",
        detail_indent + f"earliest unmet gate: {earliest_unmet_gate(card)}",
    ]
    required_proof = card.get("required_proof") or []
    if required_proof:
        lines.append(detail_indent + "required proof: " + ", ".join(required_proof))
    lines.append(
        "Legend: ● cleared phase   ◉ current phase (you are here)   "
        "○ phase not reached yet"
    )
    return "\n".join(lines)


def earliest_unmet_gate(card: dict[str, Any]) -> str:
    """Name the current phase gate without confusing it with gate status."""
    if card.get("gate") == "Blocked":
        return f"{card['phase']} blocker gate"
    if card.get("required_proof"):
        return f"{card['phase']} evidence gate"
    return "none in the current validated card"


def render_evidence_status(
    card: dict[str, Any], evidence: list[dict[str, Any]]
) -> list[str]:
    """Summarize exact-bound consumer evidence without re-evaluating the gate."""
    transition = card.get("transition_request") or {}
    expected_revision = transition.get("revision")
    expected_environment = transition.get("environment")
    accepted: dict[str, list[str]] = {}
    for item in evidence:
        if (
            type(item) is not dict
            or item.get("accepted") is not True
            or item.get("revision") != expected_revision
            or item.get("environment") != expected_environment
        ):
            continue
        kind = item.get("kind")
        if type(kind) is str and kind:
            category = evidence_class(kind)
            accepted.setdefault(category, []).append(kind)

    required_by_category: dict[str, list[str]] = {}
    for kind in card.get("required_proof") or []:
        required_by_category.setdefault(evidence_class(kind), []).append(kind)
    lines = ["Evidence status (exact revision and environment):"]
    for category in (
        "source-audited",
        "test-verified",
        "ci-verified",
        "runtime-verified",
        "live-data-verified",
    ):
        kinds = sorted(set(accepted.get(category, [])))
        missing = sorted(set(required_by_category.get(category, [])))
        if missing:
            prefix = (
                "partial (verified: " + ", ".join(kinds) + "; "
                if kinds
                else "pending ("
            )
            value = prefix + "required: " + ", ".join(missing) + ")"
        elif kinds:
            value = "verified (" + ", ".join(kinds) + ")"
        else:
            value = "not claimed"
        lines.append(f"  - {category}: {value}")
    return lines


def evidence_class(kind: str) -> str:
    """Classify one closed evidence identity for human presentation."""
    if kind.startswith("focused-test-report:"):
        return "test-verified"
    return EVIDENCE_CLASS_BY_KIND.get(kind, "project-verified")


def render_project_guidance(
    card: dict[str, Any],
    rail_definition: RailDefinition,
    *,
    evidence: list[dict[str, Any]] | None = None,
    blockers: list[dict[str, Any]] | None = None,
    task_id: str | None = None,
) -> str:
    """Render the [AEC: Project Guidance] block for one validated card.

    This block states where the task sits on the workflow, what to do next,
    and what AEC is and is not allowed to do.
    """
    position = card["rail_position"]
    transition = card.get("transition_request") or {}
    lines = ["[AEC: Project Guidance]", render_rail(card, rail_definition), ""]
    if task_id:
        lines.append(f"Task: {task_id}")
    lines.append(f"Phase: {card['phase']} (stage: {position['stage']})")
    lines.append(f"Gate status: {card['gate']}")
    required_proof = card.get("required_proof") or []
    lines.append(f"Earliest unmet gate: {earliest_unmet_gate(card)}")
    revision = transition.get("revision")
    revision_suffix = f" on exact revision {revision}" if revision else ""
    if required_proof:
        classified = [
            f"{evidence_class(item)}: {item}"
            for item in required_proof
        ]
        lines.append(
            f"Next action: Remain at {card['phase']}; obtain "
            + "; ".join(classified)
            + revision_suffix
            + "."
        )
        lines.append("Required proof: " + "; ".join(classified))
    else:
        rail = int(position["rail"])
        phase_names = rail_definition.phase_names
        if rail < len(phase_names):
            lines.append(
                "Next action: The consumer may evaluate transition to "
                f"{PHASE_DISPLAY_NAMES.get(phase_names[rail], phase_names[rail])}"
                f"{revision_suffix}; AEC will not execute it."
            )
        else:
            lines.append(
                "Next action: Verify the finished condition and retain deployment/"
                f"observation proof{revision_suffix}."
            )
    active_blockers = [
        item
        for item in blockers or []
        if type(item) is dict and item.get("active") is True
    ]
    if active_blockers:
        lines.append(
            "Blockers: "
            + ", ".join(
                f"{item.get('identity')} ({item.get('reason_code')})"
                for item in active_blockers
            )
        )
    elif card["gate"] == "Blocked":
        rationale = card.get("rationale") or {}
        lines.append(
            "Blockers: "
            + str(rationale.get("summary") or "validated blocker details unavailable")
        )
    else:
        lines.append("Blockers: none recorded in the validated card.")
    lines.extend(render_evidence_status(card, evidence or []))
    finished = card.get("finished") or []
    if finished:
        lines.append("Finished when:")
        for item in finished:
            lines.append(f"  - {item}")
    lines.append(
        "Authority: AEC is advisory/read-only "
        "(authoritative={0}, transition_request.executes={1}, "
        "transition_request.mutates={2}). Consumer owns execution, task/GitHub "
        "state, tests, merge, deployment, rollback, and sensitive data.".format(
            card.get("authoritative"),
            transition.get("executes"),
            transition.get("mutates"),
        )
    )
    return "\n".join(lines)


def render_mentoring(card: dict[str, Any]) -> str:
    """Render the [AEC: Mentoring] block for one validated card.

    This block teaches back the lesson behind the current gate, so the
    reason for the gate is clear, not just its name.
    """
    mentoring = card.get("mentoring") or {}
    lines = ["[AEC: Mentoring]"]
    lesson = mentoring.get("lesson")
    if lesson:
        lines.append(f"Lesson: {lesson}")
    why_gate_exists = mentoring.get("why_gate_exists")
    if why_gate_exists:
        lines.append(f"Why this gate exists: {why_gate_exists}")
    recognition_heuristic = mentoring.get("recognition_heuristic")
    if recognition_heuristic:
        lines.append(f"Recognize this situation when: {recognition_heuristic}")
    anti_example = card.get("anti_example")
    if anti_example:
        lines.append(f"Avoid this pattern: {anti_example}")
    good = card.get("good") or []
    if good:
        lines.append("Aim for this pattern:")
        for item in good:
            lines.append(f"  - {item}")
    return "\n".join(lines)


def render_consumer_evidence_context(
    card: dict[str, Any], evidence: list[dict[str, Any]]
) -> str | None:
    """Render rejected consumer facts outside AEC guidance and gate semantics."""
    transition = card.get("transition_request") or {}
    pending = sorted(
        {
            item["kind"]
            for item in evidence
            if type(item) is dict
            and item.get("accepted") is False
            and item.get("revision") == transition.get("revision")
            and item.get("environment") == transition.get("environment")
            and type(item.get("kind")) is str
            and item["kind"]
        }
    )
    if not pending:
        return None
    return (
        "[Consumer: Evidence Context]\n"
        "These consumer-reported facts are not AEC gates or recommendations:\n"
        + "\n".join(
            f"  - {evidence_class(item)}: {item} pending" for item in pending
        )
    )


def render_decision(card: dict[str, Any]) -> str | None:
    """Render the [AEC: Decision] block, or return None if there is no fork.

    Returns None when `decision_support` is null. A card only carries
    `decision_support` when the current step is a material fork with more
    than one reasonable choice.
    """
    support = card.get("decision_support")
    if not support:
        return None

    lines = ["[AEC: Decision]", f"Question: {support['question']}", ""]
    for choice in support.get("choices", []):
        lines.append(f"Choice: {choice['identity']}")
        lines.append(f"  Summary: {choice['summary']}")
        tradeoffs = choice.get("tradeoffs") or {}
        for dimension in TRADEOFF_DIMENSIONS:
            if dimension in tradeoffs:
                lines.append(f"  {dimension}: {tradeoffs[dimension]}")
        lines.append("")

    recommendation = support.get("recommendation") or {}
    lines.append(f"Recommendation: {recommendation.get('choice')}")
    lines.append(f"  Confidence: {recommendation.get('confidence')}")
    principal_uncertainty = recommendation.get("principal_uncertainty")
    if principal_uncertainty:
        lines.append(f"  Principal uncertainty: {principal_uncertainty}")
    expected_result = recommendation.get("expected_result") or {}
    if expected_result:
        lines.append(
            "  Expected result: measure={0}, baseline={1}, target={2}, "
            "direction={3}, unit={4}, threshold={5}".format(
                expected_result.get("measure"),
                expected_result.get("baseline"),
                expected_result.get("target"),
                expected_result.get("direction"),
                expected_result.get("unit"),
                expected_result.get("threshold"),
            )
        )
    revisit_when = recommendation.get("revisit_when") or []
    if revisit_when:
        lines.append("  Revisit when:")
        for item in revisit_when:
            lines.append(f"    - {item}")

    authority = support.get("authority") or {}
    owner = authority.get("owner")
    reason = authority.get("reason")
    if owner and reason:
        lines.append(f"Authority owner: {owner} — {reason}")
    elif owner:
        lines.append(f"Authority owner: {owner}")

    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def render_human(
    card: dict[str, Any],
    rail_definition: RailDefinition,
    *,
    evidence: list[dict[str, Any]] | None = None,
    blockers: list[dict[str, Any]] | None = None,
    task_id: str | None = None,
) -> str:
    """Render one validated card as human coaching text.

    Renders only what the card contains. A field that is absent or empty is
    left out, never replaced with a placeholder.
    """
    sections = [
        render_project_guidance(
            card,
            rail_definition,
            evidence=evidence,
            blockers=blockers,
            task_id=task_id,
        )
    ]
    consumer_context = render_consumer_evidence_context(card, evidence or [])
    if consumer_context is not None:
        sections.append(consumer_context)
    sections.append(render_mentoring(card))
    decision = render_decision(card)
    if decision is not None:
        sections.append(decision)
    return "\n\n".join(sections) + "\n"


def render_compact(card: dict[str, Any]) -> str:
    """Render a stable one-line indicator from the same validated card."""
    required_proof = card.get("required_proof") or []
    if "current-required-checks" in required_proof:
        status = "CI evidence pending"
    elif card.get("gate") == "Needs review":
        status = "review pending"
    elif card.get("gate") == "Blocked":
        status = "blocked"
    elif not required_proof and card.get("gate") == "Ready":
        status = "ready"
    else:
        status = str(card.get("gate", "evidence unavailable")).lower()
    return f"AEC: {card['phase']} · {status}\n"


def render_interaction(
    card: dict[str, Any],
    rail_definition: RailDefinition,
    trigger: str,
    *,
    evidence: list[dict[str, Any]] | None = None,
    blockers: list[dict[str, Any]] | None = None,
    task_id: str | None = None,
) -> str:
    """Select full or compact presentation without selecting lifecycle state.

    The consumer adapter owns the trigger. AEC only applies this closed,
    deterministic presentation rule to the already validated card.
    """
    if trigger not in INTERACTION_TRIGGERS:
        raise RenderFailure(f"unsupported interaction trigger: {trigger}")
    if trigger == "routine-progress":
        return render_compact(card)
    return render_human(
        card,
        rail_definition,
        evidence=evidence,
        blockers=blockers,
        task_id=task_id,
    )
