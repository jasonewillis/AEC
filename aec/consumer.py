"""Pure adapter from caller-owned state into the AEC resolver."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from aec.cards import STAGE_PHASES, project_card
from aec.contracts import normalize_exact_json, validate_project_profile
from aec.mentoring import validate_decision_context
from aec.resolver import (
    ResolutionDecision,
    resolve,
    validate_resolution_request,
)


CONSUMER_STATE_FIELDS = {
    "blockers",
    "capabilities",
    "consumer_profile",
    "effects",
    "environment",
    "evidence",
    "expires_at",
    "observed_at",
    "policy",
    "procedures",
    "provider",
    "revision",
    "schema_version",
    "task",
    "workflow_position",
}
OPTIONAL_CONSUMER_STATE_FIELDS = {"decision_context"}
HEX_REVISION = re.compile(r"^[0-9a-f]{40}$")
PINNED_IDENTITY = re.compile(r"^[A-Za-z0-9_.-]+:[A-Za-z0-9][A-Za-z0-9_.-]*$")
PRIVATE_PATH_PATTERNS = (
    re.compile(r"file://", re.IGNORECASE),
    re.compile(r"(?<![A-Za-z0-9_])~[/\\]"),
    re.compile(r"(?<![A-Za-z0-9_/])/(?!/)[^\s]+"),
    re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[/\\]"),
    re.compile(r"(?<![\\])\\\\[^\\\s]+\\[^\\\s]+"),
    re.compile(r"(?<![A-Za-z0-9_.])\.{1,2}[/\\]"),
)


@dataclass(frozen=True)
class ConsumerCard:
    """Immutable normalized mentoring card rendered from one resolver decision."""

    canonical_bytes: bytes

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-compatible card."""
        value = json.loads(self.canonical_bytes)
        if type(value) is not dict:
            raise TypeError("canonical consumer card must decode to an object")
        return value


@dataclass(frozen=True)
class ConsumerStateRejection:
    """Fail-closed result that deliberately contains no mentoring card."""

    errors: tuple[str, ...]
    code: str
    accepted: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a detached rejection with an explicit empty card."""
        return {
            "accepted": self.accepted,
            "card": None,
            "code": self.code,
            "errors": list(self.errors),
        }


def _exact_object(
    value: object,
    field: str,
    fields: set[str],
) -> tuple[dict[str, Any] | None, list[str]]:
    """Validate one closed object shape."""
    if type(value) is not dict:
        return None, [f"{field} must be an object"]
    if set(value) != fields:
        return value, [f"{field} fields do not match the contract"]
    return value, []


def _non_empty_strings(
    value: dict[str, Any], field: str, names: tuple[str, ...]
) -> list[str]:
    """Validate named fields as exact non-empty strings."""
    return [
        f"{field}.{name} must be a non-empty string"
        for name in names
        if type(value.get(name)) is not str or not value.get(name)
    ]


def _parse_timestamp(value: object, field: str) -> tuple[datetime | None, list[str]]:
    """Parse one closed UTC RFC 3339 timestamp."""
    if type(value) is not str or not value.endswith("Z"):
        return None, [f"{field} must be a UTC RFC 3339 timestamp"]
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError:
        return None, [f"{field} must be a UTC RFC 3339 timestamp"]
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        return None, [f"{field} must be a UTC RFC 3339 timestamp"]
    return parsed, []


def _validate_references(value: object, field: str) -> list[str]:
    """Validate a list of unique pinned procedure references."""
    if type(value) is not list:
        return [f"{field} must be a list"]
    errors: list[str] = []
    references: list[tuple[str, str]] = []
    for index, item in enumerate(value):
        item_field = f"{field}[{index}]"
        if type(item) is not dict or set(item) != {"identity", "revision"}:
            errors.append(f"{item_field} fields do not match the contract")
            continue
        item_errors = _non_empty_strings(
            item, item_field, ("identity", "revision")
        )
        errors.extend(item_errors)
        if not item_errors:
            references.append((item["identity"], item["revision"]))
    if len(references) != len(set(references)):
        errors.append(f"{field} must contain unique references")
    return errors


def _validate_evidence(value: object) -> list[str]:
    """Validate caller-owned evidence facts."""
    if type(value) is not list:
        return ["evidence must be a list"]
    errors: list[str] = []
    for index, item in enumerate(value):
        field = f"evidence[{index}]"
        if type(item) is not dict or set(item) != {
            "accepted",
            "environment",
            "kind",
            "revision",
        }:
            errors.append(f"{field} fields do not match the contract")
            continue
        errors.extend(_non_empty_strings(item, field, ("environment", "kind")))
        if type(item.get("accepted")) is not bool:
            errors.append(f"{field}.accepted must be a boolean")
        revision = item.get("revision")
        if type(revision) is not str or not HEX_REVISION.fullmatch(revision):
            errors.append(f"{field}.revision must be a lowercase 40-character Git commit")
    return errors


def _validate_blockers(value: object) -> list[str]:
    """Validate caller-owned blocker facts without interpreting precedence."""
    if type(value) is not list:
        return ["blockers must be a list"]
    errors: list[str] = []
    for index, item in enumerate(value):
        field = f"blockers[{index}]"
        if type(item) is not dict or set(item) != {
            "active",
            "identity",
            "reason_code",
        }:
            errors.append(f"{field} fields do not match the contract")
            continue
        errors.extend(_non_empty_strings(item, field, ("identity", "reason_code")))
        if type(item.get("active")) is not bool:
            errors.append(f"{field}.active must be a boolean")
    return errors


def validate_consumer_state(state: object) -> list[str]:
    """Validate one project-neutral consumer state record without I/O."""
    try:
        state = normalize_exact_json(state)
    except (TypeError, ValueError):
        return ["consumer state must contain only exact JSON values"]
    if type(state) is not dict:
        return ["consumer state must be an object"]

    keys = set(state)
    errors: list[str] = []
    missing = sorted(CONSUMER_STATE_FIELDS - keys)
    unknown = sorted(keys - CONSUMER_STATE_FIELDS - OPTIONAL_CONSUMER_STATE_FIELDS)
    if missing:
        errors.append(f"missing consumer state fields: {', '.join(missing)}")
    if unknown:
        errors.append(f"unknown consumer state fields: {', '.join(unknown)}")
    if state.get("schema_version") != "1.0.0":
        errors.append("consumer state schema_version must equal 1.0.0")

    provider, provider_errors = _exact_object(
        state.get("provider"), "provider", {"identity", "revision"}
    )
    errors.extend(provider_errors)
    if provider is not None and not provider_errors:
        errors.extend(_non_empty_strings(provider, "provider", ("identity", "revision")))
        revision = provider.get("revision")
        identity = provider.get("identity")
        if (
            type(revision) is str
            and type(identity) is str
            and (
                not PINNED_IDENTITY.fullmatch(revision)
                or not revision.startswith(f"{identity}:")
            )
        ):
            errors.append("provider.revision must pin provider.identity")

    for field in ("task", "revision", "environment"):
        value, value_errors = _exact_object(state.get(field), field, {"identity"})
        errors.extend(value_errors)
        if value is not None and not value_errors:
            errors.extend(_non_empty_strings(value, field, ("identity",)))
    revision_record = state.get("revision")
    if type(revision_record) is dict:
        revision = revision_record.get("identity")
        if type(revision) is not str or not HEX_REVISION.fullmatch(revision):
            errors.append("revision.identity must be a lowercase 40-character Git commit")

    observed_at, observed_errors = _parse_timestamp(
        state.get("observed_at"), "observed_at"
    )
    expires_at, expires_errors = _parse_timestamp(
        state.get("expires_at"), "expires_at"
    )
    errors.extend(observed_errors)
    errors.extend(expires_errors)
    if observed_at is not None and expires_at is not None and observed_at >= expires_at:
        errors.append("observed_at must be before expires_at")

    effects, effects_errors = _exact_object(
        state.get("effects"), "effects", {"executes", "mutates"}
    )
    errors.extend(effects_errors)
    if effects is not None and not effects_errors:
        if type(effects.get("executes")) is not bool:
            errors.append("effects.executes must be a boolean")
        elif effects["executes"] is not False:
            errors.append("effects.executes must equal false")
        if type(effects.get("mutates")) is not bool:
            errors.append("effects.mutates must be a boolean")
        elif effects["mutates"] is not False:
            errors.append("effects.mutates must equal false")

    capabilities, capability_errors = _exact_object(
        state.get("capabilities"),
        "capabilities",
        {"capabilities", "identity", "version"},
    )
    errors.extend(capability_errors)
    if capabilities is not None and not capability_errors:
        errors.extend(
            _non_empty_strings(capabilities, "capabilities", ("identity", "version"))
        )
        values = capabilities.get("capabilities")
        if (
            type(values) is not list
            or not all(type(value) is str and value for value in values)
            or len(values) != len(set(values))
        ):
            errors.append("capabilities.capabilities must be a unique string list")

    errors.extend(
        f"consumer_profile: {error}"
        for error in validate_project_profile(state.get("consumer_profile"))
    )
    errors.extend(_validate_evidence(state.get("evidence")))
    errors.extend(_validate_blockers(state.get("blockers")))
    errors.extend(
        validate_decision_context(
            state.get("decision_context"),
            revision=revision_record.get("identity")
            if type(revision_record) is dict
            else None,
        )
    )

    procedures, procedure_errors = _exact_object(
        state.get("procedures"), "procedures", {"available", "required"}
    )
    errors.extend(procedure_errors)
    if procedures is not None and not procedure_errors:
        errors.extend(_validate_references(procedures.get("available"), "procedures.available"))
        required, required_errors = _exact_object(
            procedures.get("required"),
            "procedures.required",
            {"identity", "revision"},
        )
        errors.extend(required_errors)
        if required is not None and not required_errors:
            errors.extend(
                _non_empty_strings(
                    required, "procedures.required", ("identity", "revision")
                )
            )

    policy, policy_errors = _exact_object(
        state.get("policy"), "policy", {"facts", "identity", "revision"}
    )
    errors.extend(policy_errors)
    if policy is not None and not policy_errors:
        errors.extend(_non_empty_strings(policy, "policy", ("identity", "revision")))
        facts, facts_errors = _exact_object(
            policy.get("facts"),
            "policy.facts",
            {"require_exact_environment", "require_exact_revision"},
        )
        errors.extend(facts_errors)
        if facts is not None and not facts_errors:
            for name in ("require_exact_environment", "require_exact_revision"):
                if facts.get(name) is not True:
                    errors.append(f"policy.facts.{name} must equal true")

    position, position_errors = _exact_object(
        state.get("workflow_position"),
        "workflow_position",
        {"lane", "phase", "stage", "workflow", "workflow_revision"},
    )
    errors.extend(position_errors)
    if position is not None and not position_errors:
        errors.extend(
            _non_empty_strings(
                position,
                "workflow_position",
                ("lane", "phase", "stage", "workflow", "workflow_revision"),
            )
        )
        stage = position.get("stage")
        phase = position.get("phase")
        if stage not in STAGE_PHASES:
            errors.append("workflow_position.stage is unsupported")
        elif phase not in STAGE_PHASES[stage]:
            errors.append("workflow_position.phase does not belong to stage")
        if position.get("workflow") != "ticket-to-pr":
            errors.append("workflow_position.workflow must equal ticket-to-pr")
    return errors


def _nested_strings(value: object) -> list[str]:
    """Return every nested exact string value."""
    if type(value) is dict:
        return [item for nested in value.values() for item in _nested_strings(nested)]
    if type(value) is list:
        return [item for nested in value for item in _nested_strings(nested)]
    return [value] if type(value) is str else []


def _contains_private_path(value: object) -> bool:
    """Return whether nested state exposes a local filesystem path."""
    return any(
        pattern.search(item)
        for item in _nested_strings(value)
        for pattern in PRIVATE_PATH_PATTERNS
    )


def _rejection(code: str, *errors: str) -> ConsumerStateRejection:
    """Build one non-authoritative rejection with no card."""
    return ConsumerStateRejection(tuple(errors), code)


def _canonical_bytes(value: dict[str, Any]) -> bytes:
    """Return stable canonical bytes for one normalized card."""
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8", errors="strict")


def _normalized_request(state: dict[str, Any]) -> dict[str, Any]:
    """Translate accepted caller state into the existing resolver request."""
    position = state["workflow_position"]
    procedures = state["procedures"]
    request = {
        "available_procedures": procedures["available"],
        "blockers": state["blockers"],
        "capability_profile": state["capabilities"],
        "consumer_profile": state["consumer_profile"],
        "environment": state["environment"]["identity"],
        "evidence": state["evidence"],
        "lane": position["lane"],
        "phase": position["phase"],
        "policy": state["policy"],
        "required_procedure": procedures["required"],
        "revision": state["revision"]["identity"],
        "schema_version": "2.0.0",
        "task_id": state["task"]["identity"],
        "workflow": {
            "identity": position["workflow"],
            "revision": position["workflow_revision"],
            "stage": position["stage"],
        },
    }
    if "decision_context" in state:
        request["decision_context"] = state["decision_context"]
    return request


def _render_card(decision: ResolutionDecision) -> ConsumerCard:
    """Render one normalized, non-authoritative card from a resolver decision."""
    return ConsumerCard(_canonical_bytes(project_card(decision.to_dict())))


def resolve_consumer_state(
    state: object,
    procedure_catalog: object,
    *,
    current_time: object,
    expected_environment: object,
    expected_revision: object,
) -> ConsumerCard | ConsumerStateRejection:
    """Validate caller state, invoke the pure resolver, and render one card."""
    try:
        normalized = normalize_exact_json(state)
    except (TypeError, ValueError):
        return _rejection(
            "CONSUMER_STATE_INVALID",
            "consumer state must contain only exact JSON values",
        )
    if type(normalized) is not dict:
        return _rejection("CONSUMER_STATE_INVALID", "consumer state must be an object")
    if _contains_private_path(normalized):
        return _rejection(
            "CONSUMER_STATE_PRIVATE_PATH",
            "consumer state must not contain private filesystem paths",
        )
    effects = normalized.get("effects")
    if type(effects) is dict and (
        effects.get("executes") is True or effects.get("mutates") is True
    ):
        return _rejection(
            "CONSUMER_STATE_EFFECTFUL",
            "consumer state must declare executes=false and mutates=false",
        )
    state_errors = validate_consumer_state(normalized)
    if state_errors:
        return ConsumerStateRejection(tuple(state_errors), "CONSUMER_STATE_INVALID")

    now, now_errors = _parse_timestamp(current_time, "current_time")
    if now_errors:
        return ConsumerStateRejection(tuple(now_errors), "CONSUMER_STATE_INVALID")
    observed_at, _ = _parse_timestamp(normalized["observed_at"], "observed_at")
    expires_at, _ = _parse_timestamp(normalized["expires_at"], "expires_at")
    assert now is not None and observed_at is not None and expires_at is not None
    if now < observed_at or now >= expires_at:
        return _rejection(
            "CONSUMER_STATE_STALE",
            "consumer state is outside its declared freshness window",
        )
    if type(expected_revision) is not str or not HEX_REVISION.fullmatch(
        expected_revision
    ):
        return _rejection(
            "CONSUMER_STATE_INVALID",
            "expected_revision must be a lowercase 40-character Git commit",
        )
    if type(expected_environment) is not str or not expected_environment:
        return _rejection(
            "CONSUMER_STATE_INVALID",
            "expected_environment must be a non-empty string",
        )
    actual_revision = normalized["revision"]["identity"]
    actual_environment = normalized["environment"]["identity"]
    if (
        actual_revision != expected_revision
        or actual_environment != expected_environment
    ):
        return _rejection(
            "CONSUMER_STATE_MISMATCH",
            "consumer state does not match the expected revision and environment",
        )

    request = _normalized_request(normalized)
    request_errors = validate_resolution_request(request)
    if request_errors:
        return ConsumerStateRejection(
            tuple(request_errors), "CONSUMER_STATE_INVALID"
        )
    resolution = resolve(request, procedure_catalog)
    if not isinstance(resolution, ResolutionDecision):
        return ConsumerStateRejection(
            resolution.errors,
            "CONSUMER_STATE_INVALID",
        )
    return _render_card(resolution)
