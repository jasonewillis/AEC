#!/usr/bin/env python3
"""Report local coaching value and project impact from AEC outcome receipts."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aec.outcomes import evaluate_outcomes  # noqa: E402


def main(argv: list[str]) -> int:
    """Evaluate one local record file without emitting its location."""
    if len(argv) != 1:
        print("usage: evaluate_outcomes.py <records.json>", file=sys.stderr)
        return 1
    try:
        records = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        print("outcome records could not be read as UTF-8 JSON", file=sys.stderr)
        return 1
    if type(records) is not dict or set(records) != {"records", "schema_version"}:
        print("outcome record file fields do not match the contract", file=sys.stderr)
        return 1
    if records["schema_version"] != "1.0.0":
        print("outcome record file schema_version must equal 1.0.0", file=sys.stderr)
        return 1
    try:
        report = evaluate_outcomes(records["records"])
    except ValueError as error:
        print(str(error), file=sys.stderr)
        return 1
    print(
        json.dumps(
            report,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
    )
    return 1 if report["rejected"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
