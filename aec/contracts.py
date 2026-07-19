"""Project-neutral normalized input contracts."""

from __future__ import annotations

import re


GITHUB_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
PROJECT_PROFILE_FIELDS = {
    "aec_mode",
    "agent_adapters",
    "lifecycle_authority",
    "profile_version",
    "project",
    "schema_version",
    "workflow",
}


def validate_project_profile(profile: object) -> list[str]:
    """Validate a consumer profile without importing consumer-owned state."""
    if not isinstance(profile, dict):
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
