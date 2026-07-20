import ast
import copy
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from tools import generate_resolver
from tools.generate_resolver import render_program, render_schema, validate_program


ROOT = Path(__file__).resolve().parents[1]
PROGRAM_PATH = ROOT / "config/resolver/resolver-program.json"
SCHEMA_PATH = ROOT / "schemas/resolver-program.schema.json"
GENERATED_PATH = ROOT / "aec/_generated/resolver_program.py"


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


class ResolverProgramTests(unittest.TestCase):
    def test_check_fails_when_only_the_checked_in_schema_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            schema_path = Path(directory) / "resolver-program.schema.json"
            schema_path.write_text("{}\n", encoding="utf-8")
            with mock.patch.object(
                generate_resolver,
                "SCHEMA_PATH",
                schema_path,
                create=True,
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    status = generate_resolver.main(["--check"])

        self.assertEqual(1, status)
        self.assertIn("resolver program schema is stale", output.getvalue())

    def test_check_fails_when_only_the_program_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            program = load_json(PROGRAM_PATH)
            program["outcomes"]["skill_unavailable"]["anti_example"] = (
                "A different anti-example."
            )
            program_path = Path(directory) / "resolver-program.json"
            program_path.write_text(
                json.dumps(program, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            with mock.patch.object(generate_resolver, "PROGRAM_PATH", program_path):
                output = io.StringIO()
                with redirect_stdout(output):
                    status = generate_resolver.main(["--check"])

        self.assertEqual(1, status)
        self.assertIn("generated resolver program is stale", output.getvalue())

    def test_check_fails_when_only_the_generated_artifact_drifts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            generated_path = Path(directory) / "resolver_program.py"
            generated_path.write_text(
                "RESOLVER_PROGRAM = {}\n",
                encoding="utf-8",
            )
            with mock.patch.object(
                generate_resolver,
                "GENERATED_PATH",
                generated_path,
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    status = generate_resolver.main(["--check"])

        self.assertEqual(1, status)
        self.assertIn("generated resolver program is stale", output.getvalue())

    def test_generator_rejects_program_data_outside_the_schema_contract(self) -> None:
        program = load_json(PROGRAM_PATH)
        invalid = copy.deepcopy(program)
        invalid["outcomes"]["skill_unavailable"]["good"] = []

        self.assertEqual(
            ["skill_unavailable.good must be a non-empty string list"],
            validate_program(invalid),
        )

    def test_generator_does_not_treat_json_numbers_as_booleans(self) -> None:
        program = load_json(PROGRAM_PATH)
        invalid = copy.deepcopy(program)
        invalid["outcomes"]["evidence_complete"]["allowed"] = 1

        self.assertEqual(
            ["evidence_complete outcome does not match the contract"],
            validate_program(invalid),
        )

    def test_generated_program_is_current_and_contains_only_literals(self) -> None:
        program = load_json(PROGRAM_PATH)

        self.assertEqual([], validate_program(program))
        self.assertEqual(
            render_program(program),
            GENERATED_PATH.read_text(encoding="utf-8"),
        )
        self.assertEqual(render_schema(), SCHEMA_PATH.read_text(encoding="utf-8"))

        tree = ast.parse(GENERATED_PATH.read_text(encoding="utf-8"))
        self.assertEqual(1, len(tree.body))
        assignment = tree.body[0]
        self.assertIsInstance(assignment, ast.Assign)
        self.assertEqual(["RESOLVER_PROGRAM"], [target.id for target in assignment.targets])

        allowed_nodes = {
            ast.Assign,
            ast.Constant,
            ast.Dict,
            ast.Expr,
            ast.List,
            ast.Load,
            ast.Module,
            ast.Name,
            ast.Store,
            ast.UnaryOp,
            ast.USub,
        }
        self.assertEqual(
            set(),
            {type(node) for node in ast.walk(tree)} - allowed_nodes,
        )
