"""TDD suite for the Foundry -> Pathbuilder converter helpers."""
from __future__ import annotations

import json

import convert


class TestAbilityIndex:
    def test_ability_to_index_map(self):
        assert convert.ability_to_index("str") == 0
        assert convert.ability_to_index("dex") == 1
        assert convert.ability_to_index("con") == 2
        assert convert.ability_to_index("int") == 3
        assert convert.ability_to_index("wis") == 4
        assert convert.ability_to_index("cha") == 5

    def test_ability_to_index_is_case_insensitive(self):
        assert convert.ability_to_index("CHA") == 5

    def test_boost_list_conversion(self):
        # Merrit's level-1 boosts from system.build.attributes.boosts["1"].
        assert convert.boosts_to_indices(["int", "dex", "cha", "con"]) == [3, 1, 5, 2]

    def test_empty_boosts(self):
        assert convert.boosts_to_indices([]) == []

    def test_boosts_skip_unknown_tokens(self):
        # Partially-built actors can carry empty/placeholder boost slots; those
        # must be skipped rather than crash the whole conversion.
        assert convert.boosts_to_indices(["int", "", "free", "dex"]) == [3, 1]


class TestMoney:
    def test_sums_coins_by_denomination(self, foundry_actor):
        coins = convert.extract_coins(foundry_actor["items"])
        # Merrit: 12 gp, 53 sp, 0 cp, 0 pp.
        assert coins["gold"] == 12
        assert coins["silver"] == 53
        assert coins["copper"] == 0

    def test_ignores_non_coin_treasure(self):
        items = [
            {"type": "treasure", "name": "Gold Pieces",
             "system": {"stackGroup": "coins", "quantity": 5,
                        "price": {"value": {"gp": 1}}}},
            {"type": "treasure", "name": "Fancy Amulet",
             "system": {"quantity": 9, "price": {"value": {"gp": 3}}}},
        ]
        assert convert.extract_coins(items) == {"platinum": 0, "gold": 5, "silver": 0, "copper": 0}


class TestNormalize:
    def test_lowercases_and_collapses_punctuation(self):
        assert convert.normalize("Scholar of the Ancients") == "scholar of the ancients"
        assert convert.normalize("Anti-Magical") == "anti magical"
        assert convert.normalize("  Fade   Away ") == "fade away"

    def test_lookup_matches_case_and_punct_insensitively(self):
        table = ["BACKGROUND_Anti-Magical", "BACKGROUND_Scout"]
        assert convert.lookup_id("anti magical", table) == "BACKGROUND_Anti-Magical"
        assert convert.lookup_id("SCOUT", table) == "BACKGROUND_Scout"

    def test_lookup_returns_none_on_miss(self):
        assert convert.lookup_id("Nonexistent", ["BACKGROUND_Scout"]) is None


class TestFeatPrefix:
    def test_class_feats_use_class_name(self):
        assert convert.feat_prefix("class", "Halfling", "Summoner") == "SUMMONER"
        assert convert.feat_prefix("classfeature", "Halfling", "Summoner") == "SUMMONER"

    def test_ancestry_feats_use_ancestry_name(self):
        assert convert.feat_prefix("ancestry", "Halfling", "Summoner") == "HALFLING"
        assert convert.feat_prefix("ancestryfeature", "Halfling", "Summoner") == "HALFLING"

    def test_skill_and_general_feats_use_general(self):
        assert convert.feat_prefix("skill", "Halfling", "Summoner") == "GENERAL"
        assert convert.feat_prefix("general", "Halfling", "Summoner") == "GENERAL"


class TestFeatResolution:
    def test_resolves_catalog_feat(self):
        feats = {"SUMMONER": ["SUMMONER_Reinforce Eidolon", "SUMMONER_Expanded Senses"]}
        feat_id, matched = convert.resolve_feat_id("Reinforce Eidolon", "SUMMONER", feats)
        assert feat_id == "SUMMONER_Reinforce Eidolon"
        assert matched is True

    def test_constructs_fallback_when_not_in_catalog(self):
        feats = {"HALFLING": ["HALFLING_Fade Away"]}
        feat_id, matched = convert.resolve_feat_id("Halfling Luck", "HALFLING", feats)
        assert feat_id == "HALFLING_Halfling Luck"
        assert matched is False

    def test_skill_feat_resolves_under_general(self):
        feats = {"GENERAL": ["GENERAL_Battle Medicine", "GENERAL_Quick Identification"]}
        feat_id, matched = convert.resolve_feat_id("Battle Medicine", "GENERAL", feats)
        assert feat_id == "GENERAL_Battle Medicine"
        assert matched is True


class TestBackgroundResolution:
    def test_resolves_catalog_background(self):
        backgrounds = ["BACKGROUND_Scout", "BACKGROUND_Barkeep"]
        bg_id, matched = convert.resolve_background_id("Scout", backgrounds)
        assert bg_id == "BACKGROUND_Scout"
        assert matched is True

    def test_constructs_fallback_background(self):
        bg_id, matched = convert.resolve_background_id("Scholar of the Ancients", [])
        assert bg_id == "BACKGROUND_Scholar of the Ancients"
        assert matched is False


class TestGear:
    def _items(self):
        return [
            {"type": "backpack", "_id": "BAG1", "name": "Backpack",
             "system": {"containerId": None, "bulk": {"ignored": 2}}},
            {"type": "backpack", "_id": "POUCH", "name": "Belt Pouch",
             "system": {"containerId": None, "bulk": {"ignored": 0}}},
            {"type": "equipment", "_id": "E1", "name": "Bedroll",
             "system": {"quantity": 1, "containerId": "BAG1",
                        "equipped": {"carryType": "stowed"}}},
            {"type": "consumable", "_id": "C1", "name": "Chalk",
             "system": {"quantity": 10, "containerId": "BAG1",
                        "equipped": {"carryType": "stowed"}}},
            {"type": "weapon", "_id": "W1", "name": "Dagger",
             "system": {"quantity": 1, "containerId": None,
                        "equipped": {"carryType": "held"}}},
            {"type": "weapon", "_id": "W2", "name": "Alchemist's Fire",
             "system": {"quantity": 1, "containerId": "BAG1",
                        "equipped": {"carryType": "stowed"}}},
            {"type": "armor", "_id": "A1", "name": "Leather Armor",
             "system": {"equipped": {"carryType": "worn", "inSlot": True}}},
            {"type": "armor", "_id": "A2", "name": "Armored Cloak",
             "system": {"equipped": {"carryType": "worn", "inSlot": False}}},
        ]

    def test_containers_keyed_by_id(self):
        containers = convert.build_containers(self._items())
        assert containers["BAG1"] == {"containerName": "Backpack", "backpack": True}

    def test_container_backpack_flag_from_bulk_ignored(self):
        # A container only reduces bulk (backpack:true) when bulk.ignored > 0.
        containers = convert.build_containers(self._items())
        assert containers["POUCH"] == {"containerName": "Belt Pouch", "backpack": False}

    def test_equipment_links_container_and_quantity(self):
        equipment = convert.build_equipment(self._items())
        assert {"name": "Bedroll", "inContainerID": "BAG1"} in equipment
        assert {"name": "Chalk", "quantity": 10, "inContainerID": "BAG1"} in equipment
        # weapons/armor/backpacks are not general equipment entries
        assert all(e["name"] != "Dagger" for e in equipment)

    def test_weapons_carry_stowed_flag(self):
        weapons = convert.build_weapons(self._items())
        held = next(w for w in weapons if w["weaponName"] == "Dagger")
        stowed = next(w for w in weapons if w["weaponName"] == "Alchemist's Fire")
        assert held == {"weaponName": "Dagger", "attackAbilityRef": 0}
        assert stowed["stowed"] is True

    def test_worn_armor_selected_by_slot(self):
        armor = convert.build_armor(self._items())
        assert armor["armorName"] == "Leather Armor"

    def test_no_worn_armor_is_empty(self):
        items = [{"type": "armor", "_id": "A", "name": "Cloak",
                  "system": {"equipped": {"carryType": "worn", "inSlot": False}}}]
        assert convert.build_armor(items) == {}

    def test_unworn_armor_is_kept_as_stowed(self):
        # Carried-but-not-worn armor must not be silently dropped.
        stowed = convert.build_stowed_armor(self._items())
        assert {"armorName": "Armored Cloak"} in stowed
        # the worn (inSlot) armor is not duplicated here
        assert all(a["armorName"] != "Leather Armor" for a in stowed)

    def test_quantity_zero_is_preserved(self):
        items = [{"type": "consumable", "_id": "C", "name": "Empty Vial",
                  "system": {"quantity": 0, "containerId": None,
                             "equipped": {"carryType": "worn"}}}]
        (entry,) = convert.build_equipment(items)
        assert entry == {"name": "Empty Vial", "quantity": 0}

    def test_containers_also_appear_in_equipment_list(self):
        # Pathbuilder lists a container as an owned equipment item too, linked to
        # its container entry by name; omitting it loses empty containers.
        equipment = convert.build_equipment(self._items())
        names = [e["name"] for e in equipment]
        assert "Backpack" in names
        assert "Belt Pouch" in names

    def test_two_worn_armors_keep_the_second_as_stowed(self):
        items = [
            {"type": "armor", "_id": "A1", "name": "Plate",
             "system": {"equipped": {"inSlot": True}}},
            {"type": "armor", "_id": "A2", "name": "Chain",
             "system": {"equipped": {"inSlot": True}}},
        ]
        assert convert.build_armor(items) == {"armorName": "Plate"}
        assert convert.build_stowed_armor(items) == [{"armorName": "Chain"}]


class TestKeyFields:
    def test_identity_and_stats(self, foundry_actor):
        save, _report = convert.build_save(foundry_actor)
        assert save["characterName"] == "Merrit Ashwillow"
        assert save["ancestry"] == "Halfling"
        assert save["className"] == "Summoner"
        assert save["deity"] == "Irori"
        assert save["age"] == "20"
        assert save["gender"] == "Male"

    def test_ability_boosts_and_key_ability(self, foundry_actor):
        save, _ = convert.build_save(foundry_actor)
        assert save["hashMapAbilityBoosts"]["1"] == [3, 1, 5, 2]
        assert save["classKeyAbility"] == 5  # cha

    def test_background_resolved(self, foundry_actor):
        save, _ = convert.build_save(foundry_actor)
        assert save["background"] == "BACKGROUND_Scholar of the Ancients"

    def test_money(self, foundry_actor):
        save, _ = convert.build_save(foundry_actor)
        assert save["gold"] == 12
        assert save["silver"] == 53

    def test_languages_titlecased(self, foundry_actor):
        save, _ = convert.build_save(foundry_actor)
        assert "Elven" in save["listLanguages"]
        assert "Draconic" in save["listLanguages"]

    def test_report_lists_feats(self, foundry_actor):
        _save, report = convert.build_save(foundry_actor)
        matched = {f["id"] for f in report["feats"] if f["matched"]}
        assert "SUMMONER_Reinforce Eidolon" in matched

    def test_feat_slot_uses_taken_level(self):
        # A feat's slot number is the level it was TAKEN, not its prerequisite level.
        items = [
            {"type": "feat", "_id": "F", "name": "Some Class Feat",
             "system": {"category": "class", "level": {"value": 1, "taken": 4}}},
        ]
        report = {"feats": [], "warnings": [], "unmatched": [], "collisions": []}
        selections = convert._build_feat_selections(
            items, "Halfling", "Summoner", None, {}, report
        )
        assert "Class Feat 4" in selections
        assert "Class Feat 1" not in selections

    def test_feat_slot_handles_null_taken(self):
        # `taken: null` must fall back to value, not become "Class Feat None".
        items = [
            {"type": "feat", "_id": "F", "name": "Feat A",
             "system": {"category": "class", "level": {"value": 3, "taken": None}}},
            {"type": "feat", "_id": "G", "name": "Feat B",
             "system": {"category": "class", "level": None}},
        ]
        report = {"feats": [], "warnings": [], "unmatched": [], "collisions": []}
        selections = convert._build_feat_selections(
            items, "Halfling", "Summoner", None, {}, report
        )
        assert "Class Feat 3" in selections
        assert not any("None" in slot for slot in selections)

    def test_feat_collision_is_reported(self):
        items = [
            {"type": "feat", "_id": "F", "name": "Feat A",
             "system": {"category": "class", "level": {"taken": 2}}},
            {"type": "feat", "_id": "G", "name": "Feat B",
             "system": {"category": "class", "level": {"taken": 2}}},
        ]
        report = {"feats": [], "warnings": [], "unmatched": [], "collisions": []}
        convert._build_feat_selections(items, "Halfling", "Summoner", None, {}, report)
        assert report["collisions"], "a slot collision should be reported"

    def test_nonstring_key_ability_defaults_and_warns(self):
        actor = {
            "name": "X", "items": [],
            "system": {"details": {"keyability": {"value": 5}}},
        }
        save, report = convert.build_save(actor, tables=({}, []))
        assert save["classKeyAbility"] == 0  # str
        assert any("key ability" in w for w in report["warnings"])


class TestStowedArmorInSave:
    def test_save_includes_stowed_armor(self, foundry_actor):
        save, _ = convert.build_save(foundry_actor)
        names = {a["armorName"] for a in save["listStowedPlayerArmor"]}
        assert "Leather Armor" in names or "Armored Cloak" in names


class TestWrapper:
    def test_pbex_structure(self, foundry_actor):
        pbex = convert.build_pbex(foundry_actor, web_id="fixed-id", timestamp=123)
        assert set(pbex) == {"saves", "saveIDs", "portraits", "customFiles", "folders"}
        # saves value is a JSON string that decodes to the inner save
        (raw,) = pbex["saves"].values()
        inner = json.loads(raw)
        assert inner["characterName"] == "Merrit Ashwillow"
        assert "fixed-id" in pbex["saves"]

    def test_saveids_metadata(self, foundry_actor):
        pbex = convert.build_pbex(foundry_actor, web_id="fixed-id", timestamp=123)
        meta = json.loads(pbex["saveIDs"][0])
        assert meta["characterName"] == "Merrit Ashwillow"
        assert meta["classLevel"] == "Halfling Summoner 2"
        assert meta["webID"] == "fixed-id"
        assert meta["timestamp"] == 123


class TestShape:
    def test_every_sample_key_present_with_same_type(self, foundry_actor, sample_inner_save):
        save, _ = convert.build_save(foundry_actor)
        for key, sample_val in sample_inner_save.items():
            assert key in save, f"missing key: {key}"
            assert type(save[key]) is type(sample_val), (
                f"{key}: {type(save[key])} != {type(sample_val)}"
            )

    def test_output_roundtrips_as_json(self, foundry_actor):
        pbex = convert.build_pbex(foundry_actor, web_id="x", timestamp=1)
        # whole file and each save must be valid JSON
        reparsed = json.loads(json.dumps(pbex))
        for raw in reparsed["saves"].values():
            json.loads(raw)
