#!/usr/bin/env python3
"""Convert a Foundry VTT PF2e actor export into a Pathbuilder 2e .pbex backup.

The Foundry actor JSON is self-describing (ancestry/class/background/etc. are
carried as embedded items). Pathbuilder's .pbex uses proprietary internal
identifiers; where those are needed (feats, background) we construct them as
``PREFIX_Display Name`` and validate against the tables extracted by
``extract_pathbuilder_tables.py`` (see data/). Anything we cannot confidently
map is left for the user to finish in the Pathbuilder app and reported at the end.

Usage:
    python convert.py <foundry_actor.json> [-o out.pbex]
"""
from __future__ import annotations

import argparse
import json
import re
import uuid
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

# Pathbuilder stores ability boosts as integer indices in this fixed order.
ABILITY_ORDER = ("str", "dex", "con", "int", "wis", "cha")

# Levels at which Pathbuilder tracks ability boosts (its hashMapAbilityBoosts keys).
BOOST_LEVELS = ("1", "5", "10", "15", "20")


def ability_to_index(ability: str) -> int:
    """Map a PF2e ability abbreviation to Pathbuilder's boost index (STR=0..CHA=5)."""
    return ABILITY_ORDER.index(ability.lower())


def boosts_to_indices(abilities: list[str]) -> list[int]:
    """Convert a Foundry boost list (e.g. ["int","dex"]) to Pathbuilder indices.

    Unknown or placeholder tokens (empty strings, "free", partially-built slots)
    are skipped rather than raising, so a half-built actor still converts.
    """
    indices = []
    for a in abilities:
        if a and a.lower() in ABILITY_ORDER:
            indices.append(ability_to_index(a))
    return indices


# --- Money -------------------------------------------------------------------

_DENOMINATIONS = {"pp": "platinum", "gp": "gold", "sp": "silver", "cp": "copper"}


def extract_coins(items: list[dict]) -> dict[str, int]:
    """Sum coin treasure items into {platinum, gold, silver, copper}.

    Coins are treasure items with ``system.stackGroup == "coins"``; their
    denomination is the single key of ``system.price.value`` and the amount is
    ``system.quantity``. Other treasure (gems, art) is ignored here.
    """
    coins = {"platinum": 0, "gold": 0, "silver": 0, "copper": 0}
    for item in items:
        if item.get("type") != "treasure":
            continue
        system = item.get("system", {})
        if system.get("stackGroup") != "coins":
            continue
        price_value = system.get("price", {}).get("value", {})
        qty = system.get("quantity", 0) or 0
        for denom, key in _DENOMINATIONS.items():
            if denom in price_value:
                coins[key] += qty * price_value[denom]
    return coins


# --- Name normalization / id lookup -----------------------------------------

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize(name: str) -> str:
    """Casefold and collapse punctuation/whitespace for tolerant matching."""
    return _NON_ALNUM.sub(" ", name.lower()).strip()


def lookup_id(name: str, table: list[str]) -> str | None:
    """Find the id in ``table`` whose display-name part matches ``name``.

    Ids are ``PREFIX_Display Name``; matching is done on the normalized display
    part so case and punctuation differences don't matter. Returns None on miss.
    """
    target = normalize(name)
    for full_id in table:
        display = full_id.split("_", 1)[1] if "_" in full_id else full_id
        if normalize(display) == target:
            return full_id
    return None


# --- Feat / background id resolution -----------------------------------------

# Foundry feat category -> how the Pathbuilder id prefix is derived.
_CLASS_CATEGORIES = {"class", "classfeature"}
_ANCESTRY_CATEGORIES = {"ancestry", "ancestryfeature", "heritage"}


def feat_prefix(category: str, ancestry_name: str, class_name: str) -> str:
    """Derive the Pathbuilder id prefix for a Foundry feat of ``category``.

    Class feats prefix with the class name, ancestry/heritage feats with the
    ancestry name; skill, general, and everything else share the ``GENERAL``
    family (Pathbuilder has no separate ``SKILL_`` prefix).
    """
    if category in _CLASS_CATEGORIES:
        return class_name.upper()
    if category in _ANCESTRY_CATEGORIES:
        return ancestry_name.upper()
    return "GENERAL"


def resolve_feat_id(
    name: str, prefix: str, feats_by_prefix: dict[str, list[str]]
) -> tuple[str, bool]:
    """Return (feat_id, matched). Prefer a catalog match; else construct the id.

    ``matched`` is False when the id had to be constructed (not present in the
    extracted catalog), so the caller can report it for manual verification.
    """
    catalog = feats_by_prefix.get(prefix, [])
    found = lookup_id(name, catalog)
    if found is not None:
        return found, True
    return f"{prefix}_{name}", False


def resolve_background_id(name: str, backgrounds: list[str]) -> tuple[str, bool]:
    """Return (background_id, matched); construct BACKGROUND_<name> on a miss."""
    found = lookup_id(name, backgrounds)
    if found is not None:
        return found, True
    return f"BACKGROUND_{name}", False


# --- Gear (weapons / armor / equipment / containers) -------------------------

def _carry_type(item: dict) -> str:
    return item.get("system", {}).get("equipped", {}).get("carryType", "")


def build_containers(items: list[dict]) -> dict[str, dict]:
    """Map backpack items to Pathbuilder containers, keyed by the Foundry item id.

    ``backpack`` (whether the container reduces carried bulk) is true only when
    the item actually ignores bulk (``system.bulk.ignored > 0``); ordinary
    pouches and boxes do not.
    """
    containers = {}
    for item in items:
        if item.get("type") == "backpack":
            ignored = item.get("system", {}).get("bulk", {}).get("ignored", 0) or 0
            containers[item["_id"]] = {
                "containerName": item["name"],
                "backpack": ignored > 0,
            }
    return containers


def build_equipment(items: list[dict]) -> list[dict]:
    """Build listPlayerEquipment from equipment/consumable/backpack items.

    Containers (backpacks) are listed here as owned items too, matching
    Pathbuilder's own output (they are cross-referenced with
    ``hashMapEquipmentContainers`` by name); omitting them loses empty
    containers. Quantity is only emitted when it differs from one (so an explicit
    0 for a depleted stack is preserved), and ``inContainerID`` only when the
    item lives inside a container.
    """
    equipment = []
    for item in items:
        if item.get("type") not in ("equipment", "consumable", "backpack"):
            continue
        system = item.get("system", {})
        entry = {"name": item["name"]}
        qty = system.get("quantity", 1)
        if qty is None:
            qty = 1
        if qty != 1:  # keep an explicit 0 (a depleted stack), omit the default 1
            entry["quantity"] = qty
        container_id = system.get("containerId")
        if container_id:
            entry["inContainerID"] = container_id
        equipment.append(entry)
    return equipment


def build_weapons(items: list[dict]) -> list[dict]:
    """Build listPlayerWeapons; stowed weapons carry a ``stowed`` flag."""
    weapons = []
    for item in items:
        if item.get("type") != "weapon":
            continue
        entry = {"weaponName": item["name"], "attackAbilityRef": 0}
        if _carry_type(item) == "stowed":
            entry["stowed"] = True
        weapons.append(entry)
    return weapons


def _partition_armor(items: list[dict]) -> tuple[dict | None, list[dict]]:
    """Split armor into (worn, stowed): the first slotted item is worn, rest stow.

    Everything that is not the single worn item (including any second slotted
    armor) is stowed so no armor is dropped.
    """
    armor = [i for i in items if i.get("type") == "armor"]
    worn_index = next(
        (n for n, i in enumerate(armor)
         if i.get("system", {}).get("equipped", {}).get("inSlot")),
        None,
    )
    worn = {"armorName": armor[worn_index]["name"]} if worn_index is not None else None
    stowed = [
        {"armorName": i["name"]} for n, i in enumerate(armor) if n != worn_index
    ]
    return worn, stowed


def build_armor(items: list[dict]) -> dict:
    """Return the worn (slotted) armor as {armorName: ...}, else {}."""
    worn, _stowed = _partition_armor(items)
    return worn or {}


def build_stowed_armor(items: list[dict]) -> list[dict]:
    """Return carried-but-not-worn armor (Pathbuilder's ``listStowedPlayerArmor``)."""
    _worn, stowed = _partition_armor(items)
    return stowed


# --- Reference tables --------------------------------------------------------

def load_tables(data_dir: Path = DATA_DIR) -> tuple[dict, list]:
    """Load the extracted feat/background catalogues (empty if not generated)."""
    feats_path = data_dir / "feats.json"
    bg_path = data_dir / "backgrounds.json"
    feats = json.loads(feats_path.read_text()) if feats_path.exists() else {}
    backgrounds = json.loads(bg_path.read_text()) if bg_path.exists() else []
    return feats, backgrounds


# --- Assembly ----------------------------------------------------------------

def _first_item(items: list[dict], item_type: str) -> dict | None:
    for item in items:
        if item.get("type") == item_type:
            return item
    return None


def _detail(actor: dict, key: str, subkey: str = "value") -> str:
    return str(actor.get("system", {}).get("details", {}).get(key, {}).get(subkey, "") or "")


def build_save(actor: dict, tables: tuple[dict, list] | None = None) -> tuple[dict, dict]:
    """Assemble the inner Pathbuilder character save plus a conversion report.

    Reliable fields (identity, level, ability boosts, gear, money, languages) are
    populated fully. Fields that depend on undocumented Pathbuilder internals
    (spells, per-level skill increases, class special selections, precise feat
    slot placement) are best-effort or left empty and noted in the report.
    """
    feats_table, backgrounds_table = tables if tables is not None else load_tables()
    items = actor.get("items", [])
    system = actor.get("system", {})
    report: dict = {"feats": [], "warnings": [], "unmatched": [], "collisions": []}

    ancestry_item = _first_item(items, "ancestry")
    class_item = _first_item(items, "class")
    heritage_item = _first_item(items, "heritage")
    background_item = _first_item(items, "background")
    deity_item = _first_item(items, "deity")

    ancestry_name = ancestry_item["name"] if ancestry_item else ""
    class_name = class_item["name"] if class_item else ""

    # Background id (constructed if not in the catalogue).
    background_id = ""
    if background_item:
        background_id, matched = resolve_background_id(
            background_item["name"], backgrounds_table
        )
        if not matched:
            report["unmatched"].append(f"background: {background_id}")

    # Ability boosts by level.
    foundry_boosts = system.get("build", {}).get("attributes", {}).get("boosts", {})
    ability_boosts = {lvl: [] for lvl in BOOST_LEVELS}
    for lvl, abilities in foundry_boosts.items():
        if lvl in ability_boosts and isinstance(abilities, list):
            ability_boosts[lvl] = boosts_to_indices(abilities)

    key_ability = system.get("details", {}).get("keyability", {}).get("value")
    if not isinstance(key_ability, str) or key_ability.lower() not in ABILITY_ORDER:
        report["warnings"].append(
            f"key ability missing/unrecognized ({key_ability!r}); defaulted to STR"
        )
        key_ability = "str"

    # Feats: construct ids and slot names best-effort; report matches/misses.
    feat_selections = _build_feat_selections(
        items, ancestry_name, class_name, heritage_item, feats_table, report
    )

    coins = extract_coins(items)

    languages = [
        lang.title()
        for lang in system.get("details", {}).get("languages", {}).get("value", [])
    ]

    save = {
        "hashMapPlayerSpells": {},
        "webID": "",  # filled by build_pbex
        "characterName": actor.get("name", ""),
        "age": _detail(actor, "age"),
        "deity": deity_item["name"] if deity_item else _detail(actor, "deity"),
        "gender": _detail(actor, "gender"),
        "ancestry": ancestry_name,
        "className": class_name,
        "background": background_id,
        "classOptionalTrainedSkill": "",
        "gold": coins["gold"],
        "silver": coins["silver"],
        "copper": coins["copper"],
        "hashMapAncestryFreeBoostSelections": {},
        "backgroundBoostLimitedSelection": 0,
        "getBackgroundBoostFreeSelection": 0,
        "classKeyAbility": ability_to_index(key_ability),
        "hashMapFeatSelections": feat_selections,
        "hashMapSpecialSelections": {},
        "hashMapAbilityBoosts": ability_boosts,
        "hashMapSkillIncreases": {},
        "hashMapTrainedOnlySkillChoices": {},
        "listStowedPlayerArmor": build_stowed_armor(items),
        "listPlayerWeapons": build_weapons(items),
        "playerArmor": build_armor(items),
        "listPlayerEquipment": build_equipment(items),
        "listDisabledRulebooks": [],
        "hashMapEquipmentContainers": build_containers(items),
        "listLanguages": languages,
        "dialects": [],
        "booksLastChecked": 0,
        "remastered": True,
        "showOutdated": False,
        "showOutdatedSpells": False,
    }
    if coins["platinum"]:
        save["platinum"] = coins["platinum"]

    report["warnings"].append(
        "Spells, per-level skill increases, class special selections, and precise "
        "feat slot placement are not derivable from the Foundry export; finish "
        "these in the Pathbuilder app after importing."
    )
    return save, report


def _build_feat_selections(
    items, ancestry_name, class_name, heritage_item, feats_table, report
) -> dict:
    """Best-effort hashMapFeatSelections keyed by an approximate slot name.

    Slot names in Pathbuilder are '<Ancestry> Feat <lvl>', 'Class Feat <lvl>',
    'Skill Feat <lvl>', 'General Feat <lvl>' and 'Heritage Feat'. We approximate
    the slot number with the feat's taken level. When two feats map to the same
    slot (e.g. an archetype feat Foundry only tags as 'class'), the extra ones
    get a suffixed key that Pathbuilder will not recognize, so each collision is
    recorded in ``report['collisions']`` for the user to place by hand.
    """
    selections: dict = {}

    def add(slot_base: str, feat_id: str):
        if slot_base not in selections:
            selections[slot_base] = feat_id
            return
        report["collisions"].append({"slot": slot_base, "id": feat_id})
        n = 1
        while f"{slot_base} ({n})" in selections:
            n += 1
        selections[f"{slot_base} ({n})"] = feat_id

    if heritage_item:
        prefix = ancestry_name.upper() if ancestry_name else ""
        hid, matched = resolve_feat_id(heritage_item["name"], prefix, feats_table)
        add("Heritage Feat", hid)
        report["feats"].append({"id": hid, "matched": matched, "slot": "Heritage Feat"})
        if not matched:
            report["unmatched"].append(f"heritage: {hid}")

    for item in items:
        if item.get("type") != "feat":
            continue
        system = item.get("system", {})
        category = system.get("category", "")
        # Class/ancestry *features* are granted automatically, not chosen; skip.
        if category in ("classfeature", "ancestryfeature"):
            continue
        # Slot number is the level the feat was TAKEN, not its prerequisite level.
        feat_level = system.get("level") or {}
        level = feat_level.get("taken")
        if level is None:
            level = feat_level.get("value")
        if level is None:
            level = 1
        prefix = feat_prefix(category, ancestry_name, class_name)
        feat_id, matched = resolve_feat_id(item["name"], prefix, feats_table)

        if category == "class":
            slot_base = f"Class Feat {level}"
        elif category == "ancestry":
            slot_base = f"{ancestry_name} Feat {level}"
        elif category == "skill":
            slot_base = f"Skill Feat {level}"
        else:
            slot_base = f"General Feat {level}"
        add(slot_base, feat_id)
        report["feats"].append({"id": feat_id, "matched": matched, "slot": slot_base})
        if not matched:
            report["unmatched"].append(f"feat: {feat_id}")

    return selections


def _character_level(actor: dict) -> int:
    return actor.get("system", {}).get("details", {}).get("level", {}).get("value", 1)


def wrap_pbex(save: dict, actor: dict, web_id: str, timestamp: int) -> dict:
    """Wrap an already-built inner save in the Pathbuilder .pbex backup envelope."""
    save = {**save, "webID": web_id}
    class_level = f"{save['ancestry']} {save['className']} {_character_level(actor)}".strip()
    meta = {
        "characterName": save["characterName"],
        "classLevel": class_level,
        "timestamp": timestamp,
        "webID": web_id,
    }
    return {
        "saves": {web_id: json.dumps(save)},
        "saveIDs": [json.dumps(meta)],
        "portraits": {},
        "customFiles": {},
        "folders": {},
    }


def build_pbex(
    actor: dict,
    web_id: str | None = None,
    timestamp: int = 0,
    tables: tuple[dict, list] | None = None,
) -> dict:
    """Convert an actor and wrap it in a .pbex envelope (convenience wrapper)."""
    web_id = web_id or str(uuid.uuid4())
    save, _report = build_save(actor, tables)
    return wrap_pbex(save, actor, web_id, timestamp)


def _print_report(report: dict, save: dict) -> None:
    feats = report["feats"]
    matched = [f for f in feats if f["matched"]]
    unmatched = [f for f in feats if not f["matched"]]
    print(f"Converted: {save['characterName']} ({save['ancestry']} {save['className']})")
    print(f"  Ability boosts L1: {save['hashMapAbilityBoosts']['1']}")
    print(f"  Money: {save['gold']}gp {save['silver']}sp {save['copper']}cp")
    print(f"  Languages: {', '.join(save['listLanguages'])}")
    print(f"  Feats matched in catalogue: {len(matched)}/{len(feats)}")
    for f in unmatched:
        print(f"    ! constructed (verify in app): {f['id']}  [{f['slot']}]")
    for c in report.get("collisions", []):
        print(f"    ! feat slot collision (place by hand): {c['id']}  wanted [{c['slot']}]")
    print("  NOTE: spells, skill increases, and class special selections were left "
          "empty; complete them in Pathbuilder after import.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("actor", type=Path, help="Foundry VTT actor .json export")
    parser.add_argument("-o", "--out", type=Path, help="output .pbex path")
    args = parser.parse_args()

    actor = json.loads(args.actor.read_text())
    save, report = build_save(actor)  # convert once
    pbex = wrap_pbex(save, actor, web_id=str(uuid.uuid4()), timestamp=0)

    out = args.out or args.actor.with_suffix(".pbex")
    out.write_text(json.dumps(pbex))
    _print_report(report, save)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
