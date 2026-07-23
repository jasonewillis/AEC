"""Closed validation for AEC teaching and consumer decision context."""

from __future__ import annotations

from typing import Any


MENTORING_FIELDS = {
    "lesson",
    "recognition_heuristic",
    "why_gate_exists",
}
DECISION_CONTEXT_FIELDS = {
    "authority",
    "choices",
    "question",
    "recommendation",
}
AUTHORITY_FIELDS = {"owner", "reason"}
CHOICE_FIELDS = {"identity", "summary", "tradeoffs"}
TRADEOFF_FIELDS = {
    "maintainability",
    "quality",
    "reversibility",
    "risk",
    "scope",
}
RECOMMENDATION_FIELDS = {"choice", "revisit_when", "why"}
AUTHORITY_OWNERS = {"agent", "consumer-owner", "external"}


def _non_empty_string(value: object) -> bool:
    """Return whether value is an exact non-empty string."""
    return type(value) is str and bool(value.strip())


def validate_mentoring(value: object, field: str = "mentoring") -> list[str]:
    """Validate one closed AEC-authored teaching record."""
    if type(value) is not dict or set(value) != MENTORING_FIELDS:
        return [f"{field} fields do not match the contract"]
    return [
        f"{field}.{name} must be a non-empty string"
        for name in sorted(MENTORING_FIELDS)
        if not _non_empty_string(value.get(name))
    ]


def validate_decision_context(
    value: object,
    field: str = "decision_context",
) -> list[str]:
    """Validate optional consumer-owned material-decision context."""
    if value is None:
        return []
    if type(value) is not dict or set(value) != DECISION_CONTEXT_FIELDS:
        return [f"{field} fields do not match the contract"]

    errors: list[str] = []
    if not _non_empty_string(value.get("question")):
        errors.append(f"{field}.question must be a non-empty string")

    authority = value.get("authority")
    if type(authority) is not dict or set(authority) != AUTHORITY_FIELDS:
        errors.append(f"{field}.authority fields do not match the contract")
    else:
        if authority.get("owner") not in AUTHORITY_OWNERS:
            errors.append(f"{field}.authority.owner is unsupported")
        if not _non_empty_string(authority.get("reason")):
            errors.append(f"{field}.authority.reason must be a non-empty string")

    choices = value.get("choices")
    identities: list[str] = []
    if type(choices) is not list or not 2 <= len(choices) <= 3:
        errors.append(f"{field}.choices must contain two or three choices")
    else:
        for index, choice in enumerate(choices):
            choice_field = f"{field}.choices[{index}]"
            if type(choice) is not dict or set(choice) != CHOICE_FIELDS:
                errors.append(f"{choice_field} fields do not match the contract")
                continue
            identity = choice.get("identity")
            if not _non_empty_string(identity):
                errors.append(f"{choice_field}.identity must be a non-empty string")
            else:
                identities.append(identity)
            if not _non_empty_string(choice.get("summary")):
                errors.append(f"{choice_field}.summary must be a non-empty string")
            tradeoffs = choice.get("tradeoffs")
            if type(tradeoffs) is not dict or set(tradeoffs) != TRADEOFF_FIELDS:
                errors.append(
                    f"{choice_field}.tradeoffs fields do not match the contract"
                )
            else:
                errors.extend(
                    f"{choice_field}.tradeoffs.{name} must be a non-empty string"
                    for name in sorted(TRADEOFF_FIELDS)
                    if not _non_empty_string(tradeoffs.get(name))
                )
        if len(identities) != len(set(identities)):
            errors.append(f"{field}.choices identities must be unique")

    recommendation = value.get("recommendation")
    if (
        type(recommendation) is not dict
        or set(recommendation) != RECOMMENDATION_FIELDS
    ):
        errors.append(f"{field}.recommendation fields do not match the contract")
    else:
        choice = recommendation.get("choice")
        if not _non_empty_string(choice):
            errors.append(
                f"{field}.recommendation.choice must be a non-empty string"
            )
        elif choice not in identities:
            errors.append(
                f"{field}.recommendation.choice must identify a declared choice"
            )
        if not _non_empty_string(recommendation.get("why")):
            errors.append(f"{field}.recommendation.why must be a non-empty string")
        revisit_when = recommendation.get("revisit_when")
        if (
            type(revisit_when) is not list
            or not revisit_when
            or not all(_non_empty_string(item) for item in revisit_when)
        ):
            errors.append(
                f"{field}.recommendation.revisit_when must be a non-empty string list"
            )
        elif len(revisit_when) != len(set(revisit_when)):
            errors.append(
                f"{field}.recommendation.revisit_when must contain unique values"
            )
    return errors


def normalized_decision_context(value: object) -> dict[str, Any] | None:
    """Return an already validated decision context with a precise type."""
    if value is None:
        return None
    if type(value) is not dict:
        raise TypeError("decision context must be an object or null")
    return value
