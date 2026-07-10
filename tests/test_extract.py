"""Stage 1 contract: the extractor harvests Pathbuilder internal ids from the bundle."""
from __future__ import annotations

from extract_pathbuilder_tables import harvest_ids


def test_harvest_groups_ids_by_prefix():
    js = 'x="SUMMONER_Reinforce Eidolon";y="GENERAL_Battle Medicine";z="BACKGROUND_Scout";'
    by_prefix = harvest_ids(js)
    assert by_prefix["SUMMONER"] == ["SUMMONER_Reinforce Eidolon"]
    assert by_prefix["GENERAL"] == ["GENERAL_Battle Medicine"]
    assert by_prefix["BACKGROUND"] == ["BACKGROUND_Scout"]


def test_harvest_dedupes_and_sorts():
    js = 'a="ELF_Cavern Elf";b="ELF_Arctic Elf";c="ELF_Cavern Elf";'
    assert harvest_ids(js)["ELF"] == ["ELF_Arctic Elf", "ELF_Cavern Elf"]


def test_extracted_data_files_contain_known_ids(data_dir):
    """The committed data/ tables must contain ids we know exist in the bundle."""
    import json

    backgrounds = json.loads((data_dir / "backgrounds.json").read_text())
    feats = json.loads((data_dir / "feats.json").read_text())

    assert "BACKGROUND_Scout" in backgrounds
    assert "SUMMONER_Reinforce Eidolon" in feats["SUMMONER"]
    assert "SUMMONER_Expanded Senses" in feats["SUMMONER"]
    assert "GENERAL_Battle Medicine" in feats["GENERAL"]
    assert "GENERAL_Quick Identification" in feats["GENERAL"]
