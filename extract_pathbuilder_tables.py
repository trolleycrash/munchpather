#!/usr/bin/env python3
"""Stage 1: extract Pathbuilder 2e internal identifier tables from the app bundle.

The Pathbuilder web app is compiled (Kotlin/JS) and heavily minified, so there is
no clean data catalogue to read. What it *does* contain are thousands of internal
identifier string literals of the form ``PREFIX_Display Name`` (for example
``SUMMONER_Reinforce Eidolon``, ``GENERAL_Battle Medicine``, ``BACKGROUND_Scout``).

We harvest those literals and group them by prefix. The result is a *partial*
catalogue: the bundle only embeds the ids referenced directly in code, not every
feat/background in the game (the full data set is loaded at runtime from
elsewhere). It is still useful as a validation set for the converter, and it
confirms the id naming convention the converter relies on.

The app bundle is Pathbuilder's proprietary source and is not distributed with
this project; save it from your browser and pass its path. The generated tables
in ``data/`` are committed, so the converter runs without re-running this step.

Usage:
    python extract_pathbuilder_tables.py <bundle.js> [-o data_dir]
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

DEFAULT_OUT = Path("data")

# A Pathbuilder internal id, as it appears inside a double-quoted string literal:
#   an all-caps prefix (may itself contain underscores, e.g. SF_SOMETHING),
#   an underscore, then a human-readable display name. The display class includes
#   the punctuation real feat/background names use (parentheses, comma, period,
#   ampersand) so those ids are not truncated at the first such character.
ID_RE = re.compile(r'"([A-Z][A-Z0-9]+(?:_[A-Z0-9]+)*_[A-Z][A-Za-z0-9 :\'\-/(),.&]*)"')


def harvest_ids(text: str) -> dict[str, list[str]]:
    """Return {prefix: sorted unique ids} for every PREFIX_Name literal found."""
    by_prefix: dict[str, set[str]] = defaultdict(set)
    for match in ID_RE.findall(text):
        prefix = match.split("_", 1)[0]
        by_prefix[prefix].add(match.rstrip())
    return {p: sorted(v) for p, v in sorted(by_prefix.items())}


def extract(bundle: Path, out_dir: Path) -> dict[str, list[str]]:
    text = bundle.read_text(encoding="utf-8", errors="replace")
    by_prefix = harvest_ids(text)

    out_dir.mkdir(parents=True, exist_ok=True)

    # feats.json: every non-background family, grouped by prefix.
    feats = {p: ids for p, ids in by_prefix.items() if p != "BACKGROUND"}
    (out_dir / "feats.json").write_text(json.dumps(feats, indent=1, ensure_ascii=False))

    # backgrounds.json: flat list of BACKGROUND_* ids.
    backgrounds = by_prefix.get("BACKGROUND", [])
    (out_dir / "backgrounds.json").write_text(
        json.dumps(backgrounds, indent=1, ensure_ascii=False)
    )

    # index.json: prefix -> count, for a quick overview of coverage.
    index = {p: len(ids) for p, ids in by_prefix.items()}
    (out_dir / "index.json").write_text(json.dumps(index, indent=1, ensure_ascii=False))

    return by_prefix


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "bundle", type=Path,
        help="path to the Pathbuilder web app JS bundle (not distributed here)",
    )
    parser.add_argument("-o", "--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    by_prefix = extract(args.bundle, args.out)
    total = sum(len(v) for v in by_prefix.values())
    print(f"Extracted {total} ids across {len(by_prefix)} prefixes -> {args.out}/")
    for prefix in ("BACKGROUND", "GENERAL", "SUMMONER", "HALFLING"):
        print(f"  {prefix}: {len(by_prefix.get(prefix, []))}")


if __name__ == "__main__":
    main()
