import json
import math
import unittest
from pathlib import Path

from aec.contracts import normalize_exact_json
from aec.resolver import ResolutionRejection, canonical_resolution_bytes, resolve


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


class ExactJsonNormalizationTests(unittest.TestCase):
    def test_resolve_rejects_request_subclasses_before_invoking_hooks(self) -> None:
        class HostileRequest(dict):
            def get(self, key, default=None):
                raise AssertionError("subclass hook must not run")

        request = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")

        result = resolve(HostileRequest(request), procedures)

        self.assertIsInstance(result, ResolutionRejection)
        self.assertEqual("RESOLUTION_REQUEST_INVALID", result.code)

    def test_resolve_rejects_non_json_request_values_without_leaking_exceptions(
        self,
    ) -> None:
        procedures = load_json(ROOT / "config/procedures/ticket-to-pr.json")
        requests = []

        non_string_key = load_json(
            ROOT / "tests/fixtures/resolver/golden/verify.json"
        )
        non_string_key[1] = "value"
        requests.append(non_string_key)

        non_finite = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        non_finite["policy"]["facts"]["require_exact_revision"] = math.nan
        requests.append(non_finite)

        surrogate = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        surrogate["task_id"] = "\ud800"
        requests.append(surrogate)

        cyclic = load_json(ROOT / "tests/fixtures/resolver/golden/verify.json")
        cyclic["blockers"].append(cyclic)
        requests.append(cyclic)

        for request in requests:
            with self.subTest(request_type=type(request).__name__):
                result = resolve(request, procedures)
                self.assertIsInstance(result, ResolutionRejection)
                self.assertEqual(
                    ("request must contain only exact JSON values",),
                    result.errors,
                )

    def test_accepts_only_exact_json_scalar_types(self) -> None:
        class StringSubclass(str):
            pass

        class IntegerSubclass(int):
            pass

        class FloatSubclass(float):
            pass

        self.assertEqual(
            [None, False, True, 7, 2.5, "text"],
            normalize_exact_json([None, False, True, 7, 2.5, "text"]),
        )
        for value in (StringSubclass("text"), IntegerSubclass(7), FloatSubclass(2.5)):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(TypeError):
                    normalize_exact_json(value)

    def test_rejects_container_subclasses_before_invoking_hooks(self) -> None:
        class HostileList(list):
            def __iter__(self):
                raise AssertionError("subclass hook must not run")

        class HostileDict(dict):
            def items(self):
                raise AssertionError("subclass hook must not run")

        for value in (HostileList(), HostileDict()):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(TypeError):
                    normalize_exact_json(value)

    def test_rejects_every_non_finite_float(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalize_exact_json(value)

    def test_rejects_non_string_keys(self) -> None:
        with self.assertRaises(TypeError):
            normalize_exact_json({1: "value"})

    def test_rejects_direct_and_indirect_cycles(self) -> None:
        direct: list[object] = []
        direct.append(direct)
        indirect: dict[str, object] = {"child": []}
        indirect["child"].append(indirect)

        for value in (direct, indirect):
            with self.subTest(value_type=type(value).__name__):
                with self.assertRaises(TypeError):
                    normalize_exact_json(value)

    def test_allows_shared_acyclic_values_and_returns_a_detached_copy(self) -> None:
        shared = {"items": [1, 2]}
        source = [shared, shared]

        normalized = normalize_exact_json(source)
        source[0]["items"].append(3)

        self.assertEqual([{"items": [1, 2]}, {"items": [1, 2]}], normalized)
        self.assertIsNot(normalized, source)
        self.assertIsNot(normalized[0], normalized[1])

    def test_canonical_bytes_preserve_list_order_sort_keys_and_use_strict_utf8(
        self,
    ) -> None:
        resolution = {
            "b": [2, 1],
            "a": "café",
            "resolution_hash": "ignored",
        }

        self.assertEqual(
            '{"a":"café","b":[2,1]}'.encode("utf-8"),
            canonical_resolution_bytes(resolution),
        )
        for invalid in (
            {"value": math.nan},
            {"value": math.inf},
            {"value": -math.inf},
            {"value": "\ud800"},
        ):
            with self.subTest(invalid=ascii(invalid)):
                with self.assertRaises(ValueError):
                    canonical_resolution_bytes(invalid)

    def test_accepts_unicode_scalars_and_rejects_surrogates_in_keys_and_values(
        self,
    ) -> None:
        self.assertEqual(
            {"café": ["🧭", "\U0010ffff"]},
            normalize_exact_json({"café": ["🧭", "\U0010ffff"]}),
        )
        for value in ("\ud800", "\udfff", {"\ud800": "value"}, {"key": "\udfff"}):
            with self.subTest(value=ascii(value)):
                with self.assertRaises(ValueError):
                    normalize_exact_json(value)
