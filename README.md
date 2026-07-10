# Foundry VTT → Pathbuilder 2e converter

Converts a Foundry VTT PF2e **actor export** (`fvtt-Actor-*.json`) into a
Pathbuilder 2e **`.pbex` backup** that can be restored into the Pathbuilder app
(Menu → Backup / Restore). Foundry's PF2e system imports *from* Pathbuilder but
never exports back to it; this fills that gap.

## Usage

```bash
# Convert an actor (the reference tables in data/ are already committed).
python3 convert.py fvtt-Actor-YourCharacter.json -o character.pbex
```

The `data/` tables are checked in, so conversion works out of the box. To
regenerate them you need the Pathbuilder web app bundle
(`Pathbuilder2eWebRemastered108b.js`), which is not distributed here (it is
Pathbuilder's proprietary source); save it from your browser and run:

```bash
python3 extract_pathbuilder_tables.py path/to/Pathbuilder2eWebRemastered108b.js
```

Then in Pathbuilder: open the backup/restore screen and import `character.pbex`.

## How it works

Two stages keep the fragile bundle-parsing separate from the conversion logic.

1. `extract_pathbuilder_tables.py` harvests Pathbuilder's internal identifier
   strings (`PREFIX_Display Name`, e.g. `SUMMONER_Reinforce Eidolon`) from the
   compiled Pathbuilder app bundle and writes them to `data/`
   (`feats.json`, `backgrounds.json`, `index.json`). This is a *partial*
   catalogue: the bundle only embeds ids referenced in code, so it serves as a
   validation set for the ids the converter constructs.
2. `convert.py` reads the Foundry actor and builds the inner Pathbuilder save,
   then wraps it in the `.pbex` envelope (`saves`, `saveIDs`, `portraits`,
   `customFiles`, `folders`).

### Ability boost index

Pathbuilder stores boosts as integer indices in this fixed order:

| index | 0 | 1 | 2 | 3 | 4 | 5 |
|-------|-----|-----|-----|-----|-----|-----|
| ability | STR | DEX | CON | INT | WIS | CHA |

The same order is used for `classKeyAbility`, `getBackgroundBoostFreeSelection`,
`backgroundBoostLimitedSelection`, and `hashMapAncestryFreeBoostSelections`.

## What converts reliably

Character name, age, gender, deity; ancestry / class labels; level; ability
boosts and key ability; money (coins); languages; weapons, worn armour,
equipment, and containers; background (validated or constructed as
`BACKGROUND_<name>`); class/ancestry/skill feats (validated or constructed).

## Known limitations (finish in the Pathbuilder app)

These depend on undocumented Pathbuilder internals not derivable from the Foundry
export, and are left empty or approximate:

1. Spells (`hashMapPlayerSpells`).
2. Per-level skill increases and trained-skill choices.
3. Class special selections (eidolon type, doctrine, divine font, etc.).
4. **Feat slot placement.** Feat *ids* are mapped, but Pathbuilder's exact slot
   names (`"Class Feat 4"`, etc.) are approximated from each feat's level; the
   converter reports every constructed id and any slot collisions so you can
   verify placement after import.
5. Background boost selections (`getBackgroundBoostFreeSelection` etc.) default
   to `0`.

The converter prints a report of what matched the catalogue versus what was
constructed, so unmatched items are never hidden.

## Tests

```bash
python3 -m pytest
```

Synthetic fixtures live in `tests/fixtures/` (`sample_actor.json` and
`sample.pbex`, which encodes the Pathbuilder save schema). The suite includes a
shape check that pins the converter output against every key in that schema.
