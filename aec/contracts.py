"""Project-neutral normalized input contracts."""

from __future__ import annotations

import math
import re
from typing import Any


GITHUB_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
# One closed encoding for every exact integer that crosses a public contract.
# JSON Schema draft 2020-12 accepts 1.0 as an integer, so a JSON number cannot
# express the exact-integer rule that Python enforces. A canonical signed
# decimal string can: no plus sign, no whitespace, no exponent, no decimal
# point, no leading zero except "0" itself, and no negative zero.
CANONICAL_INTEGER = re.compile(r"(?:0|-?[1-9][0-9]*)")
CANONICAL_INTEGER_PATTERN = r"^(?:0|-?[1-9][0-9]*)$(?![\s\S])"
PROJECT_PROFILE_FIELDS = {
    "aec_mode",
    "agent_adapters",
    "lifecycle_authority",
    "profile_version",
    "project",
    "schema_version",
    "workflow",
}


def canonical_integer(value: object) -> bool:
    """Return whether a value is one canonical signed decimal integer string."""
    return type(value) is str and bool(CANONICAL_INTEGER.fullmatch(value))


def normalize_exact_json(value: object) -> Any:
    """Return a detached exact-builtin JSON value or reject the input."""
    return _normalize_exact_json(value, frozenset())


def _normalize_exact_json(value: object, ancestors: frozenset[int]) -> Any:
    """Recursively copy exact JSON values while rejecting reference cycles."""
    if type(value) is float and not math.isfinite(value):
        raise ValueError("JSON numbers must be finite")
    if type(value) is str:
        _validate_json_string(value)
        return value
    if value is None or type(value) in {bool, float, int, str}:
        return value
    marker = id(value)
    if marker in ancestors:
        raise TypeError("JSON containers must be acyclic")
    descendants = ancestors | {marker}
    if type(value) is list:
        return [_normalize_exact_json(item, descendants) for item in value]
    if type(value) is dict:
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if type(key) is not str:
                raise TypeError("JSON object keys must be exact strings")
            _validate_json_string(key)
            normalized[key] = _normalize_exact_json(item, descendants)
        return normalized
    raise TypeError("value must contain only exact JSON builtins")


def _validate_json_string(value: str) -> None:
    """Reject Unicode surrogate code points, which UTF-8 cannot encode."""
    if any(0xD800 <= ord(character) <= 0xDFFF for character in value):
        raise ValueError("JSON strings must contain only Unicode scalar values")


def validate_project_profile(profile: object) -> list[str]:
    """Validate a consumer profile without importing consumer-owned state."""
    try:
        profile = normalize_exact_json(profile)
    except (TypeError, ValueError):
        return ["project profile must contain only exact JSON values"]
    if type(profile) is not dict:
        return ["project profile must be an object"]

    errors: list[str] = []
    if set(profile) != PROJECT_PROFILE_FIELDS:
        errors.append("project profile fields do not match the contract")
    if profile.get("schema_version") != "1.0.0":
        errors.append("project profile schema_version must equal 1.0.0")
    project = profile.get("project")
    if not isinstance(project, str) or not GITHUB_REPOSITORY.fullmatch(project):
        errors.append("consumer project must use owner/repository format")
    profile_version = profile.get("profile_version")
    if not isinstance(profile_version, str) or not profile_version:
        errors.append("consumer profile_version must be a non-empty string")
    if profile.get("workflow") != "ticket-to-pr":
        errors.append("consumer workflow must be ticket-to-pr")
    if profile.get("lifecycle_authority") != "consumer-owned":
        errors.append("consumer must own lifecycle authority")
    if profile.get("aec_mode") != "read-only-mentor":
        errors.append("AEC consumer mode must be read-only-mentor")

    adapters = profile.get("agent_adapters")
    if not isinstance(adapters, list) or not adapters or not all(
        isinstance(item, str) and item.strip() for item in adapters
    ):
        errors.append("agent_adapters must be a non-empty list of non-whitespace strings")
    return errors
