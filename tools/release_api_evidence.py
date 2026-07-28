#!/usr/bin/env python3
"""Collect authenticated, fail-closed GitHub evidence for one AEC release."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aec.release_manifest import (  # noqa: E402
    CURRENT_RELEASE_VERSION,
    OFFICIAL_REPOSITORY,
    ReleaseManifestFailure,
    canonical_json,
)


API_VERSION = "2026-03-10"
HEX_REVISION = re.compile(r"^[0-9a-f]{40}$")
RELEASE_TAG = re.compile(r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
MAX_TAG_DEPTH = 8


class ApiFailure(RuntimeError):
    """Required GitHub release evidence is missing, malformed, or unsafe."""


@dataclass(frozen=True)
class ApiResponse:
    """One bounded GitHub API response."""

    status: int
    body: str


def _closed_json(text: str, label: str) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ApiFailure(f"{label} contains a duplicate field")
            result[key] = value
        return result

    try:
        value = json.loads(text, object_pairs_hook=reject_duplicates)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ApiFailure(f"{label} is malformed") from error
    if type(value) is not dict:
        raise ApiFailure(f"{label} must be a JSON object")
    return value


def github_get(path: str, token: str) -> ApiResponse:
    """GET one GitHub API resource without persisting Git credentials."""
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "aec-release-evidence",
            "X-GitHub-Api-Version": API_VERSION,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return ApiResponse(response.status, response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            body = error.read().decode("utf-8")
        except (OSError, UnicodeError) as decode_error:
            raise ApiFailure("GitHub API error response is unavailable") from decode_error
        return ApiResponse(error.code, body)
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ApiFailure("GitHub API request failed") from error


def _require_success(response: ApiResponse, label: str) -> dict[str, Any]:
    if type(response.status) is not int or response.status != 200:
        raise ApiFailure(f"{label} lookup did not return HTTP 200")
    return _closed_json(response.body, f"{label} response")


def _revision(value: object, label: str) -> str:
    if type(value) is not str or HEX_REVISION.fullmatch(value) is None:
        raise ApiFailure(f"{label} is not a lowercase 40-character commit")
    return value


def _tag_target(value: object, label: str) -> tuple[str, str]:
    if type(value) is not dict:
        raise ApiFailure(f"{label} lacks an object target")
    target_type = value.get("type")
    if target_type not in {"commit", "tag"}:
        raise ApiFailure(f"{label} target type is unsupported")
    return target_type, _revision(value.get("sha"), f"{label} target")


def collect_release_evidence(
    *,
    repository: str,
    tag: str,
    expected_revision: str,
    token: str,
) -> dict[str, Any]:
    """Resolve exact tag, main lineage, immutability, and release absence."""
    if repository != OFFICIAL_REPOSITORY:
        raise ApiFailure(f"repository must equal {OFFICIAL_REPOSITORY}")
    if type(tag) is not str or RELEASE_TAG.fullmatch(tag) is None:
        raise ApiFailure("release tag must be semantic and start with v")
    if tag != f"v{CURRENT_RELEASE_VERSION}":
        raise ApiFailure(
            f"release tag must equal v{CURRENT_RELEASE_VERSION}"
        )
    expected_revision = _revision(expected_revision, "expected revision")
    if type(token) is not str or not token:
        raise ApiFailure("authenticated GitHub API token is required")

    escaped_tag = urllib.parse.quote(tag, safe="")
    tag_ref = _require_success(
        github_get(
            f"/repos/{repository}/git/ref/tags/{escaped_tag}",
            token,
        ),
        "tag ref",
    )
    target_type, target_sha = _tag_target(tag_ref.get("object"), "tag ref")
    seen = {target_sha}
    depth = 0
    while target_type == "tag":
        depth += 1
        if depth > MAX_TAG_DEPTH:
            raise ApiFailure("annotated tag chain is too deep")
        tag_object = _require_success(
            github_get(f"/repos/{repository}/git/tags/{target_sha}", token),
            "annotated tag",
        )
        target_type, target_sha = _tag_target(
            tag_object.get("object"), "annotated tag"
        )
        if target_type == "tag":
            if target_sha in seen:
                raise ApiFailure("annotated tag chain contains a cycle")
            seen.add(target_sha)

    if target_sha != expected_revision:
        raise ApiFailure("resolved tag revision does not equal expected revision")

    main = _require_success(
        github_get(f"/repos/{repository}/commits/main", token),
        "main",
    )
    main_revision = _revision(main.get("sha"), "main revision")
    if main_revision == expected_revision:
        lineage = "identical"
    else:
        comparison = _require_success(
            github_get(
                f"/repos/{repository}/compare/{expected_revision}...{main_revision}",
                token,
            ),
            "tag-to-main comparison",
        )
        base = comparison.get("base_commit")
        merge_base = comparison.get("merge_base_commit")
        if (
            type(base) is not dict
            or type(merge_base) is not dict
            or _revision(base.get("sha"), "comparison base") != expected_revision
            or _revision(merge_base.get("sha"), "comparison merge base")
            != expected_revision
            or comparison.get("status") != "ahead"
        ):
            raise ApiFailure("release revision is not a proven ancestor of main")
        lineage = "ancestor"

    immutable = _require_success(
        github_get(f"/repos/{repository}/immutable-releases", token),
        "immutable releases",
    )
    if immutable.get("enabled") is not True:
        raise ApiFailure("repository release immutability is not enabled")

    release = github_get(
        f"/repos/{repository}/releases/tags/{escaped_tag}",
        token,
    )
    if release.status == 200:
        existing = _closed_json(release.body, "release response")
        if type(existing.get("draft")) is not bool:
            raise ApiFailure("existing release response lacks a boolean draft field")
        state = "draft" if existing["draft"] else "published"
        raise ApiFailure(f"{state} release already exists")
    if release.status != 404:
        raise ApiFailure("release lookup did not return an authenticated HTTP 404")
    missing = _closed_json(release.body, "missing release response")
    if missing.get("message") != "Not Found":
        raise ApiFailure("release 404 response is ambiguous")

    return {
        "authenticated": True,
        "immutable_releases": True,
        "lineage": lineage,
        "main_revision": main_revision,
        "release": "missing",
        "repository": repository,
        "schema_version": "1.0.0",
        "tag": tag,
        "tag_revision": target_sha,
    }


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="aec-release-api-evidence")
    parser.add_argument("--repository", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--expected-revision", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--github-output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        evidence = collect_release_evidence(
            repository=arguments.repository,
            tag=arguments.tag,
            expected_revision=arguments.expected_revision,
            token=os.environ.get("GH_TOKEN", ""),
        )
        arguments.output.write_text(canonical_json(evidence), encoding="utf-8")
        if arguments.github_output is not None:
            with arguments.github_output.open("a", encoding="utf-8") as stream:
                stream.write(f"release_tag={evidence['tag']}\n")
                stream.write(f"revision={evidence['tag_revision']}\n")
        print(f"PASS authenticated release evidence: {arguments.output}")
    except (ApiFailure, ReleaseManifestFailure, OSError, UnicodeError) as error:
        print(f"FAIL release API evidence: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
