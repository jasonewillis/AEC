#!/usr/bin/env python3
"""Generate or validate the immutable AEC GitHub Release manifest asset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aec.release_manifest import (  # noqa: E402
    ReleaseManifestFailure,
    build_release_manifest,
    canonical_json,
    validate_publication_preflight,
    validate_release_manifest,
)


def load_json(path: Path) -> dict[str, Any]:
    """Load exact JSON and reject duplicate keys or non-object roots."""

    def closed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ReleaseManifestFailure(f"duplicate JSON field: {key}")
            value[key] = item
        return value

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=closed_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ReleaseManifestFailure("release JSON is unavailable or malformed") from error
    if type(value) is not dict:
        raise ReleaseManifestFailure("release JSON root must be an object")
    return value


def parse_arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="aec-release-manifest")
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("--descriptor", type=Path, required=True)
    generate.add_argument("--repository", required=True)
    generate.add_argument("--revision", required=True)
    generate.add_argument("--tag", required=True)
    generate.add_argument("--published-at", required=True)
    generate.add_argument("--output", type=Path, required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("manifest", type=Path)
    preflight = commands.add_parser("preflight")
    preflight.add_argument("--descriptor", type=Path, required=True)
    preflight.add_argument("--repository", required=True)
    preflight.add_argument("--revision", required=True)
    preflight.add_argument("--tag", required=True)
    preflight.add_argument(
        "--main-contains-revision", choices=("true", "false"), required=True
    )
    preflight.add_argument(
        "--immutable-releases-enabled", choices=("true", "false"), required=True
    )
    preflight.add_argument(
        "--existing-release-state",
        choices=("missing", "draft", "published"),
        required=True,
    )
    preflight.add_argument(
        "--token-available", choices=("true", "false"), required=True
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    try:
        if arguments.command == "generate":
            manifest = build_release_manifest(
                load_json(arguments.descriptor),
                repository=arguments.repository,
                revision=arguments.revision,
                tag=arguments.tag,
                published_at=arguments.published_at,
            )
            arguments.output.write_text(canonical_json(manifest), encoding="utf-8")
            print(f"WROTE {arguments.output}")
        elif arguments.command == "validate":
            errors = validate_release_manifest(load_json(arguments.manifest))
            if errors:
                raise ReleaseManifestFailure("; ".join(errors))
            print("PASS release manifest")
        else:
            errors = validate_publication_preflight(
                load_json(arguments.descriptor),
                repository=arguments.repository,
                revision=arguments.revision,
                tag=arguments.tag,
                main_contains_revision=arguments.main_contains_revision == "true",
                immutable_releases_enabled=(
                    arguments.immutable_releases_enabled == "true"
                ),
                existing_release_state=arguments.existing_release_state,
                token_available=arguments.token_available == "true",
            )
            if errors:
                raise ReleaseManifestFailure("; ".join(errors))
            print("PASS release publication preflight")
    except ReleaseManifestFailure as error:
        print(f"FAIL release manifest: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
