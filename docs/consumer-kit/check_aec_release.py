#!/usr/bin/env python3
"""Compare one consumer pin with an official AEC release manifest."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OFFICIAL_REPOSITORY = "jasonewillis/AEC"
HEX_REVISION = re.compile(r"^[0-9a-f]{40}$")
SEMANTIC_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
UTC_SECONDS_TIMESTAMP = re.compile(
    r"^[0-9]{4}-(0[1-9]|1[0-2])-([0-2][0-9]|3[01])"
    r"T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$"
)
MANIFEST_FIELDS = {"consumer_update", "contracts", "release", "repository", "schema_version"}
UPDATE_FIELDS = {"auto_merge_allowed", "compatibility", "required_probes"}
RELEASE_FIELDS = {"channel", "notes_url", "published_at", "revision", "tag", "version"}
CONTRACT_FIELDS = {
    "consumer_state",
    "human_render",
    "public_card",
    "resolution_decision",
    "resolution_request",
    "workflow",
}
REQUIRED_PROBES = ["human-render", "material", "routine"]


class UpdateCheckFailure(RuntimeError):
    """The release signal was unavailable, malformed, or unsafe."""


def load_json(path: Path) -> dict[str, Any]:
    def closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise UpdateCheckFailure(f"duplicate JSON field: {key}")
            value[key] = item
        return value

    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=closed_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise UpdateCheckFailure("release manifest is unavailable or malformed") from error
    if type(value) is not dict:
        raise UpdateCheckFailure("release manifest root must be an object")
    return value


def load_pin(path: Path) -> str:
    try:
        revision = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError) as error:
        raise UpdateCheckFailure("AEC pin is unavailable") from error
    if HEX_REVISION.fullmatch(revision) is None:
        raise UpdateCheckFailure("AEC pin must be one lowercase 40-character Git commit")
    return revision


def _timestamp(value: object) -> bool:
    if type(value) is not str or UTC_SECONDS_TIMESTAMP.fullmatch(value) is None:
        return False
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return parsed.tzinfo == timezone.utc and parsed.microsecond == 0


def validate_manifest(value: object) -> list[str]:
    if type(value) is not dict or set(value) != MANIFEST_FIELDS:
        return ["release manifest fields do not match the contract"]
    errors: list[str] = []
    if value.get("schema_version") != "1.0.0":
        errors.append("schema_version must equal 1.0.0")
    if value.get("repository") != OFFICIAL_REPOSITORY:
        errors.append(f"repository must equal {OFFICIAL_REPOSITORY}")

    contracts = value.get("contracts")
    if type(contracts) is not dict or set(contracts) != CONTRACT_FIELDS:
        errors.append("contracts fields do not match the contract")
    elif any(
        type(version) is not str or SEMANTIC_VERSION.fullmatch(version) is None
        for version in contracts.values()
    ):
        errors.append("contract versions must be semantic MAJOR.MINOR.PATCH")

    update = value.get("consumer_update")
    if type(update) is not dict or set(update) != UPDATE_FIELDS:
        errors.append("consumer_update fields do not match the contract")
    else:
        if update.get("auto_merge_allowed") is not False:
            errors.append("auto_merge_allowed must be false")
        if update.get("compatibility") not in {"compatible", "validation-required", "breaking"}:
            errors.append("consumer_update.compatibility is unsupported")
        if update.get("required_probes") != REQUIRED_PROBES:
            errors.append("consumer_update.required_probes do not match the contract")

    release = value.get("release")
    if type(release) is not dict or set(release) != RELEASE_FIELDS:
        errors.append("release fields do not match the contract")
    else:
        version = release.get("version")
        tag = release.get("tag")
        revision = release.get("revision")
        if type(version) is not str or SEMANTIC_VERSION.fullmatch(version) is None:
            errors.append("release.version must be semantic MAJOR.MINOR.PATCH")
        if tag != f"v{version}":
            errors.append("release.tag must equal v<release.version>")
        if type(revision) is not str or HEX_REVISION.fullmatch(revision) is None:
            errors.append("release.revision must be a lowercase 40-character Git commit")
        if release.get("channel") not in {"alpha", "beta", "stable"}:
            errors.append("release.channel is unsupported")
        if not _timestamp(release.get("published_at")):
            errors.append("release.published_at must be RFC 3339 UTC seconds")
        expected_url = f"https://github.com/{OFFICIAL_REPOSITORY}/releases/tag/{tag}"
        if release.get("notes_url") != expected_url:
            errors.append("release.notes_url does not match the official repository and tag")
    return errors


def compare_release(current_revision: str, manifest: object) -> dict[str, object]:
    if HEX_REVISION.fullmatch(current_revision) is None:
        raise UpdateCheckFailure("AEC pin must be one lowercase 40-character Git commit")
    errors = validate_manifest(manifest)
    if errors:
        raise UpdateCheckFailure("; ".join(errors))
    release = manifest["release"]
    update = manifest["consumer_update"]
    return {
        "compatibility": update["compatibility"],
        "current_revision": current_revision,
        "latest_revision": release["revision"],
        "latest_tag": release["tag"],
        "notification": "not_requested",
        "required_probes": update["required_probes"],
        "schema_version": "1.0.0",
        "status": "current" if current_revision == release["revision"] else "update_available",
    }


def notify(result: dict[str, object], repository: str) -> str:
    """Create one consumer-owned update issue, or return its existing state."""
    if result["status"] == "current":
        return "not_needed"
    if REPOSITORY.fullmatch(repository) is None:
        raise UpdateCheckFailure("notification repository must be owner/name")
    title = f"[AEC UPDATE] {result['latest_tag']} available"
    listed = subprocess.run(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            repository,
            "--state",
            "all",
            "--limit",
            "100",
            "--search",
            f'"{title}" in:title',
            "--json",
            "title",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if listed.returncode != 0:
        raise UpdateCheckFailure("consumer issue lookup failed")
    try:
        issues = json.loads(listed.stdout)
    except json.JSONDecodeError as error:
        raise UpdateCheckFailure("consumer issue lookup response is malformed") from error
    if type(issues) is not list or any(
        type(issue) is not dict or set(issue) != {"title"} or type(issue["title"]) is not str
        for issue in issues
    ):
        raise UpdateCheckFailure("consumer issue lookup response is malformed")
    if any(issue["title"] == title for issue in issues):
        return "existing"

    probes = ", ".join(result["required_probes"])
    body = (
        "A reviewed AEC release is available.\n\n"
        f"- Tag: `{result['latest_tag']}`\n"
        f"- Exact revision: `{result['latest_revision']}`\n"
        f"- Compatibility: `{result['compatibility']}`\n"
        f"- Required probes: `{probes}`\n\n"
        "Update `.aec-pin` in a consumer-owned pull request only after the required probes pass. "
        "AEC has not changed this repository or executed the candidate."
    )
    created = subprocess.run(
        [
            "gh",
            "issue",
            "create",
            "--repo",
            repository,
            "--title",
            title,
            "--body",
            body,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if created.returncode != 0:
        raise UpdateCheckFailure("consumer update issue creation failed")
    return "created"


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="check-aec-release")
    parser.add_argument("--pin", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--notify-repository")
    arguments = parser.parse_args(argv)
    try:
        result = compare_release(load_pin(arguments.pin), load_json(arguments.manifest))
        if arguments.notify_repository:
            result["notification"] = notify(result, arguments.notify_repository)
        print(canonical_json(result), end="")
    except UpdateCheckFailure as error:
        print(f"aec update: FAIL: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
