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

from textwrap import wrap
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


HUMAN_RENDER_CONTRACT_VERSION = "1.3.0"
TEXT_WIDTH = 96
LABEL_WIDTH = 9
LIGHT_RULE = "─" * 64
RAIL_CONNECTOR = "───"
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


def section_heading(label: str, *, fill: str = "═") -> str:
    """Return one portable, high-contrast plain-text section heading."""
    return label + "\n" + fill * 64


def _bracketed_stage_label(label: str, span_width: int) -> str:
    """Return `├─── LABEL ───┤` sized to fill exactly `span_width` columns.

    Falls back to a plain centred label when there is not enough room
    for the minimum bracketed form `├─ LABEL ─┤`, and truncates instead
    of overflowing when the label alone exceeds the span.
    """
    padded = f" {label} "
    if span_width < len(padded) + 2:
        if span_width < len(label):
            return label[:span_width]
        return label.center(span_width)
    filled = padded.center(span_width - 2, "─")
    return "├" + filled + "┤"


def labeled_lines(label: str, value: str) -> list[str]:
    """Wrap one value beneath a stable, scannable terminal label."""
    prefix = (
        f"{label:<{LABEL_WIDTH}}"
        if len(label) < LABEL_WIDTH
        else label + " "
    )
    chunks = wrap(
        str(value),
        width=TEXT_WIDTH - len(prefix),
        break_long_words=True,
        break_on_hyphens=False,
    ) or [""]
    return [prefix + chunks[0], *(" " * len(prefix) + item for item in chunks[1:])]


def concise_recognition(value: str) -> str:
    """Remove renderer-redundant mentoring boilerplate without changing meaning."""
    when_prefix = "Use this procedure when "
    after_prefix = "Use this procedure after "
    if value.startswith(when_prefix):
        remainder = value[len(when_prefix) :]
        return remainder[:1].upper() + remainder[1:]
    if value.startswith(after_prefix):
        remainder = value[len(after_prefix) :]
        return "After " + remainder
    return value


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

    markers = []
    for index in range(len(phase_names)):
        if index < current_index:
            markers.append("●")  # cleared
        elif index == current_index:
            markers.append("◉")  # current
        else:
            markers.append("○")  # not reached
    tokens = [
        f"{PHASE_DISPLAY_NAMES.get(name, name)} {marker}"
        for name, marker in zip(phase_names, markers, strict=True)
    ]
    phase_line = RAIL_CONNECTOR.join(tokens)
    if len(phase_line) > TEXT_WIDTH:
        raise RenderFailure(
            f"workflow rail exceeds the {TEXT_WIDTH}-column human-render contract"
        )

    grouped_phases = tuple(
        phase
        for _, phases in rail_definition.stage_groups
        for phase in phases
    )
    if grouped_phases != phase_names:
        raise RenderFailure("rail stage groups do not match the ordered phase names")
    token_starts: list[int] = []
    cursor = 0
    for token in tokens:
        token_starts.append(cursor)
        cursor += len(token) + len(RAIL_CONNECTOR)
    header_characters = [" "] * len(phase_line)
    phase_cursor = 0
    for label, phases in rail_definition.stage_groups:
        first = phase_cursor
        last = phase_cursor + len(phases) - 1
        span_start = token_starts[first]
        span_end = token_starts[last] + len(tokens[last])
        bracketed = _bracketed_stage_label(label, span_end - span_start)
        for offset, character in enumerate(bracketed):
            header_characters[span_start + offset] = character
        phase_cursor += len(phases)
    header_line = "".join(header_characters).rstrip()

    lines = [
        header_line,
        phase_line,
        f"RAIL · {PHASE_DISPLAY_NAMES.get(card['phase'], card['phase'])}"
        + f" · step {rail}/{rail_total}"
        + f" · {position['stage']} {phase}/{phase_total}",
    ]
    lines.append("● complete   ◉ current   ○ not reached")
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
    lines: list[str] = []
    for category in (
        "source-audited",
        "test-verified",
        "ci-verified",
        "runtime-verified",
        "live-data-verified",
    ):
        kinds = sorted(set(accepted.get(category, [])))
        missing = sorted(set(required_by_category.get(category, [])))
        if not kinds and not missing:
            continue
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
        lines.extend(labeled_lines("EVIDENCE", f"{category} · {value}"))
    if not lines:
        lines.extend(labeled_lines("EVIDENCE", "None claimed."))
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
    lines = [
        section_heading("[AEC: Project Guidance]"),
        render_rail(card, rail_definition),
        LIGHT_RULE,
    ]
    if task_id:
        lines.extend(labeled_lines("TASK", task_id))
    lines.extend(
        labeled_lines(
            "CURRENT",
            f"{PHASE_DISPLAY_NAMES.get(card['phase'], card['phase'])}"
            f" · {position['stage']} · step {position['rail']}/{position['rail_total']}",
        )
    )
    lines.extend(
        labeled_lines(
            "GATE",
            f"{card['gate']} · {earliest_unmet_gate(card)}",
        )
    )
    required_proof = card.get("required_proof") or []
    revision = transition.get("revision")
    if required_proof:
        lines.extend(
            labeled_lines(
                "NEXT",
                f"Stay in {PHASE_DISPLAY_NAMES.get(card['phase'], card['phase'])}. "
                "Get the proof below.",
            )
        )
        proof_by_class: dict[str, list[str]] = {}
        for item in required_proof:
            proof_by_class.setdefault(evidence_class(item), []).append(item)
        for category, items in proof_by_class.items():
            lines.extend(labeled_lines("PROOF", f"{category} · {', '.join(items)}"))
    else:
        rail = int(position["rail"])
        phase_names = rail_definition.phase_names
        if rail < len(phase_names):
            lines.extend(
                labeled_lines(
                    "NEXT",
                    "Check whether "
                    f"{PHASE_DISPLAY_NAMES.get(phase_names[rail], phase_names[rail])} "
                    "is ready. AEC will not move the task.",
                )
            )
        else:
            lines.extend(
                labeled_lines(
                    "NEXT",
                    "Confirm the finished condition. Keep deployment and observation "
                    "proof.",
                )
            )
    if revision:
        lines.extend(labeled_lines("REVISION", revision))
    active_blockers = [
        item
        for item in blockers or []
        if type(item) is dict and item.get("active") is True
    ]
    if active_blockers:
        lines.extend(
            labeled_lines(
                "BLOCKERS",
                ", ".join(
                f"{item.get('identity')} ({item.get('reason_code')})"
                for item in active_blockers
                ),
            )
        )
    elif card["gate"] == "Blocked":
        rationale = card.get("rationale") or {}
        lines.extend(
            labeled_lines(
                "BLOCKERS",
                str(
                    rationale.get("summary")
                    or "Validated blocker details are unavailable."
                ),
            )
        )
    else:
        lines.extend(labeled_lines("BLOCKERS", "None recorded."))
    lines.extend(render_evidence_status(card, evidence or []))
    finished = card.get("finished") or []
    for item in finished:
        lines.extend(labeled_lines("DONE WHEN", item))
    lines.append(LIGHT_RULE)
    lines.extend(
        labeled_lines(
            "AUTHORITY",
            "AEC is advisory and read-only. You own execution, task/GitHub state, "
            "tests, merge, deployment, rollback, and sensitive data.",
        )
    )
    return "\n".join(lines)


def render_mentoring(card: dict[str, Any]) -> str:
    """Render the [AEC: Mentoring] block for one validated card.

    This block teaches back the lesson behind the current gate, so the
    reason for the gate is clear, not just its name.
    """
    mentoring = card.get("mentoring") or {}
    lines = [section_heading("[AEC: Mentoring]")]
    lesson = mentoring.get("lesson")
    if lesson:
        lines.extend(labeled_lines("LESSON", lesson))
    why_gate_exists = mentoring.get("why_gate_exists")
    if why_gate_exists:
        lines.extend(labeled_lines("WHY", why_gate_exists))
    recognition_heuristic = mentoring.get("recognition_heuristic")
    if recognition_heuristic:
        lines.extend(labeled_lines("WHEN", concise_recognition(recognition_heuristic)))
    anti_example = card.get("anti_example")
    if anti_example:
        lines.extend(labeled_lines("AVOID", anti_example))
    good = card.get("good") or []
    for item in good:
        lines.extend(labeled_lines("AIM FOR", item))
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
    lines = [section_heading("[Consumer: Evidence Context]", fill="─")]
    for item in pending:
        lines.extend(
            labeled_lines(
                "PENDING",
                f"{evidence_class(item)} · {item}. Consumer fact only; "
                "not an AEC gate.",
            )
        )
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

    lines = [
        section_heading("[AEC: Decision]"),
        *labeled_lines("QUESTION", support["question"]),
        "",
    ]
    for choice in support.get("choices", []):
        lines.extend(labeled_lines("CHOICE", choice["identity"]))
        lines.extend(labeled_lines("SUMMARY", choice["summary"]))
        tradeoffs = choice.get("tradeoffs") or {}
        for dimension in TRADEOFF_DIMENSIONS:
            if dimension in tradeoffs:
                lines.extend(labeled_lines(dimension.upper(), tradeoffs[dimension]))
        lines.append("")

    recommendation = support.get("recommendation") or {}
    lines.extend(labeled_lines("RECOMMEND", recommendation.get("choice")))
    lines.extend(labeled_lines("CONFIDENCE", recommendation.get("confidence")))
    principal_uncertainty = recommendation.get("principal_uncertainty")
    if principal_uncertainty:
        lines.extend(labeled_lines("UNCERTAINTY", principal_uncertainty))
    expected_result = recommendation.get("expected_result") or {}
    if expected_result:
        lines.extend(
            labeled_lines(
                "EXPECTED",
                "measure={0}, baseline={1}, target={2}, direction={3}, "
                "unit={4}, threshold={5}".format(
                expected_result.get("measure"),
                expected_result.get("baseline"),
                expected_result.get("target"),
                expected_result.get("direction"),
                expected_result.get("unit"),
                expected_result.get("threshold"),
                ),
            )
        )
    revisit_when = recommendation.get("revisit_when") or []
    for item in revisit_when:
        lines.extend(labeled_lines("REVISIT", item))

    authority = support.get("authority") or {}
    owner = authority.get("owner")
    reason = authority.get("reason")
    if owner and reason:
        lines.extend(labeled_lines("OWNER", f"{owner} · {reason}"))
    elif owner:
        lines.extend(labeled_lines("OWNER", owner))

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
    return f"\n{LIGHT_RULE}\n".join(sections) + "\n"


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
