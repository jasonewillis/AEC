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
RAIL_COLUMN_WIDTH = 8
HUMAN_RENDER_CONTRACT_VERSION = "2.0.0"
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
        name.ljust(RAIL_COLUMN_WIDTH) for name in phase_names
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
        detail_indent + f"gate: {card['gate']}",
    ]
    required_proof = card.get("required_proof") or []
    if required_proof:
        lines.append(detail_indent + "blocking: " + ", ".join(required_proof))
    lines.append(
        "Legend: ● cleared phase   ◉ current phase (you are here)   "
        "○ phase not reached yet"
    )
    return "\n".join(lines)


def render_project_guidance(card: dict[str, Any], rail_definition: RailDefinition) -> str:
    """Render the [AEC: Project Guidance] block for one validated card.

    This block states where the task sits on the workflow, what to do next,
    and what AEC is and is not allowed to do.
    """
    position = card["rail_position"]
    transition = card.get("transition_request") or {}
    lines = ["[AEC: Project Guidance]", render_rail(card, rail_definition), ""]
    lines.append(f"Phase: {card['phase']} (stage: {position['stage']})")
    lines.append(f"Gate: {card['gate']}")
    # The public card carries no procedure identity (aec/cards.py
    # PUBLIC_CARD_FIELDS has none), so this names the phase, not a procedure.
    lines.append(f"Recommended next phase: {card['phase']}")
    required_proof = card.get("required_proof") or []
    if required_proof:
        lines.append("Required proof: " + ", ".join(required_proof))
    finished = card.get("finished") or []
    if finished:
        lines.append("Finished when:")
        for item in finished:
            lines.append(f"  - {item}")
    lines.append(
        "Authority: authoritative={0}, transition_request.executes={1}, "
        "transition_request.mutates={2}.".format(
            card.get("authoritative"),
            transition.get("executes"),
            transition.get("mutates"),
        )
    )
    return "\n".join(lines)


def render_mentoring(card: dict[str, Any]) -> str:
    """Render the [AEC: Mentor] block for one validated card.

    This block teaches back the lesson behind the current gate, so the
    reason for the gate is clear, not just its name.
    """
    mentoring = card.get("mentoring") or {}
    lines = ["[AEC: Mentor]"]
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


def render_human(card: dict[str, Any], rail_definition: RailDefinition) -> str:
    """Render one validated card as human coaching text.

    Renders only what the card contains. A field that is absent or empty is
    left out, never replaced with a placeholder.
    """
    sections = [render_project_guidance(card, rail_definition), render_mentoring(card)]
    decision = render_decision(card)
    if decision is not None:
        sections.append(decision)
    return "\n\n".join(sections) + "\n"
