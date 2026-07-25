"""Closed validation for AEC teaching and consumer decision context."""

from __future__ import annotations

import re
from typing import Any


MENTORING_FIELDS = {
    "lesson",
    "recognition_heuristic",
    "why_gate_exists",
}
DECISION_CONTEXT_SCHEMA_VERSION = "2.0.0"
DECISION_CONTEXT_FIELDS = {
    "authority",
    "choices",
    "context",
    "question",
    "recommendation",
    "schema_version",
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
CONTEXT_FIELDS = {"evidence_quality", "revision"}
RECOMMENDATION_FIELDS = {
    "choice",
    "confidence",
    "expected_result",
    "principal_uncertainty",
    "revisit_when",
    "why",
}
EXPECTED_RESULT_FIELDS = {"direction", "measure", "threshold"}
AUTHORITY_OWNERS = {"agent", "consumer-owner", "external"}
RESULT_DIRECTIONS = {"decrease", "hold", "increase"}
# Confidence may never exceed the evidence that supports it.
SUPPORTING_EVIDENCE_QUALITY = {
    "high": {"direct-verified"},
    "medium": {"direct-verified", "indirect"},
    "low": {"direct-verified", "indirect", "assumed"},
}
HEX_REVISION = re.compile(r"^[0-9a-f]{40}$")
# Choice and measure identities are machine references an outcome receipt must be
# able to cite exactly. Prose belongs in summary, why, and threshold.
SLUG_IDENTITY = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


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


def _validate_context(value: object, field: str, revision: object) -> list[str]:
    """Validate that the decision was formed from current, qualified context."""
    if type(value) is not dict or set(value) != CONTEXT_FIELDS:
        return [f"{field} fields do not match the contract"]
    errors: list[str] = []
    context_revision = value.get("revision")
    if type(context_revision) is not str or not HEX_REVISION.fullmatch(
        context_revision
    ):
        errors.append(f"{field}.revision must be a lowercase 40-character Git commit")
    elif revision is not None and context_revision != revision:
        errors.append(f"{field}.revision must equal the resolved revision")
    if value.get("evidence_quality") not in SUPPORTING_EVIDENCE_QUALITY["low"]:
        errors.append(f"{field}.evidence_quality is unsupported")
    return errors


def _validate_expected_result(value: object, field: str) -> list[str]:
    """Validate one declared measurable result for the recommendation."""
    if type(value) is not dict or set(value) != EXPECTED_RESULT_FIELDS:
        return [f"{field} fields do not match the contract"]
    errors: list[str] = []
    measure = value.get("measure")
    if type(measure) is not str or not SLUG_IDENTITY.fullmatch(measure):
        errors.append(f"{field}.measure must be a lowercase hyphenated identity")
    if value.get("direction") not in RESULT_DIRECTIONS:
        errors.append(f"{field}.direction is unsupported")
    if not _non_empty_string(value.get("threshold")):
        errors.append(f"{field}.threshold must be a non-empty string")
    return errors


def validate_decision_context(
    value: object,
    field: str = "decision_context",
    *,
    revision: object = None,
) -> list[str]:
    """Validate optional consumer-owned material-decision context."""
    if value is None:
        return []
    if type(value) is not dict or set(value) != DECISION_CONTEXT_FIELDS:
        return [f"{field} fields do not match the contract"]

    errors: list[str] = []
    if value.get("schema_version") != DECISION_CONTEXT_SCHEMA_VERSION:
        errors.append(
            f"{field}.schema_version must equal {DECISION_CONTEXT_SCHEMA_VERSION}"
        )
    if not _non_empty_string(value.get("question")):
        errors.append(f"{field}.question must be a non-empty string")

    context = value.get("context")
    errors.extend(_validate_context(context, f"{field}.context", revision))

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
            if type(identity) is not str or not SLUG_IDENTITY.fullmatch(identity):
                errors.append(
                    f"{choice_field}.identity must be a lowercase hyphenated identity"
                )
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
        if not _non_empty_string(recommendation.get("principal_uncertainty")):
            errors.append(
                f"{field}.recommendation.principal_uncertainty must be a non-empty string"
            )
        confidence = recommendation.get("confidence")
        if confidence not in SUPPORTING_EVIDENCE_QUALITY:
            errors.append(f"{field}.recommendation.confidence is unsupported")
        elif (
            type(context) is dict
            and context.get("evidence_quality")
            not in SUPPORTING_EVIDENCE_QUALITY[confidence]
        ):
            errors.append(
                f"{field}.recommendation.confidence exceeds the declared evidence quality"
            )
        errors.extend(
            _validate_expected_result(
                recommendation.get("expected_result"),
                f"{field}.recommendation.expected_result",
            )
        )
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
