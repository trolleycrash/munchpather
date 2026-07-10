#!/usr/bin/env python3
"""Regenerate tests/fixtures/pbex_schema.json: the Pathbuilder .pbex format
contract (field names + JSON types) that the contract tests validate against.

The output contains NO character data, only the schema. It is derived from one
or more real Pathbuilder backup exports, optionally augmented with the
authoritative export-field list embedded in the app bundle (pb.js).

Usage:
    python tools/generate_pbex_schema.py <export1.pbex> [export2.pbex ...] [--bundle pb.js]

Neither the exports nor the bundle are distributed with this project (they are
personal data / Pathbuilder's proprietary source); pass your own local copies.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "pbex_schema.json"


def jtype(v) -> str:
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str"
    if isinstance(v, list):
        return "list"
    if isinstance(v, dict):
        return "dict"
    return "null"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("exports", nargs="+", type=Path, help="real .pbex export files")
    parser.add_argument("--bundle", type=Path, help="Pathbuilder app JS bundle (optional)")
    args = parser.parse_args()

    inner_types: dict[str, set[str]] = {}
    outer_fields: set[str] = set()

    for path in args.exports:
        data = json.loads(path.read_text())
        outer_fields.update(data.keys())
        for raw in data.get("saves", {}).values():
            for k, v in json.loads(raw).items():
                t = jtype(v)
                if t != "null":
                    inner_types.setdefault(k, set()).add(t)

    allowed = set(inner_types)
    if args.bundle:
        text = args.bundle.read_text(errors="replace")
        i = text.find('t.wt("characterName"')
        if i != -1:
            allowed |= set(re.findall(r't\.wt\("([^"]+)"', text[i:i + 1600])[:48])

    schema = {
        "outer_fields": sorted(outer_fields),
        "inner_field_types": {k: sorted(t) for k, t in sorted(inner_types.items())},
        "allowed_inner_fields": sorted(allowed),
        "_source": f"{len(args.exports)} export(s)"
        + (" + app bundle export cluster" if args.bundle else ""),
    }
    OUT.write_text(json.dumps(schema, indent=1))
    print(f"Wrote {OUT}: {len(inner_types)} observed fields, {len(allowed)} allowed")


if __name__ == "__main__":
    main()
