"""Contract tests for authenticated, fail-closed GitHub release evidence."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from tools.release_api_evidence import (
    ApiFailure,
    ApiResponse,
    collect_release_evidence,
)


REPOSITORY = "jasonewillis/AEC"
TAG = "v0.1.0"
REVISION = "61bea570a35de7ae1c60a06dede7e0ca010ad9a7"
MAIN = "b" * 40


def response(status: int, value: object) -> ApiResponse:
    return ApiResponse(status, json.dumps(value))


class ReleaseApiEvidenceTests(unittest.TestCase):
    def test_exact_commit_tag_ancestor_and_missing_release_pass(self) -> None:
        answers = [
            response(200, {"object": {"sha": REVISION, "type": "commit"}}),
            response(200, {"sha": MAIN}),
            response(
                200,
                {
                    "base_commit": {"sha": REVISION},
                    "merge_base_commit": {"sha": REVISION},
                    "status": "ahead",
                },
            ),
            response(200, {"enabled": True}),
            response(404, {"message": "Not Found"}),
        ]

        with patch(
            "tools.release_api_evidence.github_get", side_effect=answers
        ) as github_get:
            evidence = collect_release_evidence(
                repository=REPOSITORY,
                tag=TAG,
                expected_revision=REVISION,
                token="bounded-token",
            )

        self.assertEqual(REVISION, evidence["tag_revision"])
        self.assertEqual(MAIN, evidence["main_revision"])
        self.assertEqual("ancestor", evidence["lineage"])
        self.assertEqual("missing", evidence["release"])
        self.assertTrue(evidence["immutable_releases"])
        self.assertEqual(
            {
                "authenticated",
                "immutable_releases",
                "lineage",
                "main_revision",
                "release",
                "repository",
                "schema_version",
                "tag",
                "tag_revision",
            },
            set(evidence),
        )
        self.assertEqual(5, github_get.call_count)

    def test_annotated_tag_is_dereferenced_to_exact_commit(self) -> None:
        tag_object = "a" * 40
        answers = [
            response(200, {"object": {"sha": tag_object, "type": "tag"}}),
            response(200, {"object": {"sha": REVISION, "type": "commit"}}),
            response(200, {"sha": REVISION}),
            response(200, {"enabled": True}),
            response(404, {"message": "Not Found"}),
        ]

        with patch("tools.release_api_evidence.github_get", side_effect=answers):
            evidence = collect_release_evidence(
                repository=REPOSITORY,
                tag=TAG,
                expected_revision=REVISION,
                token="bounded-token",
            )

        self.assertEqual("identical", evidence["lineage"])
        self.assertEqual(REVISION, evidence["tag_revision"])

    def test_every_missing_malformed_or_moving_fact_fails_closed(self) -> None:
        cases = {
            "missing tag": [response(404, {"message": "Not Found"})],
            "malformed tag": [
                response(200, {"object": {"sha": "main", "type": "commit"}})
            ],
            "unsupported tag target": [
                response(200, {"object": {"sha": "a" * 40, "type": "tree"}})
            ],
            "annotated tag cycle": [
                response(200, {"object": {"sha": "a" * 40, "type": "tag"}}),
                response(200, {"object": {"sha": "a" * 40, "type": "tag"}}),
            ],
            "tag mismatch": [
                response(200, {"object": {"sha": "c" * 40, "type": "commit"}})
            ],
            "missing main": [
                response(200, {"object": {"sha": REVISION, "type": "commit"}}),
                response(404, {"message": "Not Found"}),
            ],
            "nonancestor": [
                response(200, {"object": {"sha": REVISION, "type": "commit"}}),
                response(200, {"sha": MAIN}),
                response(
                    200,
                    {
                        "base_commit": {"sha": REVISION},
                        "merge_base_commit": {"sha": "d" * 40},
                        "status": "diverged",
                    },
                ),
            ],
            "immutable unavailable": [
                response(200, {"object": {"sha": REVISION, "type": "commit"}}),
                response(200, {"sha": REVISION}),
                response(403, {"message": "Forbidden"}),
            ],
            "existing release": [
                response(200, {"object": {"sha": REVISION, "type": "commit"}}),
                response(200, {"sha": REVISION}),
                response(200, {"enabled": True}),
                response(200, {"draft": False}),
            ],
            "existing draft": [
                response(200, {"object": {"sha": REVISION, "type": "commit"}}),
                response(200, {"sha": REVISION}),
                response(200, {"enabled": True}),
                response(200, {"draft": True}),
            ],
        }
        for name, answers in cases.items():
            with self.subTest(name=name):
                with patch(
                    "tools.release_api_evidence.github_get", side_effect=answers
                ):
                    with self.assertRaises(ApiFailure):
                        collect_release_evidence(
                            repository=REPOSITORY,
                            tag=TAG,
                            expected_revision=REVISION,
                            token="bounded-token",
                        )

    def test_missing_inputs_and_transport_failures_fail_closed(self) -> None:
        for replacement in (
            {"repository": "fork/AEC"},
            {"tag": "main"},
            {"tag": "v0.2.0"},
            {"expected_revision": ""},
            {"expected_revision": "A" * 40},
            {"token": ""},
        ):
            with self.subTest(replacement=replacement):
                arguments = {
                    "repository": REPOSITORY,
                    "tag": TAG,
                    "expected_revision": REVISION,
                    "token": "bounded-token",
                    **replacement,
                }
                with self.assertRaises(ApiFailure):
                    collect_release_evidence(**arguments)

        with patch(
            "tools.release_api_evidence.github_get",
            side_effect=ApiFailure("GitHub API request failed"),
        ):
            with self.assertRaises(ApiFailure):
                collect_release_evidence(
                    repository=REPOSITORY,
                    tag=TAG,
                    expected_revision=REVISION,
                    token="bounded-token",
                )


if __name__ == "__main__":
    unittest.main()
