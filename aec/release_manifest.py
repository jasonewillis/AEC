"""Build and validate one immutable, consumer-readable AEC release manifest."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from aec._generated.resolver_program import RESOLVER_PROGRAM
from aec.cards import PUBLIC_CARD_SCHEMA_VERSION
from aec.human_render import HUMAN_RENDER_CONTRACT_VERSION


RELEASE_MANIFEST_SCHEMA_VERSION = "1.0.0"
CURRENT_RELEASE_VERSION = "0.2.0"
OFFICIAL_REPOSITORY = "jasonewillis/AEC"
DESCRIPTOR_FIELDS = {
    "channel",
    "compatibility",
    "contracts",
    "release_notes",
    "release_version",
    "repository",
    "schema_version",
}
MANIFEST_FIELDS = {
    "consumer_update",
    "contracts",
    "release",
    "repository",
    "schema_version",
}
RELEASE_FIELDS = {
    "channel",
    "notes_url",
    "published_at",
    "revision",
    "tag",
    "version",
}
CONSUMER_UPDATE_FIELDS = {
    "auto_merge_allowed",
    "compatibility",
    "required_probes",
}
CONTRACT_FIELDS = {
    "consumer_state",
    "human_render",
    "public_card",
    "resolution_decision",
    "resolution_request",
    "workflow",
}
SEMANTIC_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
HEX_REVISION = re.compile(r"^[0-9a-f]{40}$")
UTC_SECONDS_TIMESTAMP = re.compile(
    r"^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])"
    r"T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$"
)
CHANNELS = {"alpha", "beta", "stable"}
COMPATIBILITY = {"compatible", "validation-required", "breaking"}
REQUIRED_PROBES = ["human-render", "material", "routine"]
EXISTING_RELEASE_STATES = {"missing", "draft", "published"}
CONTRACT_VERSIONS = {
    "consumer_state": "1.0.0",
    "human_render": HUMAN_RENDER_CONTRACT_VERSION,
    "public_card": PUBLIC_CARD_SCHEMA_VERSION,
    "resolution_decision": RESOLVER_PROGRAM["decision_schema_version"],
    "resolution_request": "2.0.0",
    "workflow": "1.0.0",
}


class ReleaseManifestFailure(RuntimeError):
    """Release metadata failed closed before publication or consumption."""


def classify_release_lookup(
    exit_code: object, response_text: object, error_text: object
) -> str:
    """Classify one GitHub release lookup without hiding transport failures."""
    if (
        type(exit_code) is not int
        or type(response_text) is not str
        or type(error_text) is not str
    ):
        raise ReleaseManifestFailure("release lookup result is malformed")
    if exit_code != 0:
        if "(HTTP 404)" in error_text:
            return "missing"
        raise ReleaseManifestFailure("release lookup failed without an HTTP 404")
    try:
        response = json.loads(response_text)
    except json.JSONDecodeError as error:
        raise ReleaseManifestFailure("release lookup response is malformed") from error
    if type(response) is not dict or type(response.get("draft")) is not bool:
        raise ReleaseManifestFailure("release lookup response lacks a boolean draft field")
    return "draft" if response["draft"] else "published"


def canonical_json(value: object) -> str:
    """Return deterministic exact JSON with one trailing newline."""
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _timestamp(value: object) -> bool:
    if type(value) is not str or UTC_SECONDS_TIMESTAMP.fullmatch(value) is None:
        return False
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError:
        return False
    return parsed.tzinfo == timezone.utc


def validate_release_descriptor(value: object) -> list[str]:
    """Validate the tracked release descriptor as one closed contract."""
    if type(value) is not dict or set(value) != DESCRIPTOR_FIELDS:
        return ["release descriptor fields do not match the contract"]
    errors: list[str] = []
    if value.get("schema_version") != "1.0.0":
        errors.append("schema_version must equal 1.0.0")
    version = value.get("release_version")
    if type(version) is not str or SEMANTIC_VERSION.fullmatch(version) is None:
        errors.append("release_version must be semantic MAJOR.MINOR.PATCH")
    elif version != CURRENT_RELEASE_VERSION:
        errors.append(f"release_version must equal {CURRENT_RELEASE_VERSION}")
    if value.get("channel") not in CHANNELS:
        errors.append("channel is unsupported")
    if value.get("compatibility") not in COMPATIBILITY:
        errors.append("compatibility is unsupported")
    if value.get("repository") != OFFICIAL_REPOSITORY:
        errors.append(f"repository must equal {OFFICIAL_REPOSITORY}")
    contracts = value.get("contracts")
    if type(contracts) is not dict or set(contracts) != CONTRACT_FIELDS:
        errors.append("contracts fields do not match the contract")
    elif contracts != CONTRACT_VERSIONS:
        errors.append("contracts do not match this AEC release implementation")
    notes = value.get("release_notes")
    expected_notes = f"docs/releases/v{version}.md" if type(version) is str else None
    if type(notes) is not str or notes != expected_notes:
        errors.append("release_notes must match docs/releases/v<release_version>.md")
    return errors


def validate_publication_preflight(
    descriptor: object,
    *,
    repository: str,
    revision: str,
    tag: str,
    main_contains_revision: object,
    immutable_releases_enabled: object,
    existing_release_state: object,
    token_available: object,
) -> list[str]:
    """Fail closed on every fact required before release publication."""
    errors = validate_release_descriptor(descriptor)
    if repository != OFFICIAL_REPOSITORY:
        errors.append(f"repository must equal {OFFICIAL_REPOSITORY}")
    if HEX_REVISION.fullmatch(revision) is None:
        errors.append("revision must be a lowercase 40-character Git commit")
    version = descriptor.get("release_version") if type(descriptor) is dict else None
    if tag != f"v{version}":
        errors.append("tag must equal v<release_version>")
    if main_contains_revision is not True:
        errors.append("release revision must be an ancestor of main")
    if immutable_releases_enabled is not True:
        errors.append("repository release immutability must be enabled")
    if existing_release_state not in EXISTING_RELEASE_STATES:
        errors.append("existing release state is unsupported")
    elif existing_release_state == "published":
        errors.append("published release already exists")
    if token_available is not True:
        errors.append("AEC_RELEASE_TOKEN is required")
    return errors


def build_release_manifest(
    descriptor: object,
    *,
    repository: str,
    revision: str,
    tag: str,
    published_at: str,
) -> dict[str, Any]:
    """Build one manifest from a descriptor and immutable tag facts."""
    errors = validate_release_descriptor(descriptor)
    if repository != OFFICIAL_REPOSITORY:
        errors.append(f"repository must equal {OFFICIAL_REPOSITORY}")
    if type(descriptor) is dict and repository != descriptor.get("repository"):
        errors.append("repository must match the release descriptor")
    if HEX_REVISION.fullmatch(revision) is None:
        errors.append("revision must be a lowercase 40-character Git commit")
    if not _timestamp(published_at):
        errors.append("published_at must be an RFC 3339 UTC timestamp ending in Z")
    version = descriptor.get("release_version") if type(descriptor) is dict else None
    if tag != f"v{version}":
        errors.append("tag must equal v<release_version>")
    if errors:
        raise ReleaseManifestFailure("; ".join(errors))

    manifest = {
        "consumer_update": {
            "auto_merge_allowed": False,
            "compatibility": descriptor["compatibility"],
            "required_probes": list(REQUIRED_PROBES),
        },
        "contracts": dict(descriptor["contracts"]),
        "release": {
            "channel": descriptor["channel"],
            "notes_url": f"https://github.com/{repository}/releases/tag/{tag}",
            "published_at": published_at,
            "revision": revision,
            "tag": tag,
            "version": version,
        },
        "repository": repository,
        "schema_version": RELEASE_MANIFEST_SCHEMA_VERSION,
    }
    manifest_errors = validate_release_manifest(manifest)
    if manifest_errors:
        raise ReleaseManifestFailure("; ".join(manifest_errors))
    return manifest


def validate_release_manifest(value: object) -> list[str]:
    """Validate a release asset without trusting its origin or prose."""
    if type(value) is not dict or set(value) != MANIFEST_FIELDS:
        return ["release manifest fields do not match the contract"]
    errors: list[str] = []
    if value.get("schema_version") != RELEASE_MANIFEST_SCHEMA_VERSION:
        errors.append(
            f"schema_version must equal {RELEASE_MANIFEST_SCHEMA_VERSION}"
        )
    if value.get("repository") != OFFICIAL_REPOSITORY:
        errors.append(f"repository must equal {OFFICIAL_REPOSITORY}")

    contracts = value.get("contracts")
    if type(contracts) is not dict or set(contracts) != CONTRACT_FIELDS:
        errors.append("contracts fields do not match the contract")
    elif contracts != CONTRACT_VERSIONS:
        errors.append("contracts do not match this AEC release implementation")

    update = value.get("consumer_update")
    if type(update) is not dict or set(update) != CONSUMER_UPDATE_FIELDS:
        errors.append("consumer_update fields do not match the contract")
    else:
        if update.get("auto_merge_allowed") is not False:
            errors.append("auto_merge_allowed must be false")
        if update.get("compatibility") not in COMPATIBILITY:
            errors.append("consumer_update.compatibility is unsupported")
        if update.get("required_probes") != REQUIRED_PROBES:
            errors.append("consumer_update.required_probes do not match the contract")

    release = value.get("release")
    if type(release) is not dict or set(release) != RELEASE_FIELDS:
        errors.append("release fields do not match the contract")
    else:
        version = release.get("version")
        tag = release.get("tag")
        repository = value.get("repository")
        if type(version) is not str or SEMANTIC_VERSION.fullmatch(version) is None:
            errors.append("release.version must be semantic MAJOR.MINOR.PATCH")
        elif version != CURRENT_RELEASE_VERSION:
            errors.append(f"release.version must equal {CURRENT_RELEASE_VERSION}")
        if tag != f"v{version}":
            errors.append("release.tag must equal v<release.version>")
        revision = release.get("revision")
        if type(revision) is not str or HEX_REVISION.fullmatch(revision) is None:
            errors.append("release.revision must be a lowercase 40-character Git commit")
        if release.get("channel") not in CHANNELS:
            errors.append("release.channel is unsupported")
        if not _timestamp(release.get("published_at")):
            errors.append("release.published_at must be RFC 3339 UTC")
        expected_url = (
            f"https://github.com/{repository}/releases/tag/{tag}"
            if type(repository) is str and type(tag) is str
            else None
        )
        if release.get("notes_url") != expected_url:
            errors.append("release.notes_url does not match repository and tag")
    return errors
