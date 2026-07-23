import copy
import itertools
import json
import os
import subprocess
import sys
import unittest
from dataclasses import asdict
from pathlib import Path

from aec.review_attestation import (
    OfflineReviewFailure,
    OfflineReviewVerification,
    verify_offline_review,
)
from tools.validate_foundation import validate_review_attestation_purity


ROOT = Path(__file__).resolve().parents[1]


def valid_evidence() -> dict[str, object]:
    """Return one exact valid normalized offline-review envelope."""
    bindings = {
        "subject_identity": "subject-1",
        "subject_revision": "revision-2",
        "baseline_revision": "revision-1",
        "review_identity": "review-1",
        "issuer_identity": "issuer-1",
        "receipt_digest": "receipt-1",
        "evidence_digest": "evidence-1",
        "signed_payload_digest": "payload-1",
        "signature_result_identity": "signature-result-1",
        "signer_identity": "signer-1",
        "signer_key_identity": "key-1",
    }
    return {
        **bindings,
        "observations": [
            {
                **bindings,
                "observation_identity": "observation-1",
                "order": 1,
                "review_state": "verified",
                "signature_verified": True,
            }
        ],
    }


class OfflineReviewVerificationTests(unittest.TestCase):
    def assert_failure(self, evidence: object, code: str) -> None:
        result = verify_offline_review(evidence)
        self.assertIs(type(result), OfflineReviewFailure)
        self.assertEqual(code, result.code)

    def test_exact_valid_control_returns_detached_bindings(self) -> None:
        evidence = valid_evidence()
        result = verify_offline_review(evidence)

        self.assertIs(type(result), OfflineReviewVerification)
        self.assertEqual("VERIFIED_OFFLINE", result.status)
        self.assertEqual("subject-1", result.subject_identity)
        self.assertEqual("observation-1", result.latest_observation_identity)
        self.assertEqual(1, result.latest_order)
        expected_bindings = asdict(result)
        expected_bindings.pop("canonical_bytes")
        self.assertEqual(expected_bindings, json.loads(result.canonical_bytes))
        self.assertEqual(
            json.dumps(
                expected_bindings,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8"),
            result.canonical_bytes,
        )

        evidence["subject_identity"] = "mutated"
        evidence["observations"][0]["review_state"] = "failed"
        self.assertEqual("subject-1", result.subject_identity)
        self.assertEqual("VERIFIED_OFFLINE", result.status)

    def test_result_is_immutable(self) -> None:
        result = verify_offline_review(valid_evidence())

        with self.assertRaises((AttributeError, TypeError)):
            result.status = "changed"
        with self.assertRaises((AttributeError, TypeError)):
            result.canonical_bytes = b"changed"

    def test_missing_extra_and_wrong_type_inputs_are_invalid(self) -> None:
        missing = valid_evidence()
        missing.pop("issuer_identity")
        extra = valid_evidence()
        extra["repository"] = "owner/repository"
        wrong_type = valid_evidence()
        wrong_type["subject_identity"] = 1

        for evidence in (missing, extra, wrong_type, [], None):
            with self.subTest(evidence=evidence):
                self.assert_failure(evidence, "INPUT_INVALID")

    def test_subclassed_inputs_are_invalid(self) -> None:
        class DictSubclass(dict):
            pass

        class ListSubclass(list):
            pass

        class StringSubclass(str):
            pass

        cases = []
        root = DictSubclass(valid_evidence())
        cases.append(root)
        observations = valid_evidence()
        observations["observations"] = ListSubclass(observations["observations"])
        cases.append(observations)
        observation = valid_evidence()
        observation["observations"][0] = DictSubclass(observation["observations"][0])
        cases.append(observation)
        identity = valid_evidence()
        identity["issuer_identity"] = StringSubclass("issuer-1")
        cases.append(identity)

        for evidence in cases:
            with self.subTest(evidence=evidence):
                self.assert_failure(evidence, "INPUT_INVALID")

    def test_cycles_and_mutable_aliases_are_invalid(self) -> None:
        cyclic = valid_evidence()
        cyclic["cycle"] = cyclic
        shared_observation = valid_evidence()["observations"][0]
        aliased = valid_evidence()
        aliased["observations"] = [shared_observation, shared_observation]

        self.assert_failure(cyclic, "INPUT_INVALID")
        self.assert_failure(aliased, "INPUT_INVALID")

    def test_empty_identity_and_invalid_order_are_invalid(self) -> None:
        for value in (True, False, 0, -1, 1.0, "1"):
            evidence = valid_evidence()
            evidence["observations"][0]["order"] = value
            with self.subTest(value=value):
                self.assert_failure(evidence, "INPUT_INVALID")

        evidence = valid_evidence()
        evidence["signer_identity"] = ""
        self.assert_failure(evidence, "INPUT_INVALID")

    def test_unknown_review_state_and_non_boolean_signature_are_invalid(self) -> None:
        state = valid_evidence()
        state["observations"][0]["review_state"] = "approved"
        signature = valid_evidence()
        signature["observations"][0]["signature_verified"] = 1

        self.assert_failure(state, "INPUT_INVALID")
        self.assert_failure(signature, "INPUT_INVALID")

    def test_each_binding_mismatch_fails_closed(self) -> None:
        fields = (
            "subject_identity",
            "subject_revision",
            "baseline_revision",
            "review_identity",
            "issuer_identity",
            "receipt_digest",
            "evidence_digest",
            "signed_payload_digest",
            "signature_result_identity",
            "signer_identity",
            "signer_key_identity",
        )
        for field in fields:
            evidence = valid_evidence()
            evidence["observations"][0][field] = "different"
            with self.subTest(field=field):
                self.assert_failure(evidence, "BINDING_MISMATCH")

    def test_mixed_issuers_are_binding_mismatch(self) -> None:
        evidence = valid_evidence()
        newer = copy.deepcopy(evidence["observations"][0])
        newer.update(
            observation_identity="observation-2",
            order=2,
            issuer_identity="issuer-2",
        )
        evidence["observations"].append(newer)

        self.assert_failure(evidence, "BINDING_MISMATCH")

    def test_duplicate_order_or_observation_identity_is_ambiguous(self) -> None:
        duplicate_order = valid_evidence()
        duplicate = copy.deepcopy(duplicate_order["observations"][0])
        duplicate["observation_identity"] = "observation-2"
        duplicate_order["observations"].append(duplicate)

        duplicate_identity = valid_evidence()
        duplicate = copy.deepcopy(duplicate_identity["observations"][0])
        duplicate["order"] = 2
        duplicate_identity["observations"].append(duplicate)

        self.assert_failure(duplicate_order, "ORDER_AMBIGUOUS")
        self.assert_failure(duplicate_identity, "ORDER_AMBIGUOUS")

    def test_latest_unverified_signature_fails_before_review_state(self) -> None:
        evidence = valid_evidence()
        evidence["observations"][0].update(
            review_state="pending", signature_verified=False
        )

        self.assert_failure(evidence, "SIGNATURE_UNVERIFIED")

    def test_newer_nonverified_review_supersedes_older_verified_review(self) -> None:
        for state in ("pending", "failed", "error"):
            evidence = valid_evidence()
            newer = copy.deepcopy(evidence["observations"][0])
            newer.update(
                observation_identity="observation-2",
                order=2,
                review_state=state,
            )
            evidence["observations"].append(newer)
            with self.subTest(state=state):
                self.assert_failure(evidence, "REVIEW_NOT_VERIFIED")

    def test_input_permutations_return_identical_results(self) -> None:
        evidence = valid_evidence()
        for order in (2, 3):
            observation = copy.deepcopy(evidence["observations"][0])
            observation.update(
                observation_identity=f"observation-{order}",
                order=order,
            )
            evidence["observations"].append(observation)

        expected = verify_offline_review(evidence)
        for observations in itertools.permutations(evidence["observations"]):
            candidate = copy.deepcopy(evidence)
            candidate["observations"] = list(observations)
            actual = verify_offline_review(candidate)
            self.assertEqual(expected, actual)
            self.assertEqual(expected.canonical_bytes, actual.canonical_bytes)

    def test_failure_permutations_have_identical_exact_bytes(self) -> None:
        evidence = valid_evidence()
        newer = copy.deepcopy(evidence["observations"][0])
        newer.update(
            observation_identity="observation-2",
            order=2,
            review_state="failed",
        )
        evidence["observations"].append(newer)

        expected = verify_offline_review(evidence)
        self.assertEqual(b'{"code":"REVIEW_NOT_VERIFIED"}', expected.canonical_bytes)
        for observations in itertools.permutations(evidence["observations"]):
            candidate = copy.deepcopy(evidence)
            candidate["observations"] = list(observations)
            actual = verify_offline_review(candidate)
            self.assertEqual(expected, actual)
            self.assertEqual(expected.canonical_bytes, actual.canonical_bytes)

    def test_canonical_bytes_are_stable_across_process_hash_seeds(self) -> None:
        script = """
from tests.test_review_attestation import valid_evidence
from aec.review_attestation import verify_offline_review
evidence = valid_evidence()
newer = dict(evidence["observations"][0])
newer.update(observation_identity="observation-2", order=2)
evidence["observations"].insert(0, newer)
print(verify_offline_review(evidence).canonical_bytes.hex())
"""
        outputs = []
        for seed in ("1", "777", "random"):
            environment = os.environ.copy()
            environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONHASHSEED=seed)
            outputs.append(
                subprocess.check_output(
                    [sys.executable, "-c", script],
                    cwd=os.fspath(os.path.dirname(os.path.dirname(__file__))),
                    env=environment,
                    text=True,
                ).strip()
            )
        self.assertEqual([outputs[0]] * len(outputs), outputs)

    def test_failure_precedence_is_stable(self) -> None:
        invalid = valid_evidence()
        invalid["observations"][0].update(
            order=0,
            issuer_identity="different",
            signature_verified=False,
            review_state="failed",
        )
        mismatch = valid_evidence()
        mismatch["observations"][0].update(
            issuer_identity="different",
            signature_verified=False,
            review_state="failed",
        )
        ambiguous = valid_evidence()
        newer = copy.deepcopy(ambiguous["observations"][0])
        newer.update(signature_verified=False, review_state="failed")
        ambiguous["observations"].append(newer)

        self.assert_failure(invalid, "INPUT_INVALID")
        self.assert_failure(mismatch, "BINDING_MISMATCH")
        self.assert_failure(ambiguous, "ORDER_AMBIGUOUS")

    def test_adversarial_objects_never_escape_exceptions(self) -> None:
        class Hostile:
            def __getattribute__(self, name: str) -> object:
                raise RuntimeError(name)

            def __iter__(self):
                raise RuntimeError("iterated")

        corpus = [Hostile(), object(), {Hostile(): Hostile()}, (Hostile(),)]
        for value in corpus:
            with self.subTest(value=type(value).__name__):
                self.assert_failure(value, "INPUT_INVALID")

    def test_results_do_not_claim_operational_authority(self) -> None:
        success = verify_offline_review(valid_evidence())
        failure = verify_offline_review(None)
        forbidden = (
            "ready",
            "approval",
            "merge",
            "deploy",
            "lifecycle",
            "fresh",
            "authority",
        )

        for result in (success, failure):
            rendered = repr(result).lower()
            for term in forbidden:
                self.assertNotIn(term, rendered)

    def test_foundation_purity_rejects_forbidden_imports_and_calls(self) -> None:
        source = (ROOT / "aec/review_attestation.py").read_text(encoding="utf-8")
        self.assertEqual([], validate_review_attestation_purity(source))
        mutations = {
            "filesystem-import": "\nfrom pathlib import Path\n",
            "environment-import": "\nimport os\n",
            "clock-import": "\nimport time\n",
            "randomness-import": "\nimport random\n",
            "network-import": "\nimport socket\n",
            "process-import": "\nimport subprocess\n",
            "dynamic-import": "\n__import__('os')\n",
            "dynamic-execution": "\neval('1')\n",
            "filesystem-call": "\nopen('evidence.json')\n",
            "rebound-filesystem-call": (
                "\nall = open\nall('/tmp/aec-purity-bypass', 'w')\n"
            ),
            "rebound-dynamic-execution": "\nall = eval\nall('1 + 1')\n",
            "mutated-module-call": (
                "\njson.dumps = open\njson.dumps('/tmp/aec-purity-bypass', 'w')\n"
            ),
        }
        for case_id, mutation in mutations.items():
            with self.subTest(case_id=case_id):
                self.assertTrue(
                    validate_review_attestation_purity(source + mutation),
                    f"{case_id} passed unexpectedly",
                )


if __name__ == "__main__":
    unittest.main()
