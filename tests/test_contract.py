"""Import-detail contract: validate converter output against the real Pathbuilder
.pbex format (schema + types derived from real exports) and the structural rules
Pathbuilder relies on when restoring a backup.

These tests go beyond "does it parse": they assert the output would actually be
understood by Pathbuilder — known fields only, correct types, in-range indices,
resolvable cross-references, and a self-consistent envelope.
"""
from __future__ import annotations

import json
import re

import convert

BOOST_LEVELS = {"1", "5", "10", "15", "20"}
FEAT_ID_RE = re.compile(r"^[A-Z0-9]+(?:_[A-Z0-9]+)*_.+")


def _jtype(v) -> str:
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


def _built(actor):
    save, _ = convert.build_save(actor)
    return save


def _built_pbex(actor):
    return convert.build_pbex(actor, web_id="w-1", timestamp=42)


def _inner(pbex):
    return json.loads(next(iter(pbex["saves"].values())))


class TestFieldContract:
    def test_no_unknown_inner_fields(self, foundry_actor, pbex_schema):
        # Every field we emit must be a real Pathbuilder save field; catches
        # typos and invented keys that Pathbuilder would ignore or choke on.
        allowed = set(pbex_schema["allowed_inner_fields"])
        save = _built(foundry_actor)
        unknown = [k for k in save if k not in allowed]
        assert unknown == [], f"unknown fields not in Pathbuilder schema: {unknown}"

    def test_field_types_match_real_exports(self, foundry_actor, pbex_schema):
        types = pbex_schema["inner_field_types"]
        save = _built(foundry_actor)
        mism = [
            (k, _jtype(save[k]), types[k])
            for k in save
            if k in types and _jtype(save[k]) not in types[k]
        ]
        assert mism == [], f"type mismatches vs real exports: {mism}"

    def test_outer_envelope_matches(self, foundry_actor, pbex_schema):
        pbex = _built_pbex(foundry_actor)
        assert sorted(pbex) == pbex_schema["outer_fields"]


class TestEnvelopeConsistency:
    def test_webid_consistent_across_envelope(self, foundry_actor):
        pbex = _built_pbex(foundry_actor)
        (save_key,) = pbex["saves"].keys()
        inner = _inner(pbex)
        meta = json.loads(pbex["saveIDs"][0])
        assert save_key == inner["webID"] == meta["webID"]

    def test_saves_values_are_encoded_json_strings(self, foundry_actor):
        pbex = _built_pbex(foundry_actor)
        for raw in pbex["saves"].values():
            assert isinstance(raw, str)
            assert isinstance(json.loads(raw), dict)

    def test_saveids_metadata_shape(self, foundry_actor):
        pbex = _built_pbex(foundry_actor)
        meta = json.loads(pbex["saveIDs"][0])
        assert set(meta) >= {"characterName", "classLevel", "timestamp", "webID"}

    def test_index_level_agrees_with_character_level(self, foundry_actor):
        pbex = _built_pbex(foundry_actor)
        inner = _inner(pbex)
        meta = json.loads(pbex["saveIDs"][0])
        assert meta["classLevel"].endswith(str(inner["characterLevel"]))


class TestValueInvariants:
    def test_key_ability_index_in_range(self, foundry_actor):
        assert _built(foundry_actor)["classKeyAbility"] in range(6)

    def test_ability_boosts_keys_and_values(self, foundry_actor):
        boosts = _built(foundry_actor)["hashMapAbilityBoosts"]
        assert set(boosts) <= BOOST_LEVELS
        for level, indices in boosts.items():
            assert isinstance(indices, list)
            assert all(isinstance(i, int) and 0 <= i < 6 for i in indices)

    def test_feat_selection_values_are_prefixed_ids(self, foundry_actor):
        feats = _built(foundry_actor)["hashMapFeatSelections"]
        for slot, feat_id in feats.items():
            assert FEAT_ID_RE.match(feat_id), f"{slot}: bad feat id {feat_id!r}"

    def test_coins_are_non_negative_ints(self, foundry_actor):
        save = _built(foundry_actor)
        for denom in ("gold", "silver", "copper"):
            assert isinstance(save[denom], int) and save[denom] >= 0
        # platinum is present only when non-zero (matches Pathbuilder output)
        assert "platinum" not in save or (isinstance(save["platinum"], int) and save["platinum"] > 0)


class TestCrossReferences:
    def test_container_ids_resolve(self, foundry_actor):
        save = _built(foundry_actor)
        container_ids = set(save["hashMapEquipmentContainers"])
        for entry in save["listPlayerEquipment"]:
            if "inContainerID" in entry:
                assert entry["inContainerID"] in container_ids, (
                    f"{entry['name']} references missing container {entry['inContainerID']}"
                )

    def test_weapon_entries_have_required_fields(self, foundry_actor):
        for w in _built(foundry_actor)["listPlayerWeapons"]:
            assert isinstance(w["weaponName"], str)
            assert isinstance(w["attackAbilityRef"], int)

    def test_armor_entries_have_names(self, foundry_actor):
        save = _built(foundry_actor)
        if save["playerArmor"]:
            assert isinstance(save["playerArmor"]["armorName"], str)
        for a in save["listStowedPlayerArmor"]:
            assert isinstance(a["armorName"], str)
